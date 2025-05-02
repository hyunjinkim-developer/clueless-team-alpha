from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from game.models import Player, Game

class Command(BaseCommand):
    help = """
    Reset player data and game state to initial values for a specific game or all games.

    Usage:
        python manage.py reset_game_data --game_id <id>  # Delete players and reset Game ID <id> to initial state (is_active=True, players_list=[], begun=False, case_file={})
        python manage.py reset_game_data --all           # Delete all players and reset all games to initial state

    Exactly one of --game_id or --all must be specified. 
    Game records are preserved (rows in the game_game table, representing Game model instances) 
        and reset to an initial state, only player records are deleted. 
    Authentication data (usernames and passwords in auth_user) remains unaffected.
    """

    def add_arguments(self, parser):
        # Create a mutually exclusive group for --game_id and --all
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--game_id',
            type=int,
            help='ID of the game to reset (deletes players and resets game state to initial values)',
        )
        group.add_argument(
            '--all',
            action='store_true',
            help='Reset all players and all games to initial state',
        )

    def handle(self, *args, **options):
        game_id = options.get('game_id')
        reset_all = options.get('all')

        try:
            with transaction.atomic():
                if game_id is not None:
                    # Reset players and game state for a specific game
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
                    game.is_active = True
                    game.players_list = []
                    game.begun = False
                    game.case_file = {}
                    game.save()
                    self.stdout.write(
                        f"Reset Game ID {game_id} to initial state: is_active=True, players_list=[], begun=False, case_file={{}}."
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset Game ID {game_id}: {player_count} player(s) deleted, game state initialized."
                        )
                    )
                elif reset_all:
                    # Reset all players and game state for all games
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
                        games.update(is_active=True, players_list=[], begun=False, case_file={})
                        self.stdout.write(f"Reset {game_count} game(s) to initial state: is_active=True, players_list=[], begun=False, case_file={{}}:")
                        for game in games:
                            self.stdout.write(f" - Game ID {game.id}")
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully reset {game_count} game(s) to initial state and deleted {player_count} player(s)."
                        )
                    )
        except Exception as e:
            raise CommandError(f"Error occurred: {str(e)}")