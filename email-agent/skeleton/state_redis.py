"""
skeleton.state_redis — Redis-backed state persistence.

Production-grade state backend that supports:
  • Multi-process / multi-pod safe (EKS-ready)
  • Automatic TTL expiration for session cleanup
  • Atomic save via SET (no read-modify-write races)
  • Key prefix isolation for multi-tenant deployments

Requirements:
    pip install redis

Usage:
    from skeleton import RedisStateBackend

    backend = RedisStateBackend(url="redis://localhost:6379/0")
    # or with auth:
    backend = RedisStateBackend(url="redis://:password@redis-host:6379/0")
    # or from environment:
    backend = RedisStateBackend()  # reads REDIS_URL env var
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .errors import StateError
from .models import AgentState

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis

    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RedisStateBackend:
    """
    Redis-backed state store for production deployments.

    Features:
      • Multi-process safe — safe behind a load balancer with N replicas
      • TTL-based expiration — sessions auto-expire after `ttl_seconds`
      • Key prefixing — isolate state in shared Redis instances
      • Connection pooling — reuses connections via redis.asyncio

    Args:
        url:          Redis connection URL.  Defaults to REDIS_URL env var
                      or "redis://localhost:6379/0".
        key_prefix:   Prefix for all state keys.  Allows multiple applications
                      to share a single Redis instance.
        ttl_seconds:  Time-to-live for state entries.  Sessions auto-expire
                      after this duration.  Default: 24 hours.
                      Set to None to disable expiration.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        key_prefix: str = "agent:state:",
        ttl_seconds: int | None = 86400,  # 24 hours
    ) -> None:
        if not _REDIS_AVAILABLE:
            raise ImportError(
                "RedisStateBackend requires the 'redis' package. "
                "Install it with: pip install redis"
            )

        self._url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._prefix = key_prefix
        self._ttl = ttl_seconds
        self._redis: Any = None

    def _key(self, session_id: str) -> str:
        """Build the Redis key for a session, with prefix."""
        # Sanitize to prevent key injection
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return f"{self._prefix}{safe_id}"

    async def _get_client(self) -> Any:
        """Lazy-initialize the Redis connection pool."""
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    self._url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
                # Verify connectivity
                await self._redis.ping()
                logger.info("Redis connected: %s", self._url.split("@")[-1])  # Don't log password
            except Exception as exc:
                self._redis = None
                raise StateError(
                    f"Failed to connect to Redis: {exc}",
                    details={"url": self._url.split("@")[-1]},
                ) from exc
        return self._redis

    async def load(self, session_id: str) -> AgentState | None:
        """Load state from Redis by session_id."""
        try:
            client = await self._get_client()
            key = self._key(session_id)
            raw = await client.get(key)
            if raw is None:
                return None
            state = AgentState.model_validate_json(raw)
            logger.debug(
                "State loaded from Redis: session=%s, step=%d",
                session_id,
                state.step_count,
            )
            return state
        except StateError:
            raise
        except Exception as exc:
            raise StateError(
                f"Failed to load state from Redis: {exc}",
                details={"session_id": session_id},
            ) from exc

    async def save(self, state: AgentState) -> None:
        """Save state to Redis (atomic SET with optional TTL)."""
        from datetime import datetime, timezone

        state.updated_at = datetime.now(timezone.utc)
        try:
            client = await self._get_client()
            key = self._key(state.session_id)
            raw = state.model_dump_json()

            if self._ttl is not None:
                await client.setex(key, self._ttl, raw)
            else:
                await client.set(key, raw)

            logger.debug(
                "State saved to Redis: session=%s, step=%d, status=%s",
                state.session_id,
                state.step_count,
                state.status,
            )
        except StateError:
            raise
        except Exception as exc:
            raise StateError(
                f"Failed to save state to Redis: {exc}",
                details={"session_id": state.session_id},
            ) from exc

    async def delete(self, session_id: str) -> None:
        """Remove state from Redis."""
        try:
            client = await self._get_client()
            key = self._key(session_id)
            await client.delete(key)
            logger.debug("State deleted from Redis: session=%s", session_id)
        except Exception as exc:
            raise StateError(
                f"Failed to delete state from Redis: {exc}",
                details={"session_id": session_id},
            ) from exc

    async def close(self) -> None:
        """Close the Redis connection pool."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
            logger.info("Redis connection closed")

    # ── Utility methods for production ops ──

    async def list_sessions(self, limit: int = 100) -> list[str]:
        """List active session IDs (for monitoring/debugging)."""
        try:
            client = await self._get_client()
            pattern = f"{self._prefix}*"
            keys = []
            async for key in client.scan_iter(match=pattern, count=limit):
                session_id = key.removeprefix(self._prefix)
                keys.append(session_id)
                if len(keys) >= limit:
                    break
            return keys
        except Exception as exc:
            raise StateError(
                f"Failed to list sessions: {exc}",
            ) from exc

    async def ttl_remaining(self, session_id: str) -> int | None:
        """Get remaining TTL in seconds for a session. Returns None if no TTL."""
        try:
            client = await self._get_client()
            key = self._key(session_id)
            ttl = await client.ttl(key)
            return ttl if ttl >= 0 else None
        except Exception:
            return None
