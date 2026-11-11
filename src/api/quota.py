"""Per-visitor and per-IP daily question limits (Phase 7, #64).

A visitor is a server-signed token the browser keeps and sends in the
`X-Visitor-Token` header (a cookie won't work: frontend and backend are on
different domains). The IP (IPv6 reduced to its /64) has a higher limit, so a
shared office network isn't blocked by one person, while clearing storage to
get a new token only buys a few extra questions. A request without a valid
token gets the per-visitor limit on its IP.

Only questions that reached the LLM are charged. Counters live in Upstash
Redis (the container's disk is wiped when it sleeps) and expire at the end
of the UTC day. If Redis is unreachable the check fails open: the provider
spend limit on the OpenRouter key is the last line of defence.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import ipaddress
import secrets
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Protocol

import httpx

from src.obs.logging import get_logger

log = get_logger(__name__)


class Store(Protocol):
    def get_many(self, keys: List[str]) -> List[int]: ...
    def incr_many(self, keys: List[str], ttl_seconds: int) -> List[int]: ...


class UpstashStore:
    """Minimal Upstash Redis client over its REST pipeline endpoint."""

    def __init__(self, url: str, token: str, timeout: float = 5.0):
        self.url = url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = timeout

    def _pipeline(self, commands: List[List[Any]]) -> List[Any]:
        r = httpx.post(f"{self.url}/pipeline", json=commands, headers=self.headers, timeout=self.timeout)
        r.raise_for_status()
        out = []
        for item in r.json():
            if item.get("error"):
                raise RuntimeError(item["error"])
            out.append(item.get("result"))
        return out

    def get_many(self, keys: List[str]) -> List[int]:
        return [int(v or 0) for v in self._pipeline([["GET", k] for k in keys])]

    def incr_many(self, keys: List[str], ttl_seconds: int) -> List[int]:
        cmds: List[List[Any]] = []
        for k in keys:
            cmds += [["INCR", k], ["EXPIRE", k, ttl_seconds]]
        res = self._pipeline(cmds)
        return [int(res[i]) for i in range(0, len(res), 2)]


# ── Visitor tokens ───────────────────────────────────────────────────

def issue_token(secret: str) -> str:
    vid = secrets.token_urlsafe(12)
    return f"{vid}.{_sign(vid, secret)}"


def verify_token(token: Optional[str], secret: str) -> Optional[str]:
    """The visitor id if the token is genuine, else None."""
    if not token or "." not in token:
        return None
    vid, sig = token.rsplit(".", 1)
    return vid if vid and hmac.compare_digest(sig, _sign(vid, secret)) else None


def _sign(vid: str, secret: str) -> str:
    return hmac.new(secret.encode(), vid.encode(), hashlib.sha256).hexdigest()[:32]


def ip_bucket(ip: Optional[str]) -> str:
    """IPv4 as-is; IPv6 reduced to its /64 (one household or phone)."""
    if not ip:
        return "unknown"
    try:
        addr = ipaddress.ip_address(ip.strip())
    except ValueError:
        return "unknown"
    if addr.version == 6:
        return str(ipaddress.ip_network(f"{addr}/64", strict=False).network_address) + "/64"
    return str(addr)


# ── Quota ────────────────────────────────────────────────────────────

@dataclass
class QuotaStatus:
    left: Optional[int]  # None when the quota is off or unreadable
    limit: int
    allowed: bool


class Quota:
    def __init__(
        self,
        store: Optional[Store],
        secret: str,
        per_visitor: int,
        per_ip: int,
        today: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.timezone.utc),
    ):
        self.store = store
        self.secret = secret or "dev-only-secret"
        self.per_visitor = per_visitor
        self.per_ip = per_ip
        self.today = today

    @property
    def enabled(self) -> bool:
        return self.store is not None

    def new_token(self) -> str:
        return issue_token(self.secret)

    def visitor(self, token: Optional[str]) -> Optional[str]:
        return verify_token(token, self.secret)

    def _keys(self, visitor: Optional[str], ip: Optional[str]) -> List[str]:
        day = self.today().strftime("%Y%m%d")
        keys = [f"q:ip:{ip_bucket(ip)}:{day}"]
        if visitor:
            keys.insert(0, f"q:v:{visitor}:{day}")
        return keys

    def _limits(self, visitor: Optional[str]) -> List[int]:
        # No valid token: the IP gets the per-visitor limit.
        return [self.per_visitor, self.per_ip] if visitor else [self.per_visitor]

    def _ttl(self) -> int:
        now = self.today()
        tomorrow = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return int((tomorrow - now).total_seconds()) + 60

    def check(self, visitor: Optional[str], ip: Optional[str]) -> QuotaStatus:
        if not self.enabled:
            return QuotaStatus(left=None, limit=self.per_visitor, allowed=True)
        try:
            used = self.store.get_many(self._keys(visitor, ip))
        except Exception as e:  # fail open; the provider spend limit still holds
            log.warning("quota.unavailable", error=str(e))
            return QuotaStatus(left=None, limit=self.per_visitor, allowed=True)
        left = min(limit - u for limit, u in zip(self._limits(visitor), used))
        return QuotaStatus(left=max(0, left), limit=self.per_visitor, allowed=left > 0)

    def charge(self, visitor: Optional[str], ip: Optional[str]) -> Optional[int]:
        """Count one LLM-reaching question; returns questions left, or None."""
        if not self.enabled:
            return None
        try:
            used = self.store.incr_many(self._keys(visitor, ip), self._ttl())
        except Exception as e:
            log.warning("quota.charge_failed", error=str(e))
            return None
        return max(0, min(limit - u for limit, u in zip(self._limits(visitor), used)))


def reached_llm(final: dict) -> bool:
    """True if generate called the LLM: not a cache hit or refusal, and it had passages."""
    if final.get("cache_hit") or final.get("termination_reason") == "out_of_domain":
        return False
    return bool(final.get("chunks"))


def default_quota() -> Quota:
    from src.config import get_settings

    cfg = get_settings()
    store = UpstashStore(cfg.upstash_redis_rest_url, cfg.upstash_redis_rest_token) if cfg.upstash_redis_rest_url else None
    if store and not cfg.visitor_token_secret:
        log.warning("quota.no_token_secret", hint="set VISITOR_TOKEN_SECRET; tokens use a dev-only secret")
    return Quota(store, cfg.visitor_token_secret, cfg.quota_per_visitor_day, cfg.quota_per_ip_day)
