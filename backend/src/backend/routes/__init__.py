"""Routes package - API endpoint handlers."""
from . import user, events, feedback, bot

available_routers = [
    user.router,
    events.router,
    feedback.router,
    bot.router,
]