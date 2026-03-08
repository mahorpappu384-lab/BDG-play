from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    RegisterView,
    ProfileView,
    WalletView,
    TransactionListView,
    GameSettingsView,
    LogoutView,
    ActivitySummaryView,
    ClaimAttendanceBonusView,
    RedeemGiftCodeView,
    AgencyStatsView,
    ImageKitAuthParamsView,
    HealthCheckView,
)

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),     # login
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    # urls.py (add to existing or new router)
    path('activity/summary/', ActivitySummaryView.as_view(), name='activity-summary'),
    path('agency-stats/', AgencyStatsView.as_view(), name='agency-stats'),
    # core/urls.py - add these lines
    path('activity/claim-attendance/', ClaimAttendanceBonusView.as_view(), name='claim-attendance'),
    path('activity/redeem-gift/', RedeemGiftCodeView.as_view(), name='redeem-gift'),
    path('imagekit-auth-params/', ImageKitAuthParamsView.as_view(), name='imagekit-auth'),
    path("health/", HealthCheckView.as_view()),

    # User & Wallet
    path('profile/', ProfileView.as_view(), name='profile'),
    path('wallet/', WalletView.as_view(), name='wallet'),
    path('transactions/', TransactionListView.as_view(), name='transactions'),

    # Game Settings (min bet, max bet, referral bonus etc)
    path('game-settings/', GameSettingsView.as_view(), name='game-settings'),
]