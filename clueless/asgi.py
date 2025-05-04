"""
ASGI configuration for the Clue-Less project, a multiplayer game with WebSocket support.

This file defines the ASGI application, enabling the project to handle both HTTP and
WebSocket requests. It integrates Django's standard HTTP handling with Channels for
WebSocket communication, supporting real-time game features like dynamic player updates
and game state synchronization. The configuration uses ProtocolTypeRouter to dispatch
requests, with middleware for session and authentication support, and routes WebSocket
requests via game.routing.

Key features:
- Handles HTTP requests for views (e.g., /login/, /start_game/).
- Manages WebSocket connections for real-time gameplay (e.g., player_joined, game_started).
- Supports session validation and user authentication for secure WebSocket interactions.
- Integrates with fixes for AttributeError at /login/ and lobby functionality (dynamic
  updates, start button, reload errors).

For more information, see:
- https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
- https://channels.readthedocs.io/en/stable/topics/routing.html
- https://channels.readthedocs.io/en/stable/topics/authentication.html
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.sessions import SessionMiddlewareStack
import game.routing

# Set the default Django settings module for the ASGI application
# Ensures the application uses clueless.settings for configuration (e.g., middleware,
# session settings, and Channels setup). Must be set before importing Django components
# to avoid ImproperlyConfigured errors
# See: https://docs.djangoproject.com/en/5.1/ref/settings/
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clueless.settings')

# Log a message to confirm the ASGI application is loaded
# Useful for debugging startup issues in development or deployment
print("ASGI application loaded")

# Define the ASGI application using ProtocolTypeRouter
# Routes incoming connections based on protocol type (http or websocket)
# - 'http': Uses Django's get_asgi_application() for standard HTTP requests
# - 'websocket': Chains middleware (SessionMiddlewareStack, AuthMiddlewareStack) and
#   routes WebSocket requests to game.routing.websocket_urlpatterns
# See: https://channels.readthedocs.io/en/stable/topics/routing.html#protocoltyperouter
application = ProtocolTypeRouter({
    'http': get_asgi_application(),  # Handles HTTP requests (e.g., /login/, /game/)
    "websocket": SessionMiddlewareStack(  # Handles WebSocket requests with session support
        AuthMiddlewareStack(  # Adds user authentication to WebSocket connections
            URLRouter(  # Routes WebSocket URLs defined in game.routing
                game.routing.websocket_urlpatterns  # Patterns like /ws/game/<game_id>/
            )
        )
    ),
})