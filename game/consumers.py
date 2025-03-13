from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from .models import *
from .constants import *

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("Connecting to WebSocket...")
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        print(f"Game ID set to: {self.game_id}")
        self.game_group_name = f"game_{self.game_id}"
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()
        print(f"WebSocket connected for game {self.game_id}")

        # Broadcast game state on connect
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )

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
            pass
        elif message_type == 'accuse':
            pass
        else:
            await self.send(text_data=json.dumps({'message': 'Echo: ' + text_data}))

    async def game_update(self, event):
        game_state = event['game_state']
        print(f"Received game_update event for game {self.game_id}")
        players = game_state.get('players', [])
        for player in players:
            print(f"  - ID: {player['username']}, Player_is_active: {player['is_active']}, Character: {player['character']}, Location: {player['location']}")
        await self.send(text_data=json.dumps({
            'type': 'game_update',
            'game_state': game_state
        }))

    @database_sync_to_async
    def get_game(self):
        return Game.objects.get(id=self.game_id)

    @database_sync_to_async
    def get_player(self, username):
        game = Game.objects.get(id=self.game_id)
        return Player.objects.get(game=game, username=username)

    async def handle_move(self, data):
        to_location = data.get('location')
        if not to_location:
            await self.send(text_data=json.dumps({'error': 'No location provided'}))
            return

        game = await self.get_game()
        player = await self.get_player(self.scope['user'].username)
        from_location = player.location

        player.location = to_location
        await database_sync_to_async(player.save)()

        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )
        print(f"Player {player.username} moved from {from_location} to {to_location}")

    @database_sync_to_async
    def get_game_state(self):
        game = Game.objects.get(id=self.game_id)
        players = list(game.players.filter(is_active=True).values('username', 'character', 'location', 'is_active', 'turn', 'hand'))
        return {
            'case_file': game.case_file if not game.is_active else None,
            'game_is_active': game.is_active,
            'players': players,
            'rooms': ROOMS,
            'hallways': HALLWAYS,
            'weapons': WEAPONS
        }

    async def join_game(self, data):
        # Placeholder for join_game logic if needed later
        pass