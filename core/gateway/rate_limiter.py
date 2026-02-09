"""
Rate Limiter for Gateway Module

Implements token bucket rate limiting for API requests.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Tracks requests per client and enforces rate limits.
    """

    def __init__(self, requests_per_minute: int = 60):
        self.config = RateLimitConfig(requests_per_minute=requests_per_minute)
        self.tokens: Dict[str, list] = defaultdict(list)
        self.burst_tokens: Dict[str, list] = defaultdict(list)

    def _cleanup_old_tokens(self, tokens: dict, window: int) -> None:
        """Remove tokens older than the window."""
        now = time.time()
        cutoff = now - window

        for client_id in list(tokens.keys()):
            tokens[client_id] = [t for t in tokens[client_id] if t > cutoff]

            if not tokens[client_id]:
                del tokens[client_id]

    def _get_tokens(self, client_id: str, window: int) -> list:
        """Get tokens for a client within a time window."""
        now = time.time()
        cutoff = now - window

        client_tokens = self.tokens.get(client_id, [])
        return [t for t in client_tokens if t > cutoff]

    def allow_request(self, client_id: str, window: int = 60) -> bool:
        """
        Check if a request is allowed for the given client.
        
        Args:
            client_id: Unique identifier for the client
            window: Time window in seconds (default 60 for per-minute)
        
        Returns:
            True if the request is allowed, False otherwise
        """
        self._cleanup_old_tokens(self.tokens, window)

        current_tokens = self._get_tokens(client_id, window)

        if len(current_tokens) < self.config.requests_per_minute:
            current_tokens.append(time.time())
            self.tokens[client_id] = current_tokens
            return True

        return False

    def get_remaining(self, client_id: str, window: int = 60) -> int:
        """Get remaining requests for a client in the current window."""
        current_tokens = self._get_tokens(client_id, window)
        return max(0, self.config.requests_per_minute - len(current_tokens))

    def get_reset_time(self, client_id: str, window: int = 60) -> float:
        """Get the time until the rate limit resets for a client."""
        current_tokens = self._get_tokens(client_id, window)

        if not current_tokens:
            return 0.0

        oldest = min(current_tokens)
        return max(0.0, oldest + window - time.time())


class DistributedRateLimiter:
    """
    Redis-backed distributed rate limiter for multi-instance deployments.
    
    Uses Redis INCR and EXPIRE for atomic operations.
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.local_limiter = RateLimiter()

    async def allow_request(self, client_id: str, limit: int = 60) -> bool:
        """
        Check if a request is allowed using Redis.
        
        Falls back to local limiter if Redis is unavailable.
        """
        if not self.redis:
            return self.local_limiter.allow_request(client_id)

        try:
            key = f"ratelimit:{client_id}"

            # Increment counter
            current = await self.redis.incr(key)

            # Set expiry on first request
            if current == 1:
                await self.redis.expire(key, 60)

            # Check limit
            if current <= limit:
                return True

            return False

        except Exception:
            # Fallback to local limiter
            return self.local_limiter.allow_request(client_id)

    async def get_remaining(self, client_id: str, limit: int = 60) -> int:
        """Get remaining requests."""
        if not self.redis:
            return self.local_limiter.get_remaining(client_id)

        try:
            key = f"ratelimit:{client_id}"
            current = await self.redis.get(key)
            current = int(current) if current else 0
            return max(0, limit - current)

        except Exception:
            return self.local_limiter.get_remaining(client_id)
