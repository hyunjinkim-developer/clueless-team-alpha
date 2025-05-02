from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from game.models import Player, Game

class Command(BaseCommand):
    help = """
    Reset all game and player data for a specific game or all games.

    Usage:
        python manage.py reset_game_data --game_id GAME_ID  # Delete Game ID GAME_ID and its players
        python manage.py reset_game_data --all           # Delete all games and players

    Exactly one of --game_id or --all must be specified.
    """

    def add_arguments(self, parser):
        # Create a mutually exclusive group for --game_id and --all
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--game_id',
            type=int,
            help='ID of the game to reset (deletes the game and its players)',
        )
        group.add_argument(
            '--all',
            action='store_true',
            help='Reset all games and players in the database',
        )

    def handle(self, *args, **options):
        game_id = options.get('game_id')
        reset_all = options.get('all')

        try:
            with transaction.atomic():
                if game_id is not None:
                    # Reset specific game and its players
                    try:
                        game = Game.objects.get(id=game_id)
                    except Game.DoesNotExist:
                        raise CommandError(f"Game with ID {game_id} does not exist.")
                    players = Player.objects.filter(game=game)
                    player_count = players.count()
                    if player_count > 0:
                        self.stdout.write(f"Deleting {player_count} player(s) for Game ID {game_id}:")
                        for player in players:
                            self.stdout.write(
                                f" - Player {player.username} (Character: {player.character})"
                            )
                        players.delete()
                    else:
                        self.stdout.write(f"No players found for Game ID {game_id}.")
                    self.stdout.write(f"Deleting Game ID {game_id} (Case File: {game.case_file})")
                    game.delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset Game ID {game_id} and {player_count} player(s)."
                        )
                    )
                elif reset_all:
                    # Reset all games and players
                    players = Player.objects.all()
                    games = Game.objects.all()
                    player_count = players.count()
                    game_count = games.count()
                    if player_count == 0 and game_count == 0:
                        self.stdout.write("No games or players found in the database.")
                        return
                    if player_count > 0:
                        self.stdout.write(f"Deleting {player_count} player(s) across all games:")
                        for player in players:
                            self.stdout.write(
                                f" - Player {player.username} (Character: {player.character}, Game ID: {player.game.id})"
                            )
                        players.delete()
                    if game_count > 0:
                        self.stdout.write(f"Deleting {game_count} game(s):")
                        for game in games:
                            self.stdout.write(f" - Game ID {game.id} (Case File: {game.case_file})")
                        games.delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset {game_count} game(s) and {player_count} player(s)."
                        )
                    )
        except Exception as e:
            raise CommandError(f"Error occurred: {str(e)}")