HEALTH_PATH = '/health/ready'


class HealthCheckMiddleware:
    """Answers GET HEALTH_PATH with 200 ahead of every other middleware, for Cloud Run's startup probe.

    Add it last so it is outermost: the probe's Host header need not be one of the app's domains, and
    TrustedHostMiddleware answers 400 to anything else. uvicorn serves nothing until lifespan startup has
    finished, so any answer means the worker is ready.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope['path'] == HEALTH_PATH:
            await send({'type': 'http.response.start', 'status': 200,
                        'headers': [(b'content-type', b'text/plain')]})
            await send({'type': 'http.response.body', 'body': b'ok'})
            return
        await self.app(scope, receive, send)
