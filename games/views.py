from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import random
import logging

from core.models import CustomUser, Wallet, Transaction, GameSettings
from .models import GameHistory, DepositRequest, WithdrawRequest
from .serializers import (
    PlayGameSerializer, GameHistorySerializer,
    DepositRequestSerializer, WithdrawRequestSerializer
)

logger = logging.getLogger(__name__)


class PlayGameView(APIView):
    """
    यूजर गेम खेलता है → बैलेंस से बेट कटता है → रिजल्ट के आधार पर जीत/हार
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PlayGameSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        game_type = serializer.validated_data['game_type']
        bet_amount = serializer.validated_data['bet_amount']

        user = request.user
        wallet, _ = Wallet.objects.get_or_create(user=user)

        if wallet.balance < bet_amount:
            return Response({"detail": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)

        # Game settings से min/max bet चेक कर सकते हो (optional)
        settings = GameSettings.objects.first()
        if settings and (bet_amount < settings.min_bet or bet_amount > settings.max_bet):
            return Response(
                {"detail": f"Bet amount must be between {settings.min_bet} and {settings.max_bet}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Deduct bet
            wallet.balance -= bet_amount
            wallet.save(update_fields=['balance'])

            bet_tx = Transaction.objects.create(
                user=user,
                type='bet',
                amount=-bet_amount,  # अब negative रख रहे हैं (bet = -ve)
                balance_after=wallet.balance,
                description=f"Bet on {game_type}"
            )

            # Game result logic
            win = False
            multiplier = Decimal('0')
            result_str = "Lose"
            extra_data = {}

            if game_type == "color_prediction":
                # ~45% win chance (real में provably fair RNG इस्तेमाल करो)
                win = random.random() < 0.45
                if win:
                    multiplier = random.choice([Decimal('1.92'), Decimal('2.0'), Decimal('2.5'), Decimal('3.0')])
                    result_str = f"Win ×{multiplier}"

            elif game_type == "dice_roll":
                roll = random.randint(1, 6)
                choice = request.data.get('choice', '').lower()
                if choice not in ['high', 'low']:
                    raise serializers.ValidationError({"choice": "Must be 'high' or 'low'"})

                win = (choice == "high" and roll >= 4) or (choice == "low" and roll <= 3)
                if win:
                    multiplier = Decimal('2.0')
                    result_str = f"Win (Rolled {roll})"
                else:
                    result_str = f"Lose (Rolled {roll})"
                extra_data = {"roll": roll}

            elif game_type == "slot_lottery":
                symbols = ["🍒", "🍋", "🍉", "⭐", "💎", "7️⃣"]
                s1, s2, s3 = [random.choice(symbols) for _ in range(3)]
                if s1 == s2 == s3:
                    win = True
                    multiplier = Decimal('5.0')
                    result_str = f"Jackpot! {s1} {s2} {s3}"
                elif len(set([s1, s2, s3])) == 2:
                    win = True
                    multiplier = Decimal('2.0')
                    result_str = f"Win {s1} {s2} {s3}"
                else:
                    result_str = f"Lose {s1} {s2} {s3}"
                extra_data = {"symbols": f"{s1} {s2} {s3}"}

            elif game_type == "number_guess":
                try:
                    choice = int(request.data.get('choice'))
                    if not 1 <= choice <= 10:
                        raise ValueError
                except:
                    return Response({"detail": "Choice must be integer 1-10"}, status=400)

                result = random.randint(1, 10)
                win = (choice == result)
                if win:
                    multiplier = Decimal('9.0')  # 1:9 payout
                    result_str = f"Correct! ({result})"
                else:
                    result_str = f"Wrong (was {result})"
                extra_data = {"guessed": choice, "result": result}

            else:
                return Response({"detail": "Invalid game type"}, status=400)

            win_amount = bet_amount * multiplier if win else Decimal('0')

            if win:
                wallet.balance += win_amount
                wallet.save(update_fields=['balance'])

                Transaction.objects.create(
                    user=user,
                    type='win',
                    amount=win_amount,
                    balance_after=wallet.balance,
                    description=f"Win on {game_type}"
                )

            # Game history
            GameHistory.objects.create(
                user=user,
                game_type=game_type,
                bet_amount=bet_amount,
                result=result_str,
                win_amount=win_amount,
                is_win=win,
                extra_data=extra_data
            )

        return Response({
            "message": "Game played",
            "win": win,
            "win_amount": float(win_amount),
            "multiplier": float(multiplier),
            "new_balance": float(wallet.balance),
            "transaction_id": str(bet_tx.id),
            "result": result_str,
            **extra_data
        })


class GameHistoryListView(generics.ListAPIView):
    serializer_class = GameHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GameHistory.objects.filter(user=self.request.user).order_by('-created_at')


class DepositRequestCreateView(generics.CreateAPIView):
    """
    Deposit request create + screenshot URL save (ImageKit से आया हुआ)
    """
    serializer_class = DepositRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        with transaction.atomic():
            deposit = serializer.save(
                user=self.request.user,
                status='pending'
            )

            wallet, _ = Wallet.objects.get_or_create(user=self.request.user)

            Transaction.objects.create(
                user=self.request.user,
                type='deposit',
                amount=deposit.amount,
                balance_after=wallet.balance,
                description=f"Deposit request #{deposit.id} - Pending (Proof: {deposit.screenshot_url or 'No proof'})",
                status='pending'
            )

        return deposit


class WithdrawRequestCreateView(generics.CreateAPIView):
    """
    Withdraw request → balance check → deduct → pending status
    """
    serializer_class = WithdrawRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        amount = serializer.validated_data['amount']

        # Min withdraw limit (optional - GameSettings से ले सकते हो)
        MIN_WITHDRAW = Decimal('100.00')
        if amount < MIN_WITHDRAW:
            raise serializers.ValidationError({"amount": f"Minimum withdrawal is ₹{MIN_WITHDRAW}"})

        wallet, _ = Wallet.objects.get_or_create(user=user)
        if wallet.balance < amount:
            raise serializers.ValidationError({"amount": "Insufficient balance"})

        with transaction.atomic():
            wallet.balance -= amount
            wallet.save(update_fields=['balance'])

            withdraw = serializer.save(
                user=user,
                status='pending'
            )

            Transaction.objects.create(
                user=user,
                type='withdraw',
                amount=-amount,  # negative for withdraw
                balance_after=wallet.balance,
                description=f"Withdraw request #{withdraw.id} - Pending",
                status='pending'
            )

        return withdraw


class MyDepositListView(generics.ListAPIView):
    serializer_class = DepositRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DepositRequest.objects.filter(user=self.request.user).order_by('-created_at')


class MyWithdrawListView(generics.ListAPIView):
    serializer_class = WithdrawRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return WithdrawRequest.objects.filter(user=self.request.user).order_by('-created_at')