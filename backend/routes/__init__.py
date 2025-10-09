from . import user, events, feedback, bot_webhook

available_routers = [
    user.router,
    events.router,
    feedback.router,
    bot_webhook.router
]