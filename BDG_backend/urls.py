"""
gaming URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # API endpoints
    path('api/', include('core.urls')),
    path('api/games/', include('games.urls')),

    # अगर भविष्य में frontend static files serve करनी हो तो
    # path('', include('your_frontend_app.urls')),  # optional
]

# Development में media files serve करने के लिए
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)