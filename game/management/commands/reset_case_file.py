from django.core.management.base import BaseCommand, CommandError
import argparse
import sys
from game.models import Game

class CustomBaseCommand(BaseCommand):
    """
    Custom base command to override default argument parsing and provide a friendly error message
    when required arguments are missing.
    """
    def create_parser(self, prog_name, subcommand):
        # Create a parser that doesn’t exit on error (suppresses default error output)
        parser = argparse.ArgumentParser(
            prog=f"{prog_name} {subcommand}",
            description=self.help or None,
            add_help=True
        )
        self.add_arguments(parser)
        return parser

    def run_from_argv(self, argv):
        try:
            # Parse arguments manually without letting argparse exit
            parser = self.create_parser(argv[0], argv[1])
            options = parser.parse_args(argv[2:])
            cmd_options = vars(options)
            # Check for required argument ourselves
            if 'game_id' not in cmd_options or cmd_options['game_id'] is None:
                self.stdout.write(
                    self.style.WARNING(
                        "You didn’t type in the game_id. Please specify it with --game_id (e.g., 'python manage.py reset_case_file --game_id 1')."
                    )
                )
                sys.exit(1)
            # Proceed with normal execution
            self.handle(**cmd_options)
        except Exception as e:
            if not isinstance(e, SystemExit):
                self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {str(e)}"))
            sys.exit(1)

class Command(CustomBaseCommand):
    help = 'Resets the case file for Game <game_id> to an empty dictionary. ' \
           'Usage: manage.py reset_case_file --game_id GAME_ID' \
           'Running the script without --game_id raises an error.'

    def add_arguments(self, parser):
        parser.add_argument('--game_id', type=int, required=True, help="ID of the game to reset")

    def handle(self, *args, **options):
        game_id = options['game_id']
        try:
            game = Game.objects.get(id=game_id)
            old_case_file = game.case_file
            game.case_file = {}
            game.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully reset case file for Game {game_id}. Old value: {old_case_file}, New value: {game.case_file}"
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