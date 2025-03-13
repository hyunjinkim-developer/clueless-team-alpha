import os
import django
from daphne.cli import CommandLineInterface

# Set the Manual: os.environ.setdefault points to clueless.settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clueless.settings')
# Load settings and apps, before daphne starts
django.setup()

# Listens on port 8000 for both HTTP (pages) and WebSocket (live) connections.
CommandLineInterface().run(['-b', '0.0.0.0', '-p', '8000', 'clueless.asgi:application'])