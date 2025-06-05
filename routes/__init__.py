from .exchange_routes import router as exchange_routes
from .preferences_routes import router as preferences_routes
from .stats_routes import router as stats_routes
from .notification_routes import router as notification_routes

__all__ = [
    'exchange_routes',
    'preferences_routes',
    'stats_routes',
    'notification_routes'
] 