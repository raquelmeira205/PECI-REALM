import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import deployment.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'radar_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            deployment.routing.websocket_urlpatterns
        )
    ),
})