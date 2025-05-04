from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),  # Route for login
    path('logout/', views.logout_view, name='logout'),  # Route for logout
    path('game/<int:game_id>/start/', views.start_game, name='start_game'),
    path('game/<int:game_id>/', views.game_view, name='game_view'),
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)