from django.db import models
from django.conf import settings
from decimal import Decimal

class GameHistory(models.Model):
    GAME_TYPES = (
        ('color_prediction', 'Color Prediction'),
        ('dice_roll', 'Dice Roll'),
        ('lucky_spin', 'Lucky Spin'),
        ('slot_lottery', 'Slot Lottery'),
        ('number_guess', 'Number Guess'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='game_histories')
    game_type = models.CharField(max_length=30, choices=GAME_TYPES)
    bet_amount = models.DecimalField(max_digits=12, decimal_places=2)
    result = models.CharField(max_length=100, blank=True)          # e.g. "red", "6", "win", etc.
    win_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_win = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Game Histories"

    def __str__(self):
        return f"{self.user} - {self.game_type} - {self.bet_amount}"


class DepositRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposit_requests')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    screenshot_url = models.URLField(max_length=500, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_deposits')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - ₹{self.amount} - {self.status}"


class WithdrawRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='withdraw_requests')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_details = models.TextField()  # UPI ID, Bank details, etc.
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    screenshot_url = models.URLField(max_length=500, blank=True, null=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_withdraws')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - ₹{self.amount} - {self.status}"