"""
ASGI config for clueless project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.sessions import SessionMiddlewareStack
import game.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'clueless.settings')

print("ASGI application loaded")
application = ProtocolTypeRouter({
    'http': get_asgi_application(),  # Handles HTTP requests
    "websocket": SessionMiddlewareStack(  # Handles WebSocket requests
        AuthMiddlewareStack(
            URLRouter(
                game.routing.websocket_urlpatterns
            )
        )
    ),
})
