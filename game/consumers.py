from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from .models import *
from .constants import *

# For debugging purpose, disable in production
DEBUG = True  # Debug flag to enable/disable all logging
# Debugging Flag Conventions: DEBUG_<feature> or DEBUG_<method_name>
DEBUG_HANDLE_ACCUSE = True  # <method> based


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("Connecting to WebSocket...")
        # Extract game_id from the WebSocket URL (e.g., /ws/game/1/)
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        print(f"Game ID set to: {self.game_id}")
        # Define the WebSocket group name for this game
        self.game_group_name = f"game_{self.game_id}"
        # Add this client to the game’s WebSocket group
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        # Accept the WebSocket connection
        await self.accept()
        print(f"WebSocket connected for game {self.game_id}")

        # Broadcast the initial game state to all clients in the group
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',  # Message type for clients to process
                'game_state': game_state  # Current game state
            }
        )

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection when a client leaves"""
        if hasattr(self, 'game_group_name'):  # Check if group was set
            # Update player's is_active state to False on disconnect
            player = await self.get_player(self.scope['user'].username)
            if player.is_active:  # Only update if active
                player.is_active = False
                await database_sync_to_async(player.save)()
            # Broadcast player_out without reason for disconnection
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_out',
                    'player': player.username
                }
            )
            # Remove this client from the game’s WebSocket group
            await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
            print(f"WebSocket disconnected for game {self.game_id}")

    # Handle incoming messages from clients via WebSocket
    async def receive(self, text_data):
        print(f"Received message: {text_data}")
        data = json.loads(text_data)  # Parse JSON message
        message_type = data.get('type')  # Extract message type

        if message_type == 'join_game':
            await self.join_game(data)  # Handle join_game message (placeholder)
        elif message_type == 'move':
            Game.begun = True  # Set game status to begun
            await self.handle_move(data)  # Handle player move request
        elif message_type == 'suggest':
            pass  # Placeholder for suggestion logic
        elif message_type == 'accuse':
            await self.handle_accuse(data)
        else:
            # Echo unrecognized messages back to the client
            await self.send(text_data=json.dumps({'message': 'Echo: ' + text_data}))

    async def game_update(self, event):
        """Handle game_update events broadcast to the group"""
        game_state = event['game_state']  # Extract game state from event
        print(f"Received game_update event for game {self.game_id}")
        players = game_state.get('players', [])  # Get players list, default to empty
        if DEBUG:
            # Log each player’s details
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

    async def join_game(self, data):
        # Placeholder for join_game logic if needed later
        pass

    async def handle_move(self, data): 
        """Handle a player's move request with turn restriction."""
        to_location = data.get('location')  # Extract target location from message
        if not to_location:
            # Send error if no location provided
            await self.send(text_data=json.dumps({'error': 'No location provided'}))
            return

        game = await self.get_game()  # Get Game instance
        player = await self.get_player(self.scope['user'].username)  # Get current Player
        from_location = player.location  # Store current location

        # Check if it’s this player’s turn
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'It is not your turn'}))
            return

        # Check if the target location is the same as the current location  
        if to_location == from_location:
            await self.send(text_data=json.dumps({'error': f'You are already at {to_location}'}))
            return

        # Validate move: Check if to_location is adjacent to from_location
        valid_moves = ADJACENCY.get(from_location, [])  # Get list of valid adjacent locations
        # Check if valid_moves contains a hallway that is currently occupied by a different player
        if to_location in valid_moves:
            players = await database_sync_to_async(list)(Player.objects.filter(game=game))
            for p in players:
                # Check if location is a hallway
                if p.location in HALLWAYS and p.location == to_location:
                    if p.location == to_location and p.username != player.username:
                        await self.send(text_data=json.dumps({'error': f'Cannot move to {to_location}, it is occupied by {p.username}'}))
                        return
        
        if to_location not in valid_moves:
            await self.send(
                text_data=json.dumps({'error': f'Invalid move: {to_location} is not adjacent to {from_location}'}))
            return

        player.location = to_location  # Update player’s location
        players = await database_sync_to_async(list)(Player.objects.filter(game=game))  # Fetch all players
        total_player = len(players)  # Get total number of players
        try:
            player_index = players.index(player) # Get index of the current player
        except ValueError:
            player_index = None
        
        # Update turn for the next player
        if player_index is not None:
            player.turn = False  # End current player's turn
            next_player_index = (player_index + 1) % total_player  # Calculate next player index
            next_player = players[next_player_index]  # Get next player
            next_player.turn = True  # Set next player’s turn to True
            await database_sync_to_async(next_player.save)()  # Save changes asynchronously
        
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
        print(f"Player {player.username} moved from {from_location} to {to_location}")

    async def handle_accuse(self, data):
        """ Handle player's accusation without turn enforcement. """
        # Convert data to a dictionary if it's a JSON string from a WebSocket message;
        # otherwise, assume it's already a dictionary (e.g., from test scripts)
        if isinstance(data, str):
            data = json.loads(data)
        suspect = data.get('suspect')
        weapon = data.get('weapon')
        room = data.get('room')
        if not all([suspect, weapon, room]):
            await self.send(text_data=json.dumps({'error': 'Missing accusation details (suspect, weapon or room)'}))
            return

        game = await self.get_game()
        player = await self.get_player(self.scope['user'].username)

        # # Turn check
        # # HyunJin's draft
        # if game.current_turn != player.username:  # Consider adding current_turn attribute to the game table to track the player whose turn it is
        #     await self.send(text_data=json.dumps({'error': 'Not your turn'}))
        #     return

        # Check if player is still active (can make accusations)
        if not player.is_active:
            await self.send(text_data=json.dumps({'error: You are eliminated and cannot make accusations'}))
            return

        # Compare accusation to case file
        accusation = {'suspect': suspect, 'weapon': weapon, 'room': room}
        if accusation == game.case_file:
            # Correct accusation: End the game
            game.is_active = False
            await database_sync_to_async(game.save)()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_end',
                    'winner': player.username,
                    'solution': game.case_file
                }
            )
            print(f"Player {player.username} won with correct accusation: {accusation}")
        else:
            # Incorrect accusation: Eliminate player from further participation in the game"
            player.is_active = False
            await database_sync_to_async(player.save)()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_out',
                    'player': player.username,
                    'reason': 'incorrect_accusation'  # Client notification: send reason only for incorrect accusation
                }
            )
            await self.send(text_data=json.dumps({'message': 'Your accusation was incorrect. You are out of the game but can still disprove suggestions.'}))
            print(f"Player {player.username} eliminated with incorrect accusation: {accusation}")

            # Broadcast updated game state
            game_state = await self.get_game_state()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_update',
                    'game_state': game_state
                }
            )


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