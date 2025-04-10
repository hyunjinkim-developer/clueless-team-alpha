from django.core.management.base import BaseCommand
from game.models import Game, Player
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from game.constants import ROOMS, HALLWAYS, WEAPONS

class Command(BaseCommand):
    help = 'Logs out all players from a specified game by setting is_active=False' \
           'Usage: python manage.py logout_all_players --game_id <game_id>.'

    def add_arguments(self, parser):
        parser.add_argument('--game_id', type=int, help='The ID of the game to log out players from')

    def handle(self, *args, **options):
        game_id = options['game_id']
        try:
            game = Game.objects.get(id=game_id)

            # Count active players before logout
            active_before = game.players.filter(is_active=True).count()
            # Log out all players
            game.players.update(is_active=False)
            # Verify active players after logout
            active_after = game.players.filter(is_active=True).count()
            self.stdout.write(f"Active players in Game {game_id}: before logout {active_before} -> after logout {active_after}")

            # Check if all players were logged out
            if active_after == 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully logged out all {active_before} players from Game {game_id}"))
                self.stdout.write(f"Players ever joined in Game {game.players_list}")
            else:
                self.stdout.write(self.style.ERROR(
                    f"Failed to log out all players from Game {game_id}. {active_after} remain active"))

        except Game.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Game with ID {game_id} does not exist'))