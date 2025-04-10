from django.core.management.base import BaseCommand
from game.models import Game

class Command(BaseCommand):
    help = (
        'Prints the case file for a specified game. '
        'Usage: manage.py print_case_file --game_id GAME_ID'
    )

    def add_arguments(self, parser):
        parser.add_argument('--game_id', type=int, required=True, help='ID of the game to print the case file for')

    def handle(self, *args, **options):
        game_id = options['game_id']
        try:
            game = Game.objects.get(id=game_id)
            case_file = game.case_file
            if case_file:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Case file for Game {game_id}: {case_file}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"No case file exists for Game {game_id}. It is currently empty: {case_file}"
                    )
                )
        except Game.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Game {game_id} does not exist. Please create a game first.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"An error occurred: {str(e)}")
            )