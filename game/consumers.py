from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import random
import asyncio
from .models import *
from .constants import *

# For debugging purpose, disable in production
DEBUG = True  # Debug flag to enable/disable all logging
# Debugging Flag Conventions: DEBUG_<feature> or DEBUG_<method_name>
DEBUG_AUTH = False  # Authentication-specific debug logging
DEBUG_GAME_UPDATE = True
DEBUG_HANDLE_ACCUSE = True  # <method> based


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Establish WebSocket connection and join game group."""
        print("Connecting to WebSocket...")
        # Extract game_id from the WebSocket URL (e.g., /ws/game/1/)
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        print(f"Game ID set to: {self.game_id}")
        self.game_group_name = f"game_{self.game_id}"
        # Delay to avoid rapid reconnects
        await asyncio.sleep(0.2)
        await self.channel_layer.group_add(self.game_group_name, self.channel_name)
        await self.accept()
        print(f"WebSocket connected for game {self.game_id}, channel: {self.channel_name}")

        # Retry session loading if empty
        session_key = None
        for _ in range(3):  # Retry up to 3 times
            session_key = self.scope.get('session', {}).get('session_key')
            if session_key:
                break
            if DEBUG and DEBUG_AUTH:
                print(f"Session retry: self.scope['session'] = {self.scope.get('session', 'None')}")
            await asyncio.sleep(0.1)  # Wait 0.1s before retry
        if DEBUG and DEBUG_AUTH:
            print(f"Session key: {session_key or 'None'}")
            print(f"User: {self.scope['user'].username if self.scope['user'].is_authenticated else 'Anonymous'}")
            cookies = self.scope.get('cookies', {})
            print(f"Cookies: sessionid={cookies.get('sessionid', 'None')}, "
                  f"sessionid_{session_key or 'None'}={cookies.get(f'sessionid_{session_key}', 'None')}, "
                  f"clueless_session_{session_key or 'None'}={cookies.get(f'clueless_session_{session_key}', 'None')}")
        game_state = await self.get_game_state()
        await self._send_game_update(game_state, source="connect")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection and remove client from group."""
        if hasattr(self, 'game_group_name'):
            try:
                game = await self.get_game()
                await self.channel_layer.group_discard(self.game_group_name, self.channel_name)
                # Only send player_out if game is active and not in DEBUG mode after game end
                if game.is_active and not (DEBUG and game.begun):
                    player = await self.get_player(self.scope['user'].username)
                    if player.is_active:
                        player.is_active = False
                        await database_sync_to_async(player.save)()
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
                        print(
                            f"Skipping player_out for game {self.game_id} (active: {game.is_active}, begun: {game.begun}), channel: {self.channel_name}")
                print(f"WebSocket disconnected for game {self.game_id}, channel: {self.channel_name}")
            except (Game.DoesNotExist, Player.DoesNotExist):
                print(
                    f"Game or player not found during disconnect for game {self.game_id}, channel: {self.channel_name}")

    async def receive(self, text_data):
        """Process incoming WebSocket messages."""
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
        if message_type == 'start_game':
            await self.handle_start_game()
        elif message_type == 'move':
            await self.handle_move(data)  # Handle player move request
        elif message_type == 'suggest':
            await self.handle_suggest(data)  # Placeholder for suggestion logic
        elif message_type == 'accuse':
            await self.handle_accuse(data)
        elif message_type == 'end_turn':
            await self.handle_end_turn(data)  # Handle end_turn request
        elif message_type == 'player_out':
            await self.handle_player_out(data)  # Handle player_out messages triggered on reload
        else:
            if DEBUG:
                print(f"No handler for message type {message_type}: {data}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Unknown message type: {message_type}",
                'raw_message': data  # Include raw message for debugging
            }))


    async def handle_start_game(self):
        game = await self.get_game()

        # Verify sender is first player
        if self.scope['user'].username != game.players_list[0]:
            return

        # Initialize case file and distribute cards
        await self.initialize_game(game)

        # Mark game as started
        game.begun = True
        await database_sync_to_async(game.save)()

        # Notify all clients that game has started
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_started'
            }
        )

    async def game_started(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_started'
        }))

    async def initialize_game(self, game):
        # Randomly select case file cards
        case_suspect = random.choice(SUSPECTS)
        case_weapon = random.choice(WEAPONS)
        case_room = random.choice(ROOMS)
        # Set case file
        game.case_file = {
            'suspect': case_suspect,
            'weapon': case_weapon,
            'room': case_room
        }
        print(f"Case file set: {game.case_file}")

        # Get all players
        players = await database_sync_to_async(list)(game.players.all())

        # Check if Miss Scarlet is in the game
        miss_scarlet_player = next((player for player in players if player.character == "Miss Scarlet"), None)
        if miss_scarlet_player:
            miss_scarlet_player.turn = True
            await database_sync_to_async(miss_scarlet_player.save)()
        else:
            # If Miss Scarlet is not present, set turn to True for the first player in players_list
            first_player_username = game.players_list[0]
            first_player = next(player for player in players if player.username == first_player_username)
            first_player.turn = True
            await database_sync_to_async(first_player.save)()

        # Generate hands for each player
        await self.generate_hands(game, players)

        # Save the game state
        await database_sync_to_async(game.save)()

    async def generate_hands(self, game, players):
        # Combined list of suspects, weapons, and rooms
        combined_list = SUSPECTS + WEAPONS + ROOMS

        # Exclude the case file cards
        remaining_cards = [item for item in combined_list if item not in game.case_file.values()]

        # Shuffle the remaining cards
        shuffled_cards = remaining_cards[:]
        random.shuffle(shuffled_cards)

        # Find the characters who have been assigned to players
        character_in_play = [player.character for player in players if player.character is not None]

        if len(character_in_play) == 0:
            raise ValueError("Please select characters before starting the game.")

        # Find the player whose turn is True
        starting_player = next((player.character for player in players if player.turn), None)
        if not starting_player:
            raise ValueError("No starting player found. Ensure a player has their turn set to True.")

        # Create an empty hand for each player in play
        hands = {character: [] for character in character_in_play}

        # List of players in play
        player_list = character_in_play

        # Start dealing from the player with turn=True
        starting_index = player_list.index(starting_player)

        # Distribute cards round-robin starting with the correct player
        current_player_index = starting_index
        while shuffled_cards:
            hands[player_list[current_player_index]].append(shuffled_cards.pop(0))
            current_player_index = (current_player_index + 1) % len(player_list)

        # Update player hands with the distributed cards
        for player in players:
            if player.character in hands:
                player.hand = hands[player.character]
                await database_sync_to_async(player.save)()

    async def game_update(self, event):
        """Handle game_update events broadcast to the group."""
        game_state = event.get('game_state', {})
        source = event.get('source', 'unknown')
        if DEBUG and DEBUG_GAME_UPDATE:
            print(f"Received game_update event for game {self.game_id} (source: {source})")
            # print(f"Full game_state: {game_state}")
            players = game_state.get('players', [])
            for player in players:
                print(
                    f"  - Username: {player.get('username', 'Unknown')}, Character: {player.get('character', 'None')}, Location: {player.get('location', 'None')}, Is Active: {player.get('is_active', 'Unknown')}")
            game_id = game_state.get('game_id', 'Unknown')
            case_file = game_state.get('case_file', 'Not set')
            print(f"Case file for game {game_id}: {case_file}\n")

        await self.send(text_data=json.dumps({
            'type': 'game_update',
            'game_state': game_state
        }))

    async def _send_game_update(self, game_state, source):
        """Helper method to send game_update with source tracking."""
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
        return Game.objects.get(id=self.game_id)  # Fetch Game by ID

    @database_sync_to_async
    def get_player(self, username):
        """Fetch Player instance from the database."""
        game = Game.objects.get(id=self.game_id)  # Fetch Game by ID
        return Player.objects.get(game=game, username=username)  # Fetch Player by username and game

    async def handle_move(self, data):
        """Handle a player's move request with turn restriction."""
        game = await self.get_game()  # Get Game instance
        player = await self.get_player(self.scope['user'].username)  # Get current Player
        if player.moved:
            await self.send(text_data=json.dumps({'error': 'You have already moved once this turn'}))
            return
        else:
            to_location = data.get('location')  # Extract target location from message
            if not to_location:
                # Send error if no location provided
                await self.send(text_data=json.dumps({'error': 'No location provided'}))
                return

            from_location = player.location  # Store current location

            print(f"Player {player.username} holds: {player.hand}")  # Debugging: print player hand

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
            if to_location in valid_moves:
                players = await database_sync_to_async(list)(Player.objects.filter(game=game))
                for p in players:
                    if p.location in HALLWAYS and p.location == to_location and p.username != player.username:
                        await self.send(text_data=json.dumps({'error': f'Cannot move to {to_location}, it is occupied by {p.username}'}))
                        return

            if to_location not in valid_moves:
                await self.send(
                    text_data=json.dumps({'error': f'Invalid move: {to_location} is not adjacent to {from_location}'}))
                return

            player.location = to_location  # Update player’s location
            player.moved = True  # Mark player as having moved this turn
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


    async def handle_accuse(self, data):
        """ Handle player's accusation without turn enforcement. """
        try:
            game = await self.get_game()
            player = await self.get_player(self.scope['user'].username)
        except (Game.DoesNotExist, Player.DoesNotExist):
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Game or player not found.'
            }))
            return

        if DEBUG and DEBUG_HANDLE_ACCUSE: # Testing accusation logic
            player.accused = False
            await database_sync_to_async(player.save)()

        # Ensure game is active
        if not game.is_active:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'The game is currently paused or has ended.'
            }))
            return

        # Ensure player is active
        if not player.is_active:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You are no longer active in the game.'
            }))
            return

        # Check if player has already made an accusation
        if player.accused:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'You have already made an accusation and cannot accuse again.'
            }))
            return

        # # Ensure player's turn
        # if not player.turn:
        #     await self.send(text_data=json.dumps({'error: It is not your turn'}))
        #     return


        # Validate accusation inputs
        if isinstance(data, str):
            data = json.loads(data)
        suspect = data.get('suspect')
        weapon = data.get('weapon')
        room = data.get('room')
        if not all([suspect, weapon, room]):
            await self.send(text_data=json.dumps({'error': 'Missing accusation details (suspect, weapon or room)'}))
            return
        if suspect not in SUSPECTS or weapon not in WEAPONS or room not in ROOMS:
            await self.send(text_data=json.dumps({'error': 'Invalid accusation: one or more selections are not valid'}))
            return

        if DEBUG and DEBUG_HANDLE_ACCUSE:  # Testing accusation logic
            game.case_file = {'suspect': 'Miss Scarlet', 'weapon': 'Knife', 'room': 'Study'}
            await database_sync_to_async(game.save)()
            print(f"Case file for Testing: {game.case_file}")

        accusation = {'suspect': suspect, 'weapon': weapon, 'room': room}
        if DEBUG and DEBUG_HANDLE_ACCUSE:
            print(f"Player {player.username} accuses: {accusation}")

        # Mark current player as having made an accusation
        player.accused = True
        await database_sync_to_async(player.save)()

        # Compare accusation to case file
        if accusation == game.case_file:
            # Correct accusation
            # End the game
            game.is_active = False # Set to False for production
            if DEBUG: # Override for development testing
                game.is_active = True
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
            if DEBUG and DEBUG_HANDLE_ACCUSE:
                print(f"Player {player.username} won with correct accusation: {accusation}\n")
        else:
            # Incorrect accusation: Eliminate the accusing player from actions and broadcast elimination
            # Privately notify the accusing player
            await self.send(text_data=json.dumps({
                'type': 'accusation_failed',
                'message': 'Your accusation was incorrect. You are no longer able to move or make accusations but remain a suspect.'
            }))
            # Broadcast elimination to all clients
            await self.channel_layer.group_send(
                self.game_group_name,
                {
                    'type': 'player_eliminated',
                    'player': player.username,
                    'message': f"{player.username} has been eliminated due to an incorrect accusation."
                }
            )
            if DEBUG and DEBUG_HANDLE_ACCUSE:
                print(f"Player {player.username} eliminated with incorrect accusation: {accusation}")
            # Advance turn to next player
            await self.handle_end_turn({})

        # Broadcast updated game state
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )

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
        """Handle a player's suggestion with turn restriction."""

        game = await self.get_game()
        player = await self.get_player(self.scope['user'].username)
        players = await database_sync_to_async(list)(Player.objects.filter(game=game))  # Fetch all players

        # Check if it’s this player’s turn
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'It is not your turn'}))
            return

        # Check if player has moved
        if not player.moved and not player.suggested:
            await self.send(text_data=json.dumps({'error': 'You must move before making a suggestion unless you were moved to the room'}))
            return

        # Check if player has already made an accusation
        if player.accused:
            await self.send(text_data=json.dumps({'error': 'Eliminated players cannot make suggestions'}))
            return

        if player.location not in ROOMS:
            await self.send(text_data=json.dumps({'error': f'You must be in a room to make a suggestion'}))
            return

        suspect = data.get('suspect')
        weapon = data.get('weapon')
        room = data.get('room')
        if not all([suspect, weapon, room]):
            await self.send(text_data=json.dumps({'error': 'Incomplete suggestion (suspect, weapon, or room missing)'}))
            return

        print(f"Player {player.username} suggests: {suspect}, {weapon}, {room}")  # Debugging: print suggestion

        # Move suspect to the room if they are not already
        suspect_player = None
        for p in players:
            if p.character == suspect:
                suspect_player = p

        if suspect_player is None:
            # If the suspect does not have any of the cards, check other players
            for p in players:
                if p.username != player.username:
                    if suspect in p.hand or weapon in p.hand or room in p.hand:
                        print(f"Player {p.username} shows a card to {player.username}")
                        await self.send(text_data=json.dumps({
                            'message': f"{p.username} shows you a card from their hand."
                        }))
                        await self.handle_end_turn(data)  # End the turn after suggestion
                        break
            else:
                # If no one has the cards, send a message to the player
                print(f"No one has the cards {suspect}, {weapon}, or {room}")
                await self.send(text_data=json.dumps({
                    'message': "No one has the cards you suggested."
                }))
        else:
            if suspect_player and suspect_player.location != room:
                suspect_player.location = room  # Move suspect to the suggested room
                suspect_player.suggested = True  # Mark suspect as suggested
                await database_sync_to_async(suspect_player.save)()  # Save changes asynchronously
            else:
                suspect_player.suggested = True  # Mark suspect as suggested
                await database_sync_to_async(suspect_player.save)()  # Save changes asynchronously

            # Check other players’ hands starting with the suspect
            if suspect in suspect_player.hand or weapon in suspect_player.hand or room in suspect_player.hand:
                # If the suspect has any of the cards, they show it to the player
                print(f"Player {suspect} shows a card to {player.username}")
                await self.send(text_data=json.dumps({
                    'message': f"{suspect} shows you a card from their hand."
                }))
                await self.handle_end_turn(data)  # End the turn after suggestion
            else:
                # If the suspect does not have any of the cards, check other players
                for p in players:
                    if p.username != player.username and p.username != suspect:
                        if suspect in p.hand or weapon in p.hand or room in p.hand:
                            print(f"Player {p.username} shows a card to {player.username}")
                            await self.send(text_data=json.dumps({
                                'message': f"{p.username} shows you a card from their hand."
                            }))
                            await self.handle_end_turn(data)  # End the turn after suggestion
                            break
                else:
                    # If no one has the cards, send a message to the player
                    print(f"No one has the cards {suspect}, {weapon}, or {room}")
                    await self.send(text_data=json.dumps({
                        'message': "No one has the cards you suggested."
                    }))

        # Broadcast updated game state
        game_state = await self.get_game_state()
        await self.channel_layer.group_send(
            self.game_group_name,
            {
                'type': 'game_update',
                'game_state': game_state
            }
        )


    async def handle_end_turn(self, data):
        """Handle end of turn for the current player."""
        game = await self.get_game()  # Get Game instance
        player = await self.get_player(self.scope['user'].username)  # Get current Player
        players = await database_sync_to_async(list)(Player.objects.filter(game=game))  # Fetch all players

        # Check if it’s this player’s turn
        if not player.turn:
            await self.send(text_data=json.dumps({'error': 'It is not your turn'}))
            return

        # Check if player has moved
        # Allow turn advancement without a move if the player has made an accusation
        if not player.moved and not player.accused:
            await self.send(text_data=json.dumps({'error': 'You must move before ending your turn'}))
            return

        total_player = len(players)  # Get total number of players
        try:
            player_index = players.index(player) # Get index of the current player
        except ValueError:
            player_index = None

        # Update turn for the next player
        if player_index is not None:
            player.moved = False
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

    async def handle_player_out(self, data):
        """Handle player_out messages to deactivate players."""
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
        """Fetch game state for WebSocket updates."""
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