# admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import AgencyLevel, UserAgencyProfile, CustomUser  # aur baaki models

@admin.register(AgencyLevel)
class AgencyLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'direct_commission_percent', 'team_commission_percent', 
                    'min_referrals_for_level', 'min_deposit_for_level', 'is_active')
    list_editable = ('direct_commission_percent', 'team_commission_percent', 'is_active')
    list_filter = ('is_active', 'level')
    search_fields = ('name',)
    ordering = ('level',)


@admin.register(UserAgencyProfile)
class UserAgencyProfileAdmin(admin.ModelAdmin):
    list_display = ('user_link', 'current_level', 'total_direct_referrals', 'total_team_referrals',
                    'yesterday_commission_colored', 'total_commission_earned', 'last_calculated')
    list_filter = ('current_level',)
    search_fields = ('user__phone_number', 'user__username')
    readonly_fields = ('total_direct_referrals', 'total_team_referrals', 'yesterday_commission', 
                       'total_commission_earned', 'last_calculated')
    actions = ['recalculate_stats']

    def user_link(self, obj):
        return format_html('<a href="/admin/{}/{}/{}/change/">{}</a>', 
                           obj.user._meta.app_label, obj.user._meta.model_name, obj.user.pk, obj.user.phone_number)
    user_link.short_description = "User"

    def yesterday_commission_colored(self, obj):
        color = 'green' if obj.yesterday_commission > 0 else 'red'
        return format_html('<span style="color: {};">₹{:.2f}</span>', color, obj.yesterday_commission)
    yesterday_commission_colored.short_description = "Yesterday Commission"

    @admin.action(description="Recalculate selected profiles stats")
    def recalculate_stats(self, request, queryset):
        for profile in queryset:
            profile.update_stats()
        self.message_user(request, "Stats recalculated successfully.")


# CustomUser ko bhi thoda enhance kar sakte ho
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):  # ya UserAdmin inherit karo agar chaho
    list_display = ('phone_number', 'username', 'coins', 'referral_code', 'referred_by_link', 'agency_level')
    search_fields = ('phone_number', 'username', 'referral_code')
    list_filter = ('is_active', 'is_staff')

    def referred_by_link(self, obj):
        if obj.referred_by:
            return format_html('<a href="/admin/core/customuser/{}/change/">{}</a>', 
                               obj.referred_by.pk, obj.referred_by.phone_number)
        return "-"
    referred_by_link.short_description = "Referred By"

    def agency_level(self, obj):
        return obj.agency_profile.current_level if hasattr(obj, 'agency_profile') else "-"
    agency_level.short_description = "Agency Level"