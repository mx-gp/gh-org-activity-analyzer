import hashlib
import json
import os
import time
from typing import Any, Optional, Tuple


class ResponseCache:
    """Disk-backed HTTP response cache supporting TTL expiration and ETags.

    Stores cache entries in a specified directory (default: ~/.cache/gh_analyzer_cache).
    """

    def __init__(self, cache_dir: Optional[str] = None, default_ttl: int = 300, enabled: bool = True):
        self.enabled = enabled
        self.default_ttl = default_ttl
        if cache_dir:
            self.cache_dir = os.path.abspath(os.path.expanduser(cache_dir))
        else:
            base_dir = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
            self.cache_dir = os.path.join(base_dir, "gh_analyzer_cache")

        if self.enabled:
            os.makedirs(self.cache_dir, exist_ok=True)

    def _get_key(self, url: str, method: str = "GET", data: Optional[Any] = None) -> str:
        data_str = json.dumps(data, sort_keys=True) if data else ""
        raw_key = f"{method}:{url}:{data_str}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _entry_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, url: str, method: str = "GET", data: Optional[Any] = None) -> Tuple[Optional[Any], Optional[str], bool]:
        """Returns (cached_data, etag, is_expired).

        If not cached, returns (None, None, True).
        """
        if not self.enabled:
            return None, None, True

        key = self._get_key(url, method, data)
        path = self._entry_path(key)
        if not os.path.exists(path):
            return None, None, True

        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)

            cached_data = entry.get("data")
            etag = entry.get("etag")
            expires_at = entry.get("expires_at", 0)

            is_expired = time.time() > expires_at
            return cached_data, etag, is_expired
        except Exception:
            return None, None, True

    def set(
        self,
        url: str,
        method: str,
        data: Optional[Any],
        response_data: Any,
        etag: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Saves response data, optional etag, and TTL expiration to disk cache."""
        if not self.enabled:
            return

        ttl = self.default_ttl if ttl is None else ttl
        key = self._get_key(url, method, data)
        path = self._entry_path(key)

        entry = {
            "url": url,
            "method": method,
            "etag": etag,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
            "data": response_data,
        }

        tmp_path = f"{path}.tmp.{os.getpid()}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(entry, f)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def touch(self, url: str, method: str = "GET", data: Optional[Any] = None, ttl: Optional[int] = None) -> None:
        """Refreshes expiration on an existing 304 Not Modified cache entry."""
        if not self.enabled:
            return

        ttl = self.default_ttl if ttl is None else ttl
        key = self._get_key(url, method, data)
        path = self._entry_path(key)
        if not os.path.exists(path):
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            entry["expires_at"] = time.time() + ttl
            tmp_path = f"{path}.tmp.{os.getpid()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(entry, f)
            os.replace(tmp_path, path)
        except Exception:
            pass

    def clear(self) -> int:
        """Removes all cache entries from disk."""
        if not os.path.exists(self.cache_dir):
            return 0
        count = 0
        for f in os.listdir(self.cache_dir):
            if f.endswith(".json"):
                try:
                    os.remove(os.path.join(self.cache_dir, f))
                    count += 1
                except OSError:
                    pass
        return count
