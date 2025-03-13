from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from .models import *
from .constants import *

# For debugging purpose, remove after development
DEBUG = False

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("Connecting to WebSocket...")  # Debug log for connection start
        # Extract game_id from the WebSocket URL (e.g., /ws/game/1/)
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        print(f"Game ID set to: {self.game_id}")  # Debug log for game_id
        # Define the WebSocket group name for this game
        self.game_group_name = f"game_{self.game_id}"
        # Add this client to the game’s WebSocket group
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        # Accept the WebSocket connection
        await self.accept()
        print(f"WebSocket connected for game {self.game_id}")  # Debug log for successful connection

        # Broadcast the initial game state to all clients in the group
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',  # Message type for clients to process
                'game_state': game_state  # Current game state
            }
        )

    # Handle WebSocket disconnection when a client leaves
    async def disconnect(self, close_code):
        if hasattr(self, 'game_group_name'):  # Check if group was set
            # Remove this client from the game’s WebSocket group
            await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
            print(f"WebSocket disconnected for game {self.game_id}")  # Debug log for disconnection

    # Handle incoming messages from clients via WebSocket
    async def receive(self, text_data):
        print(f"Received message: {text_data}")  # Debug log for incoming message
        data = json.loads(text_data)  # Parse JSON message
        message_type = data.get('type')  # Extract message type
        if message_type == 'join_game':
            await self.join_game(data)  # Handle join_game message (placeholder)
        elif message_type == 'move':
            await self.handle_move(data)  # Handle player move request
        elif message_type == 'suggest':
            pass  # Placeholder for suggestion logic
        elif message_type == 'accuse':
            pass  # Placeholder for accusation logic
        else:
            # Echo unrecognized messages back to the client
            await self.send(text_data=json.dumps({'message': 'Echo: ' + text_data}))

    # Handle game_update events broadcast to the group
    async def game_update(self, event):
        game_state = event['game_state']  # Extract game state from event
        print(f"Received game_update event for game {self.game_id}")  # Debug log
        players = game_state.get('players', [])  # Get players list, default to empty
        if DEBUG:
            # Log each player’s details for debugging
            for player in players:
                print(
                    f"  - Username: {player['username']}, Character: {player['character']}, Location: {player['location']}, Is Active: {player['is_active']}")
        # Send the game state to this client
        await self.send(text_data=json.dumps({
            'type': 'game_update',
            'game_state': game_state
        }))

    # Async wrapper for synchronous database query to get Game instance
    @database_sync_to_async
    def get_game(self):
        return Game.objects.get(id=self.game_id)  # Fetch Game by ID

    # Async wrapper for synchronous database query to get Player instance
    @database_sync_to_async
    def get_player(self, username):
        game = Game.objects.get(id=self.game_id)  # Fetch Game by ID
        return Player.objects.get(game=game, username=username)  # Fetch Player by username and game

    # Handle player move requests from clients
    async def handle_move(self, data):
        to_location = data.get('location')  # Extract target location from message
        if not to_location:
            # Send error if no location provided
            await self.send(text_data=json.dumps({'error': 'No location provided'}))
            return

        game = await self.get_game()  # Get Game instance
        player = await self.get_player(self.scope['user'].username)  # Get current Player
        from_location = player.location  # Store current location

        player.location = to_location  # Update player’s location
        await database_sync_to_async(player.save)()  # Save changes asynchronously

        # Broadcast updated game state to all clients
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )
        print(f"Player {player.username} moved from {from_location} to {to_location}")  # Debug log for move

    # Async wrapper for synchronous database query to get game state
    # Sync with views.py
    @database_sync_to_async
    def get_game_state(self):
        game = Game.objects.get(id=self.game_id)  # Fetch Game by ID
        # Fetch all players (active or inactive) with all fields
        fields = [f.name for f in Player._meta.fields]  # Dynamically get all field names from Player model
        players = list(game.players.values(*fields)) # Fetch all fields for all players
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