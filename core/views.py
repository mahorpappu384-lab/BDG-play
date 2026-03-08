from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.permissions import AllowAny
from django.db import transaction
from decimal import Decimal
import random

# ImageKit integration (pip install imagekitio)
from imagekitio import ImageKit

from .models import (
    CustomUser, Wallet, Transaction, GameSettings,
    AttendanceRecord, GiftCode, RechargePromotion, UserAgencyProfile,
)

from .serializers import (
    RegisterSerializer, UserSerializer, WalletSerializer,
    TransactionSerializer, GameSettingsSerializer,
    AttendanceRecordSerializer, GiftCodeSerializer, RechargePromotionSerializer
)

User = get_user_model()

# ImageKit client (private key sirf yahan rakho – kabhi frontend mein mat daalna!)
imagekit = ImageKit(
    private_key="private_HISF9EY2ymlDhuARtpNnjcws+mw="   # ← only this is required
)

# ────────────────────────────────────────────────
# Existing views (Register, Profile, Wallet, etc.)
# ────────────────────────────────────────────────

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        user = request.user
        profile_photo = request.data.get('profile_photo')

        if profile_photo:
            user.profile_photo = profile_photo
            user.save(update_fields=['profile_photo'])
            print(f"[Profile Update] Saved profile_photo for {user.phone_number}: {profile_photo}")  # ← Add this log
        else:
            print("[Profile Update] No profile_photo in request data")

        serializer = UserSerializer(user)
        return Response(serializer.data)

class WalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        serializer = WalletSerializer(wallet)
        return Response(serializer.data)


class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')


class GameSettingsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        settings = GameSettings.objects.first()
        if not settings:
            settings = GameSettings.objects.create()
        serializer = GameSettingsSerializer(settings)
        return Response(serializer.data)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ────────────────────────────────────────────────
# NEW: Activity related endpoints
# ────────────────────────────────────────────────

class ActivitySummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()

        today_att = AttendanceRecord.objects.filter(user=user, date=today).first()
        today_bonus = today_att.bonus_given if today_att else Decimal('0.00')

        bonus_breakdown = {
            'referral': Transaction.objects.filter(
                user=user, type='referral'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),

            'attendance': Transaction.objects.filter(
                user=user, type='bonus', description__icontains='Attendance'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),

            'welcome': Transaction.objects.filter(
                user=user, type='bonus', description='Welcome Bonus'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),

            'gift': Transaction.objects.filter(
                user=user, type='bonus', description__icontains='Gift code'
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),

            'rebate': Decimal('0.00'),
            'jackpot': Decimal('0.00'),
            'other': Decimal('0.00'),
        }

        total_bonus = sum(bonus_breakdown.values())

        recharge_promo = RechargePromotion.objects.filter(
            is_active=True,
            valid_from__lte=timezone.now(),
            valid_until__gte=timezone.now()
        ).order_by('-valid_from').first()

        data = {
            "today_bonus": float(today_bonus),
            "total_bonus": float(total_bonus),
            "referral_count": user.referred_users.count(),
            "referral_bonus_earned": float(bonus_breakdown['referral']),
            "can_claim_today": today_att is None,
            "breakdown": {
                "referral_bonus": float(bonus_breakdown['referral']),
                "attendance_bonus": float(bonus_breakdown['attendance']),
                "rebate_bonus": float(bonus_breakdown['rebate']),
                "gift_bonus": float(bonus_breakdown['gift']),
                "jackpot_bonus": float(bonus_breakdown['jackpot']),
                "other_bonus": float(bonus_breakdown['other']),
            },
            "recharge_promo": RechargePromotionSerializer(recharge_promo).data if recharge_promo else None
        }

        return Response(data)


class ClaimAttendanceBonusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        today = timezone.now().date()

        with transaction.atomic():
            att, created = AttendanceRecord.objects.get_or_create(
                user=user,
                date=today,
                defaults={'bonus_given': Decimal('0.00')}
            )

            if not created:
                return Response(
                    {"detail": "You have already claimed today's attendance bonus."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            settings = GameSettings.objects.first()
            bonus = Decimal('10.00')
            if settings:
                bonus = getattr(settings, 'daily_attendance_bonus', Decimal('10.00'))

            att.bonus_given = bonus
            att.save()

            wallet, _ = Wallet.objects.get_or_create(user=user)
            wallet.balance += bonus
            wallet.save()

            Transaction.objects.create(
                user=user,
                type='bonus',
                amount=bonus,
                balance_after=wallet.balance,
                description='Daily Attendance Bonus'
            )

        return Response({
            "message": "Attendance bonus claimed!",
            "amount": float(bonus),
            "new_balance": float(wallet.balance)
        }, status=status.HTTP_200_OK)


class RedeemGiftCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code_str = request.data.get('code')
        if not code_str:
            return Response({"detail": "Code is required"}, status=400)

        try:
            gift = GiftCode.objects.get(code=code_str.upper())
        except GiftCode.DoesNotExist:
            return Response({"detail": "Invalid gift code"}, status=400)

        if not gift.can_be_used:
            return Response({"detail": "This gift code is no longer valid or has been used"}, status=400)

        with transaction.atomic():
            user = request.user
            wallet, _ = Wallet.objects.get_or_create(user=user)

            wallet.balance += gift.amount
            wallet.save()

            gift.used_by = user
            gift.used_at = timezone.now()
            gift.used_count += 1
            if gift.used_count >= gift.max_uses:
                gift.is_active = False
            gift.save()

            Transaction.objects.create(
                user=user,
                type='bonus',
                amount=gift.amount,
                balance_after=wallet.balance,
                description=f'Gift code redeemed: {gift.code}'
            )

        return Response({
            "message": "Gift code redeemed successfully!",
            "amount": float(gift.amount),
            "new_balance": float(wallet.balance)
        })


# ────────────────────────────────────────────────
# Agency Stats (already improved)
# ────────────────────────────────────────────────

class AgencyStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        print(f"[AgencyStats] User: {user.phone_number} | Auth: {request.user.is_authenticated}")

        profile, created = UserAgencyProfile.objects.get_or_create(user=user)
        if created:
            print(f"[AgencyStats] Created new profile for {user.phone_number}")

        profile.update_stats()

        yesterday_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) - timezone.timedelta(days=1)
        yesterday_end = yesterday_start + timezone.timedelta(days=1)

        yesterday_commission = Transaction.objects.filter(
            user=user,
            type='referral',
            created_at__range=(yesterday_start, yesterday_end)
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        direct_users_qs = user.referred_users.all()
        direct_register = direct_users_qs.count()

        direct_deposit_count = Transaction.objects.filter(
            user__in=direct_users_qs,
            type='deposit',
            status='completed'
        ).values('user').distinct().count()

        direct_total_amount = Transaction.objects.filter(
            user__in=direct_users_qs,
            type='deposit',
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        team_register = CustomUser.objects.filter(referred_by__referred_by=user).count()

        data = {
            "yesterday_commission": float(yesterday_commission),
            "direct": {
                "register": direct_register,
                "deposit": direct_deposit_count,
                "amount": float(direct_total_amount),
                "first_deposit": 0,
            },
            "team": {
                "register": team_register,
                "deposit": 0,
                "amount": 0,
                "first_deposit": 0,
            },
            "current_level": profile.current_level.name if profile.current_level else "None",
            "invite_code": user.referral_code or "N/A",
            "debug": {
                "profile_exists": True,
                "profile_id": profile.id,
                "total_direct_from_db": profile.total_direct_referrals,
                "total_team_from_db": profile.total_team_referrals,
            }
        }

        return Response(data)


# ────────────────────────────────────────────────
# NEW: ImageKit Authentication Params (secure upload ke liye)
# ────────────────────────────────────────────────

class ImageKitAuthParamsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            import time
            import hmac
            import hashlib

            current_time = int(time.time())

            # Token: usually milliseconds as string (your current style is fine)
            token = str(current_time * 1000)

            # Expire: current time + 1 hour (3600 seconds)
            expire = current_time + 3600

            # ─── THIS IS THE CRITICAL FIX ───
            # Concatenate raw values ONLY — NO "token=", NO "&", NO "expire="
            data_to_sign = token + str(expire)

            # HMAC-SHA1 using private key
            signature_bytes = hmac.new(
                imagekit.private_key.encode('utf-8'),      # ← your REAL private key here
                data_to_sign.encode('utf-8'),
                hashlib.sha1
            ).digest()

            signature = signature_bytes.hex()           # lowercase hex

            print(f"[ImageKit Auth] Generated → token={token}, expire={expire}, data_signed='{data_to_sign}', signature={signature}")

            return Response({
                "token": token,
                "expire": expire,
                "signature": signature
            })

        except Exception as e:
            print(f"ImageKit auth error: {str(e)}")
            return Response({"error": str(e)}, status=500)

class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "message": "Server is healthy 🚀"
        }, status=status.HTTP_200_OK)