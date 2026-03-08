from django.urls import path
from .views import (
    PlayGameView,
    GameHistoryListView,
    DepositRequestCreateView,
    WithdrawRequestCreateView,
    MyDepositListView,
    MyWithdrawListView,
)

urlpatterns = [
    path('play/', PlayGameView.as_view(), name='play-game'),
    path('history/', GameHistoryListView.as_view(), name='game-history'),

    path('deposit-request/', DepositRequestCreateView.as_view(), name='deposit-request'),
    path('withdraw-request/', WithdrawRequestCreateView.as_view(), name='withdraw-request'),

    path('my-deposits/', MyDepositListView.as_view(), name='my-deposits'),
    path('my-withdraws/', MyWithdrawListView.as_view(), name='my-withdraws'),
]