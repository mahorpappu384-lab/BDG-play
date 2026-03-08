from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import random
from django.conf import settings
import string
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import post_save
from decimal import Decimal


class CustomUserManager(BaseUserManager):
    """
    Custom user manager जो phone_number को primary बनाता है
    और username को optional रखता है
    """
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The phone_number field must be set')

        # username को optional रखो → अगर नहीं दिया तो phone_number ही username बना दो
        username = extra_fields.pop('username', phone_number)

        user = self.model(
            phone_number=phone_number,
            username=username,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)


class CustomUser(AbstractUser):
    # username optional (phone primary login field)
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)

    # phone_number मुख्य login field
    phone_number = models.CharField(
        max_length=15,
        unique=True,
        blank=False,
        null=True,
        verbose_name="Phone Number"
    )
    profile_photo = models.URLField(max_length=500, blank=True, null=True)

    email = models.EmailField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Email (optional)"
    )

    coins = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    referral_code = models.CharField(max_length=10, unique=True, blank=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Custom manager
    objects = CustomUserManager()

    # Login अब phone_number से होगा
    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []  # कोई required नहीं

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # अगर username खाली है तो phone_number से भर दो
        if not self.username:
            self.username = self.phone_number

        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone_number or self.username or "User"


class Wallet(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.user} - {self.balance}"


class Transaction(models.Model):
    TYPE_CHOICES = (
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('bet', 'Bet'),
        ('win', 'Win'),
        ('bonus', 'Bonus'),
        ('referral', 'Referral Bonus'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name="User"
    )

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Transaction Type"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Amount",
        help_text="Positive for deposit/win/bonus, negative for withdraw/bet"
    )

    balance_after = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Balance After Transaction"
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Description",
        help_text="Optional note about the transaction"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='completed',
        verbose_name="Status"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"
        # optional: अगर एक user की एक ही time पर duplicate entry रोकना हो
        # indexes = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        sign = '+' if self.amount > 0 else '-'
        return f"{self.user} | {self.type.upper()} | {sign}{abs(self.amount):.2f} | {self.status}"

    @property
    def display_amount(self):
        """Frontend के लिए formatted amount with sign"""
        sign = '+' if self.amount > 0 else '-'
        return f"{sign}{abs(self.amount):.2f}"

    @property
    def is_positive(self):
        return self.amount > 0

    @property
    def is_pending(self):
        return self.status == 'pending'


class Referral(models.Model):
    referrer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='referrals_given')
    referred_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='referred_by_me')
    bonus_given = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('referrer', 'referred_user')

    def __str__(self):
        return f"{self.referrer} → {self.referred_user}"


class GameSettings(models.Model):
    min_bet = models.DecimalField(max_digits=8, decimal_places=2, default=10.00)
    max_bet = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    referral_bonus = models.DecimalField(max_digits=8, decimal_places=2, default=50.00)
    welcome_bonus = models.DecimalField(max_digits=8, decimal_places=2, default=100.00)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Game Settings"

    def __str__(self):
        return "Global Game Settings"

class AttendanceRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    bonus_given = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.phone_number} - {self.date}"


class GiftCode(models.Model):
    code = models.CharField(max_length=12, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)
    max_uses = models.PositiveIntegerField(default=1)           # added: how many times code can be used
    used_count = models.PositiveIntegerField(default=0)
    used_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='used_gift_codes')
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.code

    @property
    def is_expired(self):
        return self.expires_at and self.expires_at < timezone.now()

    @property
    def can_be_used(self):
        return self.is_active and not self.is_expired and self.used_count < self.max_uses


class RechargePromotion(models.Model):
    title = models.CharField(max_length=120)
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    bonus_percent = models.PositiveIntegerField(default=10)      # 10 = 10%
    max_bonus = models.DecimalField(max_digits=12, decimal_places=2, default=5000.00)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

# models.py (tumhare existing CustomUser ke neeche add karo)

class AgencyLevel(models.Model):
    """
    Admin se levels define kar sake (Bronze, Silver, etc.)
    Har level ke alag commission rates
    """
    name = models.CharField(max_length=50, unique=True)  # e.g. Bronze, Silver, Gold
    level = models.PositiveIntegerField(unique=True)
    direct_commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)   # %
    team_commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)     # team pe kitna %
    min_referrals_for_level = models.PositiveIntegerField(default=0)
    min_deposit_for_level = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['level']

    def __str__(self):
        return f"{self.name} (Level {self.level})"


class UserAgencyProfile(models.Model):
    """
    Har user ka agency profile (level, commission tracking)
    """
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='agency_profile')
    current_level = models.ForeignKey(AgencyLevel, on_delete=models.SET_NULL, null=True, blank=True)
    total_direct_referrals = models.PositiveIntegerField(default=0)
    total_team_referrals = models.PositiveIntegerField(default=0)  # multi-level count
    yesterday_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_commission_earned = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_calculated = models.DateTimeField(null=True, blank=True)

    def update_stats(self):
        """Stats recalculate karne ka method (signals ya cron job se call karo)"""
        # Direct
        direct = self.user.referred_users.count()
        self.total_direct_referrals = direct

        # Team (simple 2-level example, zyada levels ke liye recursive function banao)
        team_count = 0
        for direct_user in self.user.referred_users.all():
            team_count += direct_user.referred_users.count()
        self.total_team_referrals = team_count

        # Commission calculate (real mein Transaction se sum karo)
        # Example placeholder
        self.yesterday_commission = Decimal('0.00')  # logic add karo

        self.save()

    def __str__(self):
        return f"{self.user} - {self.current_level or 'No Level'}"


# Signals (signals.py mein add karo)
@receiver(post_save, sender=CustomUser)
def create_agency_profile(sender, instance, created, **kwargs):
    if created:
        UserAgencyProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=CustomUser)
def update_referrer_agency_stats(sender, instance, created, **kwargs):
    if created and instance.referred_by:
        try:
            profile = instance.referred_by.agency_profile
            profile.update_stats()
        except:
            pass