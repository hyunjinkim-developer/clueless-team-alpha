from django.core.management.base import BaseCommand
from game.models import Game, Player
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from game.constants import ROOMS, HALLWAYS, WEAPONS

class Command(BaseCommand):
    help = 'Deletes all Player records ever associated with a specified game and resets players_list on the game table.' \
           'Username and password for login still remain.' \
           'Usage: python manage.py delete_all_players --game_id GAME_ID.'

    def add_arguments(self, parser):
        parser.add_argument('--game_id', type=int, help='The ID of the game to delete all players from')
        parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')

    def handle(self, *args, **options):
        game_id = options['game_id']
        force = options['force']

        try:
            game = Game.objects.get(id=game_id)

            # Count players before deletion
            total_players_before = game.players.count()
            self.stdout.write(f"Total players in Game {game_id} before deletion: {total_players_before}")

            # Confirmation prompt unless --force is used
            if not force:
                confirm = input(f"Are you sure you want to delete all {total_players_before} players from Game {game_id}? (y/n): ")
                if confirm.lower() != 'y':
                    self.stdout.write(self.style.WARNING('Operation cancelled'))
                    return

            # Delete all players
            deleted_count, _ = game.players.all().delete()

            # Reset players_list
            game.players_list = []
            game.save()

            # Verify deletion
            total_players_after = game.players.count()
            self.stdout.write(f"Total players in Game {game_id} after deletion: {total_players_after}")

            if total_players_after == 0:
                self.stdout.write(self.style.SUCCESS(f"Successfully deleted all {deleted_count} players from Game {game_id}"))
            else:
                self.stdout.write(self.style.ERROR(f"Failed to delete all players from Game {game_id}. {total_players_after} remain"))

            # Broadcast updated game state
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"game_{game.id}",
                {
                    'type': 'game_update',
                    'game_state': {
                        'case_file': game.case_file if not game.is_active else None,
                        'players': list(game.players.filter(is_active=True).values('username', 'character', 'location', 'turn', 'hand')),
                        'is_active': game.is_active,
                        'rooms': ROOMS,
                        'hallways': HALLWAYS,
                        'weapons': WEAPONS
                    }
                }
            )
        except Game.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Game with ID {game_id} does not exist"))