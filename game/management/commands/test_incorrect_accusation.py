from django.core.management.base import BaseCommand
from channels.db import database_sync_to_async
import json
import asyncio
from game.constants import SUSPECTS, WEAPONS, ROOMS
from game.consumers import GameConsumer
from game.models import Player


class Command(BaseCommand):
    help = (
        'Tests an incorrect accusation in GameConsumer for an existing, active player in a specified game. '
        'Displays the case_file, then simulates an accusation that mismatches it. '
        'If the player’s is_active is False, notifies the developer to log in first. '
        'Usage: python manage.py test_incorrect_accusation --game_id GAME_ID --username USERNAME'
    )

    def add_arguments(self, parser):
        parser.add_argument('--game_id', type=int, required=True, help='ID of the game to test')
        parser.add_argument('--username', type=str, required=True,
                            help='Username of an existing, active player in the game')

    async def async_handle(self, game_id, username):
        """Simulate an incorrect accusation for an existing, active player without modifying the database."""
        # Prepare a mock WebSocket scope for the specified game and user
        scope = {
            'type': 'websocket',
            'path': f'/ws/game/{game_id}/',
            'url_route': {'kwargs': {'game_id': str(game_id)}},
            'user': await self.get_user(username)
        }

        # Set up GameConsumer with the mock scope
        consumer = GameConsumer()
        consumer.scope = scope
        consumer.channel_layer = None
        consumer.channel_name = f"test_{game_id}"

        # Mock connect to initialize consumer
        async def mock_connect():
            print("Simulating WebSocket connection...")
            consumer.game_id = scope['url_route']['kwargs']['game_id']
            print(f"Game ID set to: {consumer.game_id}")
            consumer.game_group_name = f"game_{consumer.game_id}"
            await consumer.accept()
            print(f"Simulated WebSocket connected for game {consumer.game_id}")

        # Mock disconnect for cleanup
        async def mock_disconnect(close_code):
            print(f"Simulated WebSocket disconnected for game {consumer.game_id}")

        # Mock accept as a no-op
        async def mock_accept():
            print("Mock accept called")

        # Mock group_send to log broadcast attempts and handle serialization
        async def mock_group_send(group_name, message):
            print("Mock group_send called")
            if 'game_state' in message:
                game_state = message['game_state']
                game_state['rooms'] = list(game_state['rooms'])
                game_state['hallways'] = list(game_state['hallways'])
                game_state['weapons'] = list(game_state['weapons'])
            print(f"Simulated group_send to {group_name}: {message}")

        # Mock send to log client messages
        async def mock_send(text_data):
            print(f"Simulated send to client: {text_data}")

        # Apply mocks to consumer
        consumer.connect = mock_connect
        consumer.disconnect = mock_disconnect
        consumer.accept = mock_accept
        consumer.channel_layer = type('MockChannelLayer', (), {'group_send': mock_group_send})
        consumer.send = mock_send

        # Simulate WebSocket connection
        await consumer.connect()

        # Fetch and display the case_file
        game = await consumer.get_game()
        self.stdout.write(f"Case file for Game {game_id}: {game.case_file}")

        # Get the player and check their state
        try:
            player = await consumer.get_player(username)
        except Player.DoesNotExist:
            raise ValueError(
                f"Player '{username}' does not exist in Game {game_id}. Please log in to Game 1 first to create the player.")

        if not player.is_active:
            raise ValueError(
                f"Player '{username}' is not active in Game {game_id}. Please log in to Game 1 first to set is_active to True.")

        print(f"Player state - is_active: {player.is_active}")

        # Generate an incorrect accusation
        incorrect_suspect = next(s for s in SUSPECTS if s != game.case_file['suspect'])
        incorrect_weapon = next(w for w in WEAPONS if w != game.case_file['weapon'])
        incorrect_room = next(r for r in ROOMS if r != game.case_file['room'])
        incorrect_accusation = {
            'type': 'accuse',
            'suspect': incorrect_suspect,
            'weapon': incorrect_weapon,
            'room': incorrect_room
        }
        test_message = json.dumps(incorrect_accusation)
        self.stdout.write(f"Testing incorrect accusation for {username} with: {test_message}")

        # Run the accusation test
        print("Sending accusation to receive...")
        await consumer.receive(test_message)
        print("Accusation processing completed")

        # No state change, so no reversion needed
        player_after = await consumer.get_player(username)
        print(f"Player {username} is_active after test: {player_after.is_active}")

        # Simulate disconnection
        await consumer.disconnect(close_code=1000)

    @database_sync_to_async
    def get_user(self, username):
        """Retrieve the User instance for the given username."""
        from django.contrib.auth.models import User
        return User.objects.get(username=username)

    def handle(self, *args, **options):
        """Run the async test for an incorrect accusation."""
        game_id = options['game_id']
        username = options['username']
        try:
            asyncio.run(self.async_handle(game_id, username))
            self.stdout.write(
                self.style.SUCCESS(f"Incorrect accusation test completed for Game {game_id} with user {username}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Test failed: {str(e)}"))