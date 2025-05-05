from django.urls import path
from . import consumers, views

urlpatterns = [
   path('ws/chat/<int:game_id>/', consumers.ChatConsumer.as_asgi(), name='chat_websocket'),
   path('test-chat/', views.test_chat_template, name='test_chat_template'),
]