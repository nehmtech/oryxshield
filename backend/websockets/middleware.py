"""
WebSocket ASGI middleware for OryxShield.

Layers (applied outer → inner):
  LoggingMiddleware      – lifecycle logging
  IPWhitelistMiddleware  – optional IP restriction (via settings.WS_ALLOWED_IPS)
  RateLimitMiddleware    – per-user concurrent-connection cap (Redis-backed)
  JWTAuthMiddleware      – JWT from query-string ?token= or Authorization header
"""
import logging
from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client_ip(scope) -> str:
    """Extract the real client IP, respecting X-Forwarded-For."""
    headers = dict(scope.get('headers', []))
    xff = headers.get(b'x-forwarded-for', b'').decode()
    if xff:
        return xff.split(',')[0].strip()
    client = scope.get('client')
    return client[0] if client else ''


def _get_token_from_scope(scope) -> str | None:
    """
    Return the raw JWT string from (in priority order):
      1. Sec-WebSocket-Protocol header with format "bearer.<jwt>"
         (frontend passes this to avoid exposing token in URL / server logs)
      2. Authorization: Bearer <jwt> header
      3. ?token=<jwt> query parameter (legacy / fallback)
    """
    headers = dict(scope.get('headers', []))

    # 1. Sec-WebSocket-Protocol: bearer.<jwt>
    # The client sends: new WebSocket(url, ['bearer', token])
    # The handshake header is: Sec-WebSocket-Protocol: bearer, <jwt>
    # OR some clients encode as a single value: "bearer.<token>"
    ws_protocols = headers.get(b'sec-websocket-protocol', b'').decode()
    if ws_protocols:
        parts = [p.strip() for p in ws_protocols.split(',')]
        for i, part in enumerate(parts):
            if part.lower() == 'bearer' and i + 1 < len(parts):
                candidate = parts[i + 1].strip()
                if candidate:
                    return candidate
            # Also handle "bearer.<token>" single value
            if part.lower().startswith('bearer.'):
                return part[7:].strip()

    # 2. Authorization header (standard HTTP upgrade headers)
    auth_header = headers.get(b'authorization', b'').decode()
    if auth_header.lower().startswith('bearer '):
        return auth_header[7:].strip()

    # 3. Query string (legacy — token appears in server logs; prefer options 1/2)
    qs = scope.get('query_string', b'').decode()
    params = parse_qs(qs)
    token = params.get('token', [None])[0]
    if token:
        return token

    return None


# ---------------------------------------------------------------------------
# JWTAuthMiddleware
# ---------------------------------------------------------------------------

class JWTAuthMiddleware(BaseMiddleware):
    """
    Authenticate WebSocket handshakes via JWT.

    Sets scope['user'] to the authenticated User instance or AnonymousUser.
    Does NOT close the connection here — individual consumers decide whether
    to reject anonymous users.
    """

    async def __call__(self, scope, receive, send):
        token = _get_token_from_scope(scope)

        if token:
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                scope['user'] = await self._get_user(user_id)
                if scope['user'].is_authenticated:
                    logger.info('WS auth OK: user_id=%s path=%s', user_id, scope.get('path'))
                else:
                    logger.warning('WS auth: user_id=%s not found / inactive', user_id)
            except TokenError as exc:
                logger.warning('WS auth token error: %s', exc)
                scope['user'] = AnonymousUser()
            except Exception as exc:
                logger.error('WS auth unexpected error: %s', exc, exc_info=True)
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _get_user(self, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return AnonymousUser()


# ---------------------------------------------------------------------------
# IPWhitelistMiddleware
# ---------------------------------------------------------------------------

class IPWhitelistMiddleware(BaseMiddleware):
    """
    Restrict WebSocket connections to a list of IPs defined in
    settings.WS_ALLOWED_IPS (list of strings).  An empty list means *all*
    IPs are allowed.
    """

    async def __call__(self, scope, receive, send):
        allowed = getattr(settings, 'WS_ALLOWED_IPS', [])
        if allowed:
            client_ip = _get_client_ip(scope)
            if client_ip not in allowed:
                logger.warning('WS IP rejected: %s path=%s', client_ip, scope.get('path'))
                await send({'type': 'websocket.close', 'code': 4403})
                return
        return await super().__call__(scope, receive, send)


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseMiddleware):
    """
    Reject connections that would exceed settings.WS_MAX_CONNECTIONS_PER_USER
    (default 10) for an authenticated user.

    Uses Redis via django-channels' channel layer.  Falls back gracefully if
    Redis is unavailable (allows the connection rather than failing hard).
    """

    MAX_CONNECTIONS: int = getattr(settings, 'WS_MAX_CONNECTIONS_PER_USER', 10)
    KEY_PREFIX: str = 'ws:conn_count:'

    async def __call__(self, scope, receive, send):
        user = scope.get('user')
        if user and user.is_authenticated:
            try:
                over_limit = await self._is_over_limit(user.pk)
                if over_limit:
                    logger.warning(
                        'WS rate-limit: user_id=%s exceeded %d connections',
                        user.pk,
                        self.MAX_CONNECTIONS,
                    )
                    await send({'type': 'websocket.close', 'code': 4429})
                    return
            except Exception as exc:
                # Redis unavailable — allow the connection, log the error
                logger.error('WS rate-limit check failed: %s', exc)

        return await super().__call__(scope, receive, send)

    async def _is_over_limit(self, user_id) -> bool:
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        key = f'{self.KEY_PREFIX}{user_id}'
        # Increment; set TTL on first creation (24 h safety net)
        # Using Redis directly via channel_layer's pool if available
        redis_pool = getattr(channel_layer, '_get_or_create_connection', None)
        if redis_pool is None:
            # Generic fallback: optimistically allow
            return False
        # Access underlying aioredis/redis-py via channel_layer
        count = await sync_to_async(self._redis_incr)(channel_layer, key)
        return count > self.MAX_CONNECTIONS

    @staticmethod
    def _redis_incr(channel_layer, key: str) -> int:
        """Synchronous Redis INCR via channel_layer's connection pool."""
        # channels-redis exposes a sync client via .get_capacity() internals;
        # the safest cross-version approach is going through aioredis directly.
        # Fall back to 0 (allow) on any failure.
        try:
            import redis as redis_lib
            url = getattr(channel_layer, 'hosts', [('redis://localhost', 6379)])[0]
            client = redis_lib.Redis.from_url(url if isinstance(url, str) else f'redis://{url[0]}:{url[1]}')
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, 86400)
            result = pipe.execute()
            client.close()
            return result[0]
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# LoggingMiddleware
# ---------------------------------------------------------------------------

class LoggingMiddleware(BaseMiddleware):
    """
    Log every WebSocket connection open and close with user, IP, and path.
    """

    async def __call__(self, scope, receive, send):
        path    = scope.get('path', '')
        ip      = _get_client_ip(scope)
        user    = scope.get('user', AnonymousUser())
        uname   = user.username if getattr(user, 'is_authenticated', False) else 'anon'

        logger.info('WS open  path=%s user=%s ip=%s', path, uname, ip)
        try:
            result = await super().__call__(scope, receive, send)
            logger.info('WS close path=%s user=%s ip=%s', path, uname, ip)
            return result
        except Exception as exc:
            logger.error('WS error path=%s user=%s ip=%s err=%s', path, uname, ip, exc, exc_info=True)
            raise