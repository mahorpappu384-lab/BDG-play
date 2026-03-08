from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Referral, GameSettings, Transaction
from django.db import transaction


@receiver(post_save, sender=CustomUser)
def handle_referral_and_welcome(sender, instance, created, **kwargs):
    if created:
        # Welcome bonus
        try:
            settings = GameSettings.objects.first()
            if settings and settings.welcome_bonus > 0:
                instance.coins += settings.welcome_bonus
                instance.save(update_fields=['coins'])

                Transaction.objects.create(
                    user=instance,
                    type='bonus',
                    amount=settings.welcome_bonus,
                    balance_after=instance.coins,
                    description='Welcome Bonus'
                )
        except:
            pass  # settings नहीं हैं तो skip

        # Referral check (अगर referred_by set है)
        if instance.referred_by:
            try:
                settings = GameSettings.objects.first() or GameSettings()
                bonus = settings.referral_bonus or 50

                with transaction.atomic():
                    instance.referred_by.coins += bonus
                    instance.referred_by.save(update_fields=['coins'])

                    Referral.objects.create(
                        referrer=instance.referred_by,
                        referred_user=instance,
                        bonus_given=bonus
                    )

                    Transaction.objects.create(
                        user=instance.referred_by,
                        type='referral',
                        amount=bonus,
                        balance_after=instance.referred_by.coins,
                        description=f'Referral bonus for {instance.username}'
                    )
            except:
                pass