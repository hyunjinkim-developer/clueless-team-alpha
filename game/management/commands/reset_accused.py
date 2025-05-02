from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from game.models import Player, Game

class Command(BaseCommand):
    help = """
    Reset accused status to False for players and set game is_active to True for a specific game or all games.

    Usage:
        python manage.py reset_accused --game_id <id>  # Reset accused for players and is_active for Game ID <id>
        python manage.py reset_accused --all           # Reset accused for all players and is_active for all games

    Exactly one of --game_id or --all must be specified.
    """

    def add_arguments(self, parser):
        # Create a mutually exclusive group for --game_id and --all
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--game_id',
            type=int,
            help='ID of the game to reset accused status and is_active for',
        )
        group.add_argument(
            '--all',
            action='store_true',
            help='Reset accused status for all players and is_active for all games',
        )

    def handle(self, *args, **options):
        game_id = options.get('game_id')
        reset_all = options.get('all')

        try:
            with transaction.atomic():
                if game_id is not None:
                    # Reset accused for players and is_active for a specific game
                    try:
                        game = Game.objects.get(id=game_id)
                    except Game.DoesNotExist:
                        raise CommandError(f"Game with ID {game_id} does not exist.")
                    players = Player.objects.filter(game=game)
                    player_count = players.count()
                    if player_count > 0:
                        players.update(accused=False)
                        self.stdout.write(f"Reset accused status for {player_count} player(s) in Game ID {game_id}:")
                        for player in players:
                            self.stdout.write(
                                f" - Player {player.username} (Character: {player.character}) reset to accused=False"
                            )
                    else:
                        self.stdout.write(f"No players found for Game ID {game_id}.")
                    game.is_active = True
                    game.save()
                    self.stdout.write(f"Reset is_active to True for Game ID {game_id}.")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset Game ID {game_id}: {player_count} player(s) accused=False, is_active=True."
                        )
                    )
                elif reset_all:
                    # Reset accused for all players and is_active for all games
                    players = Player.objects.all()
                    games = Game.objects.all()
                    player_count = players.count()
                    game_count = games.count()
                    if player_count == 0 and game_count == 0:
                        self.stdout.write("No games or players found in the database.")
                        return
                    if player_count > 0:
                        players.update(accused=False)
                        self.stdout.write(f"Reset accused status for {player_count} player(s) across all games:")
                        for player in players:
                            self.stdout.write(
                                f" - Player {player.username} (Character: {player.character}, Game ID: {player.game.id}) reset to accused=False"
                            )
                    if game_count > 0:
                        games.update(is_active=True)
                        self.stdout.write(f"Reset is_active to True for {game_count} game(s):")
                        for game in games:
                            self.stdout.write(f" - Game ID {game.id}")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset {game_count} game(s) is_active=True and {player_count} player(s) accused=False."
                        )
                    )
        except Exception as e:
            raise CommandError(f"Error occurred: {str(e)}")