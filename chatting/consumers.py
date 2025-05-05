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

        if not session_key or not await database_sync_to_async(Session.objects.filter(session_key=session_key).exists)():
            print(f"[ChatConsumer] Invalid session: {session_key or 'None'}")
            await self.close(code=4001, reason="Invalid session")
            return

        await self.channel_layer.group_add(self.chat_group_name, self.channel_name)
        print(f"[ChatConsumer] Connected to group: {self.chat_group_name}, channel: {self.channel_name}")
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'chat_group_name'):
            await self.channel_layer.group_discard(self.chat_group_name, self.channel_name)
            print(f"[ChatConsumer] Disconnected from group: {self.chat_group_name}, channel: {self.channel_name}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message')
            username = self.scope['user'].username
            if message and username:
                await self.channel_layer.group_send(
                    self.chat_group_name,
                    {
                        'type': 'chat_message',
                        'username': username,
                        'message': message
                    }
                )
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid message format.'
            }))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'username': event['username'],
            'message': event['message']
        }))