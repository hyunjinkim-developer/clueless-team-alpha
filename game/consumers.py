from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
import random
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

        if message_type == 'start_game':
            await self.handle_start_game()
        elif message_type == 'join_game':
            await self.join_game(data)  # Handle join_game message (placeholder)
        elif message_type == 'move':
            await self.handle_move(data)  # Handle player move request
        elif message_type == 'suggest':
            await self.handle_suggest(data)  # Placeholder for suggestion logic
        elif message_type == 'accuse':
            await self.handle_accuse(data)
        elif message_type == 'end_turn':
            await self.handle_end_turn(data)  # Handle end_turn request
        else:
            # Echo unrecognized messages back to the client
            await self.send(text_data=json.dumps({'message': 'Echo: ' + text_data}))

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
        # Convert data to a dictionary if it's a JSON string from a WebSocket message;
        # otherwise, assume it's already a dictionary (e.g., from test scripts)
        game = await self.get_game()
        player = await self.get_player(self.scope['user'].username)
        
        # Check if player has already made an accusation
        if player.accused:
            await self.send(text_data=json.dumps({'error': 'You are eliminated and cannot make accusations'}))
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
    
        # identify which player has the character suggested
        # if character suggested is not assigned to a player, 
        # then the suspect player becomes the next player in the list
        suspect_player = None
        for p in players:
            if p.character == suspect:
                suspect_player = p
        # if suspect_player == None:
        #     currIndex = players.index(player)
        #     nextIndex = currIndex + 1
        #     suspect_player = players[nextIndex]
        
        # fix lines 375 to 425 suggestion logic
        
        # move suspected player to suggested room
        suspect_player.location = room
        suspect_player.suggested = True

        # make list of players in order of checking suggestion with players' card hands
        # start with suggested player
        # then follow turn order
        playerCopyList = players[:]
        playerSuggestList = [suspect_player]
        playerCopyList.remove(suspect_player)
        playerCopyList.remove(player)
        playerSuggestList.extend(playerCopyList)
        print(f"ordered list of players to check card hand for suggestion: {playerSuggestList}")

        # check suspected player's hand for suspect, then weapon, then room
        # put all matches into separate list
        # if 0 cards match - move to next player and repeat process
        # if 1 card matches - state that card disproves the suggestion
        # if more than 1 card matches - ask suspected player which card to disprove suggestion with

        # currHand = suspect_player.hand
        # matchList = []
        # suspectMatch = [card for card in currHand if card==suspect]
        # roomMatch = [card for card in currHand if card==room]
        # weaponMatch = [card for card in currHand if card==weapon]
        # matchList.extend(suspectMatch)
        # matchList.extend(roomMatch)
        # matchList.extend(weaponMatch)
        # print(f"suspected player: {suspect_player.username} as {suspect_player.character}")
        # print(f"suspected player's card hand: {suspect_player.hand}")
        # print(f"List of matching cards: {matchList}") #test which cards match

        # numMatches = len(matchList)
        # if numMatches == 1:
        #     await self.send(text_data=json.dumps({'message': 'Card {matchList} disproves suggestion. End of turn'}))
        #     await self.handle_end_turn(data)
        # elif numMatches > 1:
        #     await self.send(text_data=json.dumps({'message': 'Test message - multiple cards disprove suggestion'}))
        #     await self.handle_end_turn(data)
        # else:
        #     await self.send(text_data=json.dumps({'message': 'No cards to disprove suggestion. Moving to next player'}))
        #     return
        # end of Ria's code 4/27/2025 18:58
        
        # if suspect_player is None:
        #     # If the suspect does not have any of the cards, check other players
        #     for p in players:
        #         if p.username != player.username:
        #             if suspect in p.hand or weapon in p.hand or room in p.hand:
        #                 print(f"Player {p.username} shows a card to {player.username}")
        #                 await self.send(text_data=json.dumps({
        #                     'message': f"{p.username} shows you a card from their hand."
        #                 }))
        #                 await self.handle_end_turn(data)  # End the turn after suggestion
        #                 break
        #     else:
        #         # If no one has the cards, send a message to the player
        #         print(f"No one has the cards {suspect}, {weapon}, or {room}")
        #         await self.send(text_data=json.dumps({
        #             'message': "No one has the cards you suggested."
        #         }))
        # else:
        #     if suspect_player and suspect_player.location != room:
        #         suspect_player.location = room  # Move suspect to the suggested room
        #         suspect_player.suggested = True  # Mark suspect as suggested
        #         await database_sync_to_async(suspect_player.save)()  # Save changes asynchronously
        #     else:
        #         suspect_player.suggested = True  # Mark suspect as suggested
        #         await database_sync_to_async(suspect_player.save)()  # Save changes asynchronously
            
        #     # Check other players’ hands starting with the suspect
        #     if suspect in suspect_player.hand or weapon in suspect_player.hand or room in suspect_player.hand:
        #         # If the suspect has any of the cards, they show it to the player
        #         print(f"Player {suspect} shows a card to {player.username}")
        #         await self.send(text_data=json.dumps({
        #             'message': f"{suspect} shows you a card from their hand."
        #         }))
        #         await self.handle_end_turn(data)  # End the turn after suggestion
        #     else:
        #         # If the suspect does not have any of the cards, check other players
        #         for p in players:
        #             if p.username != player.username and p.username != suspect:
        #                 if suspect in p.hand or weapon in p.hand or room in p.hand:
        #                     print(f"Player {p.username} shows a card to {player.username}")
        #                     await self.send(text_data=json.dumps({
        #                         'message': f"{p.username} shows you a card from their hand."
        #                     }))
        #                     await self.handle_end_turn(data)  # End the turn after suggestion
        #                     break
        #         else:
        #             # If no one has the cards, send a message to the player
        #             print(f"No one has the cards {suspect}, {weapon}, or {room}")
        #             await self.send(text_data=json.dumps({
        #                 'message': "No one has the cards you suggested."
        #             }))

        # Ria's suggestion logic should end here
                    
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
        if not player.moved:
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