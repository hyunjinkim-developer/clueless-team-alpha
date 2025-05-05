from channels.generic.websocket import AsyncWebsocketConsumer
import json
from django.conf import settings
from django.contrib.sessions.models import Session
from channels.db import database_sync_to_async

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        self.chat_group_name = f"chat_{self.game_id}"
        cookies = self.scope.get('cookies', {})
        session_key = cookies.get('sessionid')
        print(f"[ChatConsumer] Connecting to game {self.game_id}, session_key: {session_key}")
        print(f"[ChatConsumer] Scope cookies: {cookies}")

        if not session_key or not await database_sync_to_async(Session.objects.filter(session_key=session_key).exists)():
            print(f"[ChatConsumer] Invalid session: {session_key or 'None'}")
            await self.close(code=4001, reason="Invalid session")
            return

        user = self.scope.get('user')
        print(f"[ChatConsumer] User: {user}, Authenticated: {user.is_authenticated if user else 'No user'}")
        if not user or not user.is_authenticated:
            print(f"[ChatConsumer] User not authenticated")
            await self.close(code=4002, reason="User not authenticated")
            return

        await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
        print(f"[ChatConsumer] Added to group: {self.chat_group_name}, channel: {self.channel_name}")
        await self.accept()
        print(f"[ChatConsumer] WebSocket accepted for game {self.game_id}")

    async def disconnect(self, close_code):
        if hasattr(self, 'chat_group_name'):
            print(f"[ChatConsumer] Disconnecting from group: {self.chat_group_name}, code: {close_code}")
            await self.channel_layer.group_discard(self.chat_group_name, self.channel_name)
            print(f"[ChatConsumer] Disconnected from group: {self.chat_group_name}, channel: {self.channel_name}")

    async def receive(self, text_data):
        print(f"[ChatConsumer] Received raw data: {text_data}")
        try:
            data = json.loads(text_data)
            message = data.get('message')
            username = self.scope['user'].username
            print(f"[ChatConsumer] Received message from {username}: {message}")
            if message and username:
                await self.channel_layer.group_send(
                    self.chat_group_name,
                    {
                        'type': 'chat_message',
                        'username': username,
                        'message': message
                    }
                )
                print(f"[ChatConsumer] Broadcasted message to group: {self.chat_group_name}")
        except json.JSONDecodeError:
            print(f"[ChatConsumer] JSON decode error: {text_data}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid message format.'
            }))

    async def chat_message(self, event):
        print(f"[ChatConsumer] Sending chat message to client: {event}")
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'username': event['username'],
            'message': event['message']
        }))