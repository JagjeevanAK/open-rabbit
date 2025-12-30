from . import user, events, feedback, bot_webhook, user_feedback

available_routers = [
    user.router,
    events.router,
    feedback.router,
    bot_webhook.router,
    user_feedback.router
]