# game/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("Connecting to WebSocket...")
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        print(f"Game ID set to: {self.game_id}")
        self.game_group_name = f"game_{self.game_id}"
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()
        print(f"WebSocket connected for game {self.game_id}")

    async def disconnect(self, close_code):
        if hasattr(self, 'game_group_name'):
            await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
            print(f"WebSocket disconnected for game {self.game_id}")

    async def receive(self, text_data):
        print(f"Received message: {text_data}")
        data = json.loads(text_data)
        message_type = data.get('type')
        if message_type == 'join_game':
            await self.join_game(data)
        elif message_type == 'move':
            await self.handle_move(data)
        elif message_type == 'suggest':
            await self.handle_suggestion(data)
        elif message_type == 'accuse':
            await self.handle_accusation(data)
        else:
            await self.send(text_data=json.dumps({'message': 'Echo: ' + text_data}))

    async def game_update(self, event):
        game_state = event['game_state']
        print(f"Received game_update event for game {self.game_id}")

        # Log all players and their characters
        players = game_state.get('players', [])
        print("Current players in the game:")
        for player in players:
            username = player.get('username', 'Unknown')
            character = player.get('character', 'No character assigned')
            print(f"  - User: {username}, Character: {character}")

        # Send the game state to the client
        await self.send(text_data=json.dumps({
                'type': 'game_update',
                'game_state': game_state
        }))