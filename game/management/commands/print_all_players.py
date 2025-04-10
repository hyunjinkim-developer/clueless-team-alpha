from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Prints all usernames and their hashed passwords from the auth_user table(Signin user table).'

    def handle(self, *args, **options):
        # Fetch all users
        users = User.objects.all()

        if not users:
            self.stdout.write(self.style.WARNING('No users found in the database'))
            return

        self.stdout.write('List of all users:')
        for user in users:
            username = user.username
            password_hash = user.password
            self.stdout.write(f"Username: {username}, Password Hash: {password_hash}")

        self.stdout.write(self.style.SUCCESS(f"Successfully printed {users.count()} users"))