from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),  # Route for login
    path('logout/', views.logout_view, name='logout'),  # Route for logout

    path('game/<int:game_id>/', views.game_view, name='game_view'),
]