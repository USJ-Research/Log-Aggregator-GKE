from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from home.views import CustomPasswordResetView, CustomPasswordResetConfirmView


urlpatterns = [
    # path('admin/', admin.site.urls),
    path('',include('home.urls')),
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password_reset_done/', auth_views.PasswordResetDoneView.as_view(template_name = 'home/reset_password_sent.html'), name='password_reset_done'),
    path('password_reset_confirm/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password_reset_complete/', auth_views.PasswordResetCompleteView.as_view(template_name = 'home/reset_password_complete.html'), name='password_reset_complete'),
]

urlpatterns = urlpatterns + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)