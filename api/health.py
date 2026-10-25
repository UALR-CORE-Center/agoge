"""A minimal readiness probe that works with Cloud Run's internal Host header."""
from fastapi import APIRouter, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse


READINESS_PATH = '/health/ready'


class HealthCheckTrustedHostMiddleware(TrustedHostMiddleware):
    async def __call__(self, scope, receive, send):
        # Cloud Run probes can use an internal host instead of the public domain.
        # Exempt only the read-only readiness endpoint, never application routes.
        if (scope['type'] == 'http' and scope.get('method') in ('GET', 'HEAD')
                and scope.get('path') == READINESS_PATH):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


health_router = APIRouter()


@health_router.api_route(READINESS_PATH, methods=['GET', 'HEAD'], include_in_schema=False)
async def readiness(request: Request):
    # Lifespan initializes the environment once. Probes make no cloud calls and
    # expose no project settings, credentials or dependency error messages.
    ready = getattr(request.app.state, 'api_ready', False)
    return JSONResponse({'status': 'ready' if ready else 'not_ready'},
                        status_code=200 if ready else 503,
                        headers={'Cache-Control': 'no-store'})
