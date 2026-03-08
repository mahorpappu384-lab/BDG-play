from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import CustomUser, Wallet, Transaction, Referral, GameSettings, AttendanceRecord, GiftCode, RechargePromotion


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    referral_code = serializers.CharField(required=False, allow_blank=True)
    
    # phone_number required कर दिया
    phone_number = serializers.CharField(required=True, max_length=15)

    class Meta:
        model = CustomUser
        fields = ('phone_number', 'email', 'password', 'password2', 'referral_code')
        extra_kwargs = {
            'email': {'required': False, 'allow_blank': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords don't match."})

        # phone number unique check (DRF auto handle करता है लेकिन extra message के लिए)
        if CustomUser.objects.filter(phone_number=attrs['phone_number']).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already registered."})

        return attrs

    def create(self, validated_data):
        referral_code = validated_data.pop('referral_code', None)
        password = validated_data.pop('password2')  # extra field हटाओ

        # phone_number से user create
        user = CustomUser.objects.create_user(
            phone_number=validated_data['phone_number'],
            email=validated_data.get('email'),
            password=password,
        )

        # Welcome bonus
        if GameSettings.objects.exists():
            settings = GameSettings.objects.first()
            user.coins += settings.welcome_bonus
            user.save(update_fields=['coins'])

        # Referral logic (signals.py में बेहतर handle होगा)
        if referral_code:
            try:
                referrer = CustomUser.objects.get(referral_code=referral_code)
                user.referred_by = referrer
                user.save(update_fields=['referred_by'])
            except CustomUser.DoesNotExist:
                pass  # invalid code → ignore

        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('id', 'phone_number', 'email', 'username', 'coins', 'profile_photo', 'referral_code', 'created_at')
        read_only_fields = ('coins', 'referral_code', 'created_at')


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ('balance',)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'


class GameSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameSettings
        fields = '__all__'

class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = ['date', 'bonus_given', 'created_at']
        read_only_fields = ['date', 'bonus_given', 'created_at']


class GiftCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftCode
        fields = ['code', 'amount', 'is_active', 'used_count', 'max_uses', 'expires_at']
        read_only_fields = ['used_count', 'is_active', 'expires_at']


class RechargePromotionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RechargePromotion
        fields = ['title', 'min_amount', 'bonus_percent', 'max_bonus', 'valid_until']