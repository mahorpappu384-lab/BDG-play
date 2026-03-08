from rest_framework import serializers
from .models import GameHistory, DepositRequest, WithdrawRequest
from core.models import GameSettings  # min/max bet के लिए


class GameHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = GameHistory
        fields = '__all__'
        read_only_fields = ('user', 'win_amount', 'is_win', 'result', 'created_at')


class DepositRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepositRequest
        fields = ['id', 'amount', 'status', 'screenshot_url', 'created_at']
        read_only_fields = ['status', 'created_at']


class WithdrawRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawRequest
        fields = ['id', 'amount', 'payment_details', 'status', 'screenshot_url', 'created_at']
        read_only_fields = ['status', 'created_at']


class PlayGameSerializer(serializers.Serializer):
    game_type = serializers.ChoiceField(choices=GameHistory.GAME_TYPES)
    bet_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1)
    choice     = serializers.CharField(required=False, allow_blank=True)

    def validate_bet_amount(self, value):
        settings = GameSettings.objects.first()
        if not settings:
            raise serializers.ValidationError("Game settings not configured.")
        
        if value < settings.min_bet:
            raise serializers.ValidationError(f"Minimum bet is {settings.min_bet}")
        if value > settings.max_bet:
            raise serializers.ValidationError(f"Maximum bet is {settings.max_bet}")
        return value