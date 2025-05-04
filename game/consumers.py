"""
WebSocket consumer for the Clue-Less game, handling real-time interactions.

This module defines the GameConsumer, an AsyncWebsocketConsumer that manages
WebSocket connections for the multiplayer game. It handles connection establishment,
disconnection, message processing, and game state updates, supporting features like
dynamic player updates, game start, moves, suggestions, and accusations. The consumer
validates sessions using cookies, ensures authenticated users via Channels middleware,
and broadcasts game state changes to clients, integrating with fixes for session
overwrites, AttributeError at /login/, and lobby functionality (dynamic updates, start
button, reload fixes).

Key features:
- Validates session cookies (sessionid, clueless_*) to ensure session integrity.
- Uses Channels middleware (SessionMiddlewareStack, AuthMiddlewareStack) for
  authentication, ensuring self.scope['user'] is set correctly.
- Broadcasts player_joined and game_started events for real-time lobby updates.
- Manages game logic with turn restrictions and card distribution.
- Supports debugging with detailed logging when DEBUG is enabled.

For more information, see:
- https://channels.readthedocs.io/en/stable/topics/consumers.html
- https://channels.readthedocs.io/en/stable/topics/authentication.html
- https://docs.djangoproject.com/en/5.1/topics/http/sessions/
"""

# Standard library imports for JSON parsing and async operations
import asyncio
import random
import json

# Django imports for database access and session management
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.sessions.models import Session
from django.contrib.sessions.backends.db import SessionStore

# Local imports for game models and constants
from .models import *
from .constants import *

# Debug flags for logging; disable in production to reduce verbosity
# When enabled, logs session details, game state, and action events for debugging
# Set to False in production for performance and security
DEBUG = True  # Enables/disables all logging
DEBUG_AUTH = True  # Authentication-specific debug logging
DEBUG_GAME_UPDATE = True  # Game state update logging
DEBUG_HANDLE_ACCUSE = True  # Accusation event logging
HANDLE_END_TURN = True  # End turn event logging

class GameConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time game interactions in Clue-Less.

    Handles WebSocket connections, validates sessions, manages game state, and processes
    player actions (e.g., moves, accusations). Ensures authenticated users via
    self.scope['user'] (set by AuthMiddlewareStack) and validates session cookies to
    prevent unauthorized access. Broadcasts events like player_joined and game_started
    to support lobby features (dynamic updates, start button). Integrates with
    SessionValidationMiddleware for session isolation, addressing session overwrite
    issues in private browsing modes (e.g., Safari).
    """
    # Mapping of player usernames to their WebSocket channel names
    player_channel_map = {}
    
    async def connect(self):
        """
        Handle WebSocket connection establishment.

        Validates the session using the sessionid cookie, retrieves user data, joins the
        game group, sends the initial game state, and broadcasts a player_joined event.
        Closes the connection if session validation fails, ensuring security.

        - **Authentication**: Uses self.scope['user'] set by AuthMiddlewareStack in
          asgi.py to identify the authenticated user. Ensures only authenticated users
          connect, aligning with views.py authentication checks.
        - **Session Handling**: Retrieves the sessionid cookie and validates it against
          the django_session table. Loads session data to check for expected_username,
          mirroring SessionValidationMiddleware’s logic to prevent session overwrites.
          Stores session_data in self.scope['session'] for use in other methods.
        - **Error Handling**: Closes the connection (code 4001) if the sessionid is
          missing, invalid, or lacks expected_username, preventing unauthorized access.
        - **Debugging**: Logs cookie details and session validation status when
          DEBUG_AUTH is enabled, aiding diagnosis of WebSocket connection issues.
        """
        # Log connection attempt for debugging
        print("Connecting to WebSocket...")
        # Extract game_id from URL route (e.g., /ws/game/<game_id>/)
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        print(f"Game ID set to: {self.game_id}")
        # Define group name for broadcasting messages to game participants
        self.game_group_name = f"game_{self.game_id}"

        # Retrieve cookies from the WebSocket scope
        cookies = self.scope.get('cookies', {})
        session_key = cookies.get('sessionid')

        # Log cookie details for debugging session issues
        if DEBUG and DEBUG_AUTH:
            print("[connect] Cookie details:")
            print(f"  sessionid: {session_key or 'None'}")
            for key in cookies:
                if key.startswith('clueless_'):
                    print(f"  {key}: {cookies[key]}")

        # Validate presence of sessionid cookie
        if not session_key:
            if DEBUG and DEBUG_AUTH:
                print("[connect] No sessionid cookie found")
            await self.close(code=4001, reason="Missing session cookie")
            return

        # Check if session exists in the database
        session_exists = await database_sync_to_async(Session.objects.filter(session_key=session_key).exists)()
        if not session_exists:
            if DEBUG and DEBUG_AUTH:
                print("[connect] Session not found in database:")
                print(f"  Session key: {session_key}")
            await self.close(code=4001, reason="Invalid session")
            return

        # Load session data
        try:
            session_data = await database_sync_to_async(self.load_session)(session_key)
        except Exception as e:
            if DEBUG and DEBUG_AUTH:
                print("[connect] Failed to load session:")
                print(f"  Session key: {session_key}")
                print(f"  Error: {str(e)}")
            await self.close(code=4001, reason="Failed to load session")
            return

        # Ensure session contains expected_username
        if not session_data.get('expected_username'):
            if DEBUG and DEBUG_AUTH:
                print("[connect] Session lacks expected_username:")
                print(f"  Session key: {session_key}")
            await self.close(code=4001, reason="Invalid session data")
            return

        # Store session data in scope for use in other methods
        self.scope['session'] = session_data

        # Log successful validation for debugging
        if DEBUG and DEBUG_AUTH:
            print("[connect] Session validated successfully:")
            print(f"  Session key: {session_key}")
            print(f"  User: {self.scope['user'].username if self.scope['user'].is_authenticated else 'Anonymous'}")

        # Add client to game group for broadcasting
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        # Accept the WebSocket connection
        await self.accept()
        print(f"WebSocket connected for game {self.game_id}, channel: {self.channel_name}")
        
        # Add the player's username and channel_name to the mapping
        username = self.scope['user'].username
        GameConsumer.player_channel_map[username] = self.channel_name

        # Send initial game state to the client
        game_state = await self.get_game_state()
        await self._send_game_update(game_state, source="connect")

        # Broadcast player_joined event to update lobby
        game = await self.get_game()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'player_joined',
                'player': self.scope['user'].username,
                'players': game.players_list,
                'player_count': len(game.players_list)
            }
        )

    def load_session(self, session_key):
        """
        Load session data from the database synchronously.

        Retrieves and decodes session data for the given session_key, used in connect()
        to validate the session. Logs loading status for debugging.

        Returns:
            dict: Decoded session data containing expected_username and other fields.
        Raises:
            Session.DoesNotExist: If the session_key is invalid.
        """
        try:
            session = Session.objects.get(session_key=session_key)
            decoded_session = session.get_decoded()
            if DEBUG:
                print("[load_session] Session loaded:")
                print(f"  Session key: {session_key}")
                print(f"  Expected username: {decoded_session.get('expected_username', 'None')}")
            return decoded_session
        except Session.DoesNotExist:
            if DEBUG:
                print("[load_session] Session not found:")
                print(f"  Session key: {session_key}")
            raise

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.

        Removes the client from the game group and deactivates the player if the game
        is active, broadcasting a player_out event to update clients.

        - **Authentication**: Uses self.scope['user'].username to identify the player
          for deactivation, relying on AuthMiddlewareStack to set the user.
        - **Session Handling**: No direct session manipulation, but deactivation updates
          the player's state, which is reflected in game state broadcasts.
        """
        # Remove the player's username from the mapping on disconnect
        username = self.scope['user'].username
        if username in GameConsumer.player_channel_map:
            del GameConsumer.player_channel_map[username]
            
        if hasattr(self, 'game_group_name'):
            try:
                game = await self.get_game()
                # Remove client from game group
                await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
                # Only send player_out if game is active and not in DEBUG mode after start
                if game.is_active and not (DEBUG and game.begun):
                    player = await self.get_player(self.scope['user'].username)
                    if player.is_active:
                        player.is_active = False
                        await database_sync_to_async(player.save)()
                    if DEBUG:
                        print("[disconnect] Sending player_out:")
                        print(f"  Player: {player.username}")
                        print(f"  Game ID: {self.game_id}")
                        print(f"  Channel: {self.channel_name}")
                    # Broadcast player_out event
                    await self.channel_layer.group_send(
                        self.game_group_name,
                        {
                            'type': 'player_out',
                            'player': player.username,
                            'username': player.username,
                            'channel_name': self.channel_name
                        }
                    )
                else:
                    if DEBUG:
                        print("[disconnect] Skipping player_out:")
                        print(f"  Game ID: {self.game_id}")
                        print(f"  Active: {game.is_active}")
                        print(f"  Begun: {game.begun}")
                        print(f"  Channel: {self.channel_name}")
                print(f"WebSocket disconnected for game {self.game_id}, channel: {self.channel_name}")
            except (Game.DoesNotExist, Player.DoesNotExist):
                print(f"[disconnect] Game or player not found for game {self.game_id}, channel: {self.channel_name}")

    async def receive(self, text_data):
        """
        Process incoming WebSocket messages.

        Parses JSON messages and dispatches to handlers for start_game, move, suggest,
        accuse, end_turn, and player_out. Logs messages for debugging and handles errors
        gracefully.
        """
        if not hasattr(self, 'game_group_name') or not hasattr(self, 'channel_name'):
            if DEBUG:
                print(f"Ignoring message due to uninitialized consumer: {text_data}")
            return
        if DEBUG:
            print(f"Received WebSocket message: {text_data}, channel: {self.channel_name}")
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            if DEBUG:
                print(f"Invalid JSON message: {text_data}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid message format.'
            }))
            return

        message_type = data.get('type')
        if not message_type:
            if DEBUG:
                print(f"No message type in data: {data}")
            return
        
        # Skip turn validation for card_selected messages
        if message_type == 'card_selected':
            await self.handle_card_selected(data)
            return
        
        if message_type == 'start_game':
            await self.handle_start_game()
        elif message_type == 'move':
            await self.handle_move(data)
        elif message_type == 'suggest':
            await self.handle_suggest(data)
        elif message_type == 'accuse':
            await self.handle_accuse(data)
        elif message_type == 'end_turn':
            # Capture the return values from handle_end_turn
            turn_info = await self.handle_end_turn(data)  # Handle end_turn request
            
            if turn_info is None:
                # If a player clicks when not their turn
                return
            
            # Extract the current and next player's characters
            current_player_character = turn_info.get('current_player_character')
            next_player_character = turn_info.get('next_player_character')

            # Broadcast the end turn message to all players
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_action',
                    'message': f"{current_player_character} has ended their turn!\n\nIt is now {next_player_character}'s turn."
                }
            )
        else:
            if DEBUG:
                print(f"No handler for message type {message_type}: {data}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Unknown message type: {message_type}",
                'raw_message': data
            }))

    async def player_joined(self, event):
        """
        Handle player_joined events to notify clients of new players.

        Sends a player_joined message with the player list and count, enabling dynamic
        lobby updates in start_game.html (fixes lack of automatic player updates).
        """
        await self.send(text_data=json.dumps({
            'type': 'player_joined',
            'player': event['player'],
            'players': event['players'],
            'player_count': event['player_count']
        }))

    async def handle_start_game(self):
        """
        Handle start_game message to initialize the game.

        Ensures only the host (first player) can start with at least 3 players,
        addressing the unclickable start button issue in start_game.html. Broadcasts
        game_started event to redirect clients to the game page.

        - **Authentication**: Uses self.scope['user'].username to verify the host,
          relying on AuthMiddlewareStack for user authentication.
        """
        game = await self.get_game()
        if self.scope['user'].username != game.players_list[0]:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Only the host can start the game.'
            }))
            return
        if len(game.players_list) < 2:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'At least 2 players are required to start the game.'
            }))
            return
        await self.initialize_game(game)
        game.begun = True
        await database_sync_to_async(game.save)()
        await self.channel_layer.group_send(
            self.game_group_name,
            {'type': 'game_started'}
        )
    
    async def game_started(self, event):
        """Notify clients that the game has started, triggering redirect to game page."""
        await self.send(text_data=json.dumps({
            'type': 'game_started'
        }))

    async def initialize_game(self, game):
        """
        Initialize game state by setting case file and distributing cards.

        Sets the first player's turn (Miss Scarlet or first in players_list) and saves
        the game state.
        """
        case_suspect = random.choice(SUSPECTS)
        case_weapon = random.choice(WEAPONS)
        case_room = random.choice(ROOMS)
        game.case_file = {'suspect': case_suspect, 'weapon': case_weapon, 'room': case_room}
        print(f"Case file set: {game.case_file}")
        players = await database_sync_to_async(list)(game.players.all())
        miss_scarlet_player = next((player for player in players if player.character == "Miss Scarlet"), None)
        if miss_scarlet_player:
            miss_scarlet_player.turn = True
            await database_sync_to_async(miss_scarlet_player.save)()
        else:
            first_player_username = game.players_list[0]
            first_player = next(player for player in players if player.username == first_player_username)
            first_player.turn = True
            await database_sync_to_async(first_player.save)()
        await self.generate_hands(game, players)
        await database_sync_to_async(game.save)()

    async def generate_hands(self, game, players):
        """
        Distribute cards to players' hands, starting with the player whose turn is True.

        Excludes case file cards, shuffles remaining cards, and assigns them to players.
        """
        combined_list = SUSPECTS + WEAPONS + ROOMS
        remaining_cards = [item for item in combined_list if item not in game.case_file.values()]
        shuffled_cards = remaining_cards[:]
        random.shuffle(shuffled_cards)
        character_in_play = [player.character for player in players if player.character is not None]
        if len(character_in_play) == 0:
            raise ValueError("Please select characters before starting the game.")
        starting_player = next((player.character for player in players if player.turn), None)
        if not starting_player:
            raise ValueError("No starting player found. Ensure a player has their turn set to True.")
        hands = {character: [] for character in character_in_play}
        player_list = character_in_play
        starting_index = player_list.index(starting_player)
        current_player_index = starting_index
        while shuffled_cards:
            hands[player_list[current_player_index]].append(shuffled_cards.pop(0))
            current_player_index = (current_player_index + 1) % len(player_list)
        for player in players:
            if player.character in hands:
                player.hand = hands[player.character]
                await database_sync_to_async(player.save)()
    
    async def broadcast_suggestion_result(self, event):
        await self.send(text_data=json.dumps({
            'type': 'suggestion_result',
            'suggesting_player': event['suggesting_player'],
            'suspect': event['suspect'],
            'weapon': event['weapon'],
            'room': event['room'],
            'refuting_player': event.get('refuting_player')
        }))
                    
    async def game_update(self, event):
        """
        Handle game_update events broadcast to the group.

        Sends updated game state to clients, logging details for debugging.
        """
        game_state = event.get('game_state', {})
        source = event.get('source', 'unknown')
        if DEBUG and DEBUG_GAME_UPDATE:
            print(f"Received game_update event for game {self.game_id} (source: {source})")
            players = game_state.get('players', [])
            for player in players:
                print(
                    f"  - Username: {player.get('username', 'Unknown')}, "
                    f"Character: {player.get('character', 'None')}, Location: {player.get('location', 'None')}, "
                    f"Is Active: {player.get('is_active', 'Unknown')}, Accused: {player.get('accused', 'Unknown')}")
            game_id = game_state.get('game_id', 'Unknown')
            case_file = game_state.get('case_file', 'Not set')
            print(f"Case file for game {game_id}: {case_file}\n")
        await self.send(text_data=json.dumps({
            'type': 'game_update',
            'game_state': game_state
        }))

    async def player_action(self, event):
        # Send the action message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'popup',
            'message': event['message']
        }))
        
    async def select_card(self, event):
        await self.send(text_data=json.dumps({
            'type': 'select_card',
            'message': event['message'],
            'matchList': event['matchList'],
            'suggesting_player_channel': event['suggesting_player_channel']
        }))

    # Async wrapper for synchronous database query to get Game instance
    async def _send_game_update(self, game_state, source):
        """
        Helper method to send game_update with source tracking.

        Broadcasts game state to all clients in the game group, logging for debugging.
        """
        if DEBUG:
            print(f"Sending game_update for game {self.game_id} (source: {source})")
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state,
                'source': source
            }
        )

    @database_sync_to_async
    def get_game(self):
        """Fetch Game instance from the database."""
        return Game.objects.get(id=self.game_id)

    @database_sync_to_async
    def get_player(self, username):
        """Fetch Player instance from the database."""
        game = Game.objects.get(id=self.game_id)
        return Player.objects.get(game=game, username=username)

    async def handle_move(self, data):
        """
        Handle a player's move request with turn restriction.

        Validates move adjacency and hallway occupancy, updating player location and
        broadcasting game state.

        - **Authentication**: Uses self.scope['user'].username to identify the player,
          ensuring only authenticated users can move.
        """
        game = await self.get_game()
        player = await self.get_player(self.scope['user'].username)
        # When only one player is left, the player takes turn continuously
        players = await database_sync_to_async(list)(Player.objects.filter(game=game))
        non_eliminated_players = [p for p in players if not p.accused]
        if player.moved and len(non_eliminated_players) != 1:
            await self.send(text_data=json.dumps({'error': 'You have already moved once this turn'}))
            return
        to_location = data.get('location')
        if not to_location:
            await self.send(text_data=json.dumps({'error': 'No location provided'}))
            return
        from_location = player.location
        print(f"Player {player.username} holds: {player.hand}")
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'It is not your turn'}))
            return
        if to_location == from_location:
            await self.send(text_data=json.dumps({'error': f'You are already at {to_location}'}))
            return
        valid_moves = ADJACENCY.get(from_location, [])
        if to_location in valid_moves:
            players = await database_sync_to_async(list)(Player.objects.filter(game=game))
            for p in players:
                if p.location in HALLWAYS and p.location == to_location and p.username != player.username:
                    await self.send(text_data=json.dumps({'error': f'Cannot move to {to_location}, it is occupied by {p.username}'}))
                    return
        if to_location not in valid_moves:
            await self.send(text_data=json.dumps({'error': f'Invalid move: {to_location} is not adjacent to {from_location}'}))
            return
        player.location = to_location
        player.moved = True
        await database_sync_to_async(player.save)()
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )
        # Broadcast the move action to all players
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'player_action',
                'message': f"{player.character} has moved from {from_location} into the {to_location}"
            }
        )

    async def handle_accuse(self, data):
        """
        Handle player's accusation with turn enforcement.

        Compares accusation to case file, updates player status, and broadcasts game
        end or elimination events.

        - **Authentication**: Uses self.scope['user'].username to identify the player,
          ensuring only authenticated users can accuse.
        """
        try:
            game = await self.get_game()
            player = await self.get_player(self.scope['user'].username)
        except (Game.DoesNotExist, Player.DoesNotExist):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Game or player not found.'
            }))
            return
        if not game.is_active:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'The game is currently paused or has ended.'
            }))
            return
        if not player.is_active:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You are no longer active in the game.'
            }))
            return
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'It is not your turn'}))
            return
        if player.accused:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You have already made an accusation and cannot accuse again.'
            }))
            return
        if isinstance(data, str):
            data = json.loads(data)
        suspect = data.get('suspect')
        weapon = data.get('weapon')
        room = data.get('room')
        if not all([suspect, weapon, room]):
            await self.send(text_data=json.dumps({'error': 'Missing accusation details (suspect, weapon or room)'}))
            return

        # Compare accusation to case file
        if suspect not in SUSPECTS or weapon not in WEAPONS or room not in ROOMS:
            await self.send(text_data=json.dumps({'error': 'Invalid accusation: one or more selections are not valid'}))
            return
        
        # Broadcast accusation to all players
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'player_action',
                'message': f"{player.character} has accused {suspect}, {weapon}, and {room}!"
            }
        )

        accusation = {'suspect': suspect, 'weapon': weapon, 'room': room}
        if DEBUG and DEBUG_HANDLE_ACCUSE:
            print(f"Player {player.username} accuses: {accusation}")
        player.accused = True
        await database_sync_to_async(player.save)()
        if accusation == game.case_file:
            game.is_active = True if DEBUG else False
            await database_sync_to_async(game.save)()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_end',
                    'winner': player.username,
                    'solution': game.case_file,
                    'message': f"{player.username} won with the correct accusation!"
                }
            )
            # Broadcast the move action to all players and add to log history
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_action',
                    'message': f"{player.username} won with the correct accusation!"
                }
            )
            if DEBUG and DEBUG_HANDLE_ACCUSE:
                print(f"Player {player.username} won with correct accusation: {accusation}\n")
        else:
            await self.send(text_data=json.dumps({
                'type': 'accusation_failed',
                'message': 'Your accusation was incorrect. You are no longer able to move or make accusations but remain a suspect.'
            }))
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'accusation_result',
                    'accusing_player': player.username,
                    'suspect': suspect,
                    'weapon': weapon,
                    'room': room,
                    'is_correct': False
                }
            )
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_eliminated',
                    'player': player.username,
                    'message': f"{player.username} has been eliminated due to an incorrect accusation."
                }
            )
            # Broadcast the move action to all players
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_action',
                    'message': f"{player.username} has been eliminated due to an incorrect accusation."
                }
            )
            if DEBUG and DEBUG_HANDLE_ACCUSE:
                print(f"Player {player.username} eliminated with incorrect accusation: {accusation}")
            await self.handle_end_turn({})
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )
    async def accusation_result(self, event):
        await self.send(text_data=json.dumps({
            'type': 'accusation_result',
            'accusing_player': event['accusing_player'],
            'suspect': event['suspect'],
            'weapon': event['weapon'],
            'room': event['room'],
            'is_correct': event['is_correct']
        }))

    async def game_end(self, event):
        """Notify clients of game end with winner and solution."""
        await self.send(text_data=json.dumps({
            'type': 'game_end',
            'winner': event['winner'],
            'solution': event['solution'],
            'message': event.get('message', f"Game over! {event['winner']} won!")
        }))

    async def player_eliminated(self, event):
        """Notify clients of a player's elimination."""
        await self.send(text_data=json.dumps({
            'type': 'player_eliminated',
            'player': event['player'],
            'message': event['message']
        }))

    async def handle_suggest(self, data):
        """
        Handle a player's suggestion with turn restriction.

        Moves suspect to the suggested room, checks players' hands for cards, and
        broadcasts game state updates.

        - **Authentication**: Uses self.scope['user'].username to identify the player,
          ensuring only authenticated users can suggest.
        """
        game = await self.get_game()
        player = await self.get_player(self.scope['user'].username)
        players = await database_sync_to_async(list)(Player.objects.filter(game=game))
        
        # Get the channel_name of the suggesting player
        suggesting_player_channel = GameConsumer.player_channel_map.get(player.username)
        
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'It is not your turn'}))
            return
        if not player.moved and not player.suggested:
            await self.send(text_data=json.dumps({'error': 'You must move before making a suggestion unless you were moved to the room'}))
            return
        if player.accused:
            await self.send(text_data=json.dumps({'error': 'Eliminated players cannot make suggestions'}))
            return
        if player.location not in ROOMS:
            print(f"player's location is: {player.location}")
            await self.send(text_data=json.dumps({'error': f'You must be in a room to make a suggestion'}))
            return
        suspect = data.get('suspect')
        weapon = data.get('weapon')
        room = data.get('room')
        if not all([suspect, weapon, room]):
            await self.send(text_data=json.dumps({'error': 'Incomplete suggestion (suspect, weapon, or room missing)'}))
            return
        
        # Broadcast suggestion to all players
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'player_action',
                'message': f"{player.character} has suggested {suspect}, {weapon}, and {room}"
            }
        )
    
        # make list of players in order of checking suggestion with players' card hands
        # start with suggested player
        # then follow turn order
        playerCopyList = players.copy()
        playerSuggestList = []
    
        suspect_player = None
        for p in players:
            if p.character == suspect:
                suspect_player = p
        
        if suspect_player is not None:
            # move suspected player to suggested room
            suspect_player.location = player.location
            suspect_player.suggested = True
            await database_sync_to_async(suspect_player.save)()  # Save changes asynchronously
            
            # Broadcast updated game state
            game_state = await self.get_game_state()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_update',
                    'game_state': game_state
                }
            )
            
            playerSuggestList = [suspect_player]
            playerCopyList.remove(suspect_player)
            playerCopyList.remove(player)
            playerSuggestList.extend(playerCopyList)
        else:
            playerCopyList.remove(player)
            playerSuggestList.extend(playerCopyList)
            

        # check suspected player's hand for suspect, then weapon, then room
        # put all matches into separate list
        # if 0 cards match - move to next player and repeat process
        # if 1 card matches - state that card disproves the suggestion
        # if more than 1 card matches - ask suspected player which card to disprove suggestion with

        for plyr in playerSuggestList:
            currHand = plyr.hand
            matchList = []
            suspectMatch = [card for card in currHand if card==suspect]
            roomMatch = [card for card in currHand if card==room]
            weaponMatch = [card for card in currHand if card==weapon]
            matchList.extend(suspectMatch)
            matchList.extend(roomMatch)
            matchList.extend(weaponMatch)
            print(f"Disproving player: {plyr.username} as {plyr.character}")
            print(f"Disproving player's card hand: {plyr.hand}")
            print(f"List of matching cards: {matchList}") #test which cards match
            numMatches = len(matchList)
            
            if numMatches == 1:
                await self.channel_layer.send(
                    suggesting_player_channel,
                    {
                        'type': 'player_action',
                        'message': f'Card {matchList} disproves suggestion. End of turn'
                    }
                )
                await self.handle_end_turn(data)
                break
            elif numMatches > 1:
                disproving_player_channel = GameConsumer.player_channel_map.get(plyr.username)
                if disproving_player_channel:
                    # Prompt player to select which card to disprove suggestion with
                    await self.channel_layer.send(
                        disproving_player_channel,
                        {
                            'type': 'select_card',
                            'message': f'You have multiple cards to disprove the suggestion:',
                            'matchList': matchList,
                            'suggesting_player_channel': suggesting_player_channel
                        }
                    )
                break
            else:
                # Broadcast the results of your suggestion to all players
                await self.channel_layer.group_send(
                    self.game_group_name,
                    {
                        'type': 'player_action',
                        'message': f"None of the other players could disprove your suggestion."
                    }
                )
                
                    
        # Broadcast updated game state
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'broadcast_suggestion_result',
                'suggesting_player': player.username,
                'suspect': suspect,
                'weapon': weapon,
                'room': room,
                'refuting_player': p.username if 'p' in locals() and suspect in p.hand or weapon in p.hand or room in p.hand else None
            }
        )

    async def handle_card_selected(self, data):
        """
        Handle the card selected by the disproving player and send it to the suggesting player.
        """
        selected_card = data.get('card')
        suggesting_player_channel = data.get('suggesting_player_channel')  # Get the suggesting player's channel

        if not selected_card or not suggesting_player_channel:
            return

        # Send the selected card only to the suggesting player
        await self.channel_layer.send(
            suggesting_player_channel,
            {
                'type': 'player_action',
                'message': f"The card [{selected_card}] has been shown to disprove your suggestion."
            }
        )

    async def handle_end_turn(self, data):
        """
        Handle end of turn for the current player.

        Advances turn to the next non-eliminated player, updating game state and
        broadcasting changes.

        - **Authentication**: Uses self.scope['user'].username to identify the player,
          ensuring only authenticated users can end their turn.
        """
        game = await self.get_game()
        player = await self.get_player(self.scope['user'].username)
        players = await database_sync_to_async(list)(Player.objects.filter(game=game))
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'It is not your turn'}))
            return
        if not player.moved and not player.accused:
            await self.send(text_data=json.dumps({'error': 'You must move before ending your turn'}))
            return
        non_eliminated_players = [p for p in players if not p.accused]
        if DEBUG and HANDLE_END_TURN:
            print(f"Non-eliminated players: {[p.username for p in non_eliminated_players]}")
        if len(non_eliminated_players) == 0:
            game.is_active = False
            await database_sync_to_async(game.save)()
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'game_tie',
                    'message': 'Game over! All players have been eliminated, resulting in a tie.'
                }
            )
            if DEBUG:
                print(f"Game {self.game_id} ended in a tie: no non-eliminated players remain.")
            return
        player.moved = False
        player.turn = False
        await database_sync_to_async(player.save)()
        if len(non_eliminated_players) == 1:
            next_player = non_eliminated_players[0]
            if DEBUG:
                print(f"Single non-eliminated player: {next_player.username}, assigning turn")
            next_player.turn = True
            await database_sync_to_async(next_player.save)()
        else:
            try:
                player_index = players.index(player)
            except ValueError:
                player_index = None
            if player_index is not None:
                total_players = len(players)
                for i in range(1, total_players):
                    next_index = (player_index + i) % total_players
                    next_player = players[next_index]
                    if not next_player.accused:
                        if DEBUG:
                            print(f"Assigning turn to next non-eliminated player: {next_player.username}")
                        next_player.turn = True
                        await database_sync_to_async(next_player.save)()
                        break
                else:
                    game.is_active = False
                    await database_sync_to_async(game.save)()
                    await self.channel_layer.group_send(
                        self.game_group_name,
                        {
                            'type': 'game_tie',
                            'message': 'Game over! All players have been eliminated, resulting in a tie.'
                        }
                    )
                    if DEBUG:
                        print(f"Game {self.game_id} ended in a tie: no non-eliminated players available for turn.")
                    return
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )

        # Return the characters of the current and next players
        return {
            'current_player_character': player.character,
            'next_player_character': next_player.character
        }

    async def game_tie(self, event):
        """Notify clients that the game has ended in a tie."""
        await self.send(text_data=json.dumps({
            'type': 'game_tie',
            'message': event.get('message', 'Game over! All players have been eliminated, resulting in a tie.')
        }))

    async def handle_player_out(self, data):
        """
        Handle player_out messages to deactivate players.

        Updates player status and broadcasts game state, ensuring clients reflect
        player disconnections.

        - **Authentication**: Uses username from the message to identify the player,
          ensuring only valid players are deactivated.
        """
        username = data.get('username')
        if not username:
            if DEBUG and DEBUG_AUTH:
                print(f"[handle_player_out] No username provided in player_out message for game {self.game_id}: {data}, "
                      f"channel: {self.channel_name}")
            return
        if DEBUG:
            print(f"Processing player_out for username {username} in game {self.game_id}, channel: {self.channel_name}")
        try:
            game = await self.get_game()
            if game.is_active:
                player = await self.get_player(username)
                if player.is_active:
                    player.is_active = False
                    await database_sync_to_async(player.save)()
                if DEBUG and DEBUG_AUTH:
                    print(f"Player {username} marked as inactive in game {self.game_id}")
                game_state = await self.get_game_state()
                await self._send_game_update(game_state, source="handle_player_out")
        except (Game.DoesNotExist, Player.DoesNotExist):
            if DEBUG and DEBUG_AUTH:
                print(f"Player {username} or game {self.game_id} not found in handle_player_out: {data}")

    @database_sync_to_async
    def get_game_state(self):
        """
        Fetch game state for WebSocket updates.

        Retrieves game data, including players, case file, and constants, handling
        missing games gracefully.
        """
        try:
            game = Game.objects.get(id=self.game_id)
            fields = [f.name for f in Player._meta.fields]
            players = list(game.players.values(*fields))
            return {
                'game_id': self.game_id,
                'case_file': game.case_file or {},
                'game_is_active': game.is_active,
                'players': players,
                'rooms': ROOMS,
                'hallways': HALLWAYS,
                'weapons': WEAPONS,
            }
        except Game.DoesNotExist:
            if DEBUG:
                print(f"Game {self.game_id} not found in get_game_state")
            return {
                'game_id': self.game_id,
                'case_file': {},
                'game_is_active': False,
                'players': [],
                'rooms': ROOMS,
                'hallways': HALLWAYS,
                'weapons': WEAPONS,
            }