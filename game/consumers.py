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

        # Move Validation: Check if the move is valid based on adjacency
        valid_moves = {
            'Study': ['Hallway1', 'Hallway3', 'Kitchen'],
            'Hall': ['Hallway1', 'Hallway2', 'Hallway4'],
            'Lounge': ['Hallway2', 'Hallway5', 'Conservatory'],
            'Library': ['Hallway3', 'Hallway6', 'Hallway8'],
            'BilliardRoom': ['Hallway4', 'Hallway6', 'Hallway7', 'Hallway9'],
            'DiningRoom': ['Hallway5', 'Hallway7', 'Hallway10'],
            'Conservatory': ['Hallway8', 'Hallway11', 'Lounge'],
            'Ballroom': ['Hallway9', 'Hallway11', 'Hallway12'],
            'Kitchen': ['Hallway10', 'Hallway12', 'Study'],
            'Hallway1': ['Study', 'Hall'],
            'Hallway2': ['Hall', 'Lounge'],
            'Hallway3': ['Study', 'Library'],
            'Hallway4': ['Hall', 'BilliardRoom'],
            'Hallway5': ['Lounge', 'DiningRoom'],
            'Hallway6': ['Library', 'BilliardRoom'],
            'Hallway7': ['BilliardRoom', 'DiningRoom'],
            'Hallway8': ['Library', 'Conservatory'],
            'Hallway9': ['BilliardRoom', 'Ballroom'],
            'Hallway10': ['DiningRoom', 'Kitchen'],
            'Hallway11': ['Conservatory', 'Ballroom'],
            'Hallway12': ['Ballroom', 'Kitchen']
        }
        if to_location not in valid_moves.get(from_location, []):
            await self.send(text_data=json.dumps({'error': 'Invalid move - locations not adjacent'}))
            return

        # Turn Enforcement: Ensure it’s the player’s turn
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'Not your turn'}))
            return

        # Update player location
        player.location = to_location
        await database_sync_to_async(player.save)()

        # Rotate turn to next player
        players = await database_sync_to_async(lambda: list(game.players.all()))()
        current_index = players.index(player)
        next_player = players[(current_index + 1) % len(players)]
        player.turn = False
        next_player.turn = True
        await database_sync_to_async(player.save)()
        await database_sync_to_async(next_player.save)()

        # Broadcast updated game state
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )
        print(
            f"Player {player.username} moved from {from_location} to {to_location}, turn passed to {next_player.username}")

    @database_sync_to_async
    def get_game_state(self):
        game = Game.objects.get(id=self.game_id)
        players = list(game.players.values('username', 'character', 'location', 'turn', 'hand'))
        return {
            'case_file': game.case_file if not game.is_active else None,
            'players': players,
            'is_active': game.is_active,
            'rooms': ROOMS,
            'hallways': HALLWAYS,
            'weapons': WEAPONS
        }