from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from game.models import Player, Game

class Command(BaseCommand):
    help = """
    Reset accused status to False for players in a specific game or all games.

    Usage:
        python manage.py reset_accused --game_id GAME_ID  # Reset accused for players in Game ID GAME_ID
        python manage.py reset_accused --all           # Reset accused for all players across all games

    Exactly one of --game_id or --all must be specified.
    """

    def add_arguments(self, parser):
        # Create a mutually exclusive group for --game_id and --all
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--game_id',
            type=int,
            help='ID of the game to reset accused status for',
        )
        group.add_argument(
            '--all',
            action='store_true',
            help='Reset accused status for all players across all games',
        )

    def handle(self, *args, **options):
        game_id = options.get('game_id')
        reset_all = options.get('all')

        try:
            with transaction.atomic():
                if game_id is not None:
                    # Reset accused for players in a specific game
                    try:
                        game = Game.objects.get(id=game_id)
                    except Game.DoesNotExist:
                        raise CommandError(f"Game with ID {game_id} does not exist.")
                    players = Player.objects.filter(game=game)
                    if not players.exists():
                        self.stdout.write(f"No players found for Game ID {game_id}.")
                        return
                    count = players.update(accused=False)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset accused status for {count} player(s) in Game ID {game_id}."
                        )
                    )
                    for player in players:
                        self.stdout.write(
                            f" - Player {player.username} (Character: {player.character}) reset to accused=False"
                        )
                elif reset_all:
                    # Reset accused for all players across all games
                    players = Player.objects.all()
                    if not players.exists():
                        self.stdout.write("No players found in the database.")
                        return
                    count = players.update(accused=False)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset accused status for {count} player(s) across all games."
                        )
                    )
                    for player in players:
                        self.stdout.write(
                            f" - Player {player.username} (Character: {player.character}, Game ID: {player.game.id}) reset to accused=False"
                        )
        except Exception as e:
            raise CommandError(f"Error occurred: {str(e)}")