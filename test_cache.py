import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import MagicMock
from analyzer import GitHubOrgActivityAnalyzer
from cache import ResponseCache


class TestResponseCache(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cache = ResponseCache(cache_dir=self.test_dir, default_ttl=2, enabled=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cache_miss_and_hit(self):
        url = "https://api.github.com/repos/octocat/hello"
        data, etag, expired = self.cache.get(url)
        self.assertIsNone(data)
        self.assertIsNone(etag)
        self.assertTrue(expired)

        # Set entry
        self.cache.set(url, "GET", None, {"name": "hello"}, etag='"12345"', ttl=5)
        data, etag, expired = self.cache.get(url)
        self.assertEqual(data, {"name": "hello"})
        self.assertEqual(etag, '"12345"')
        self.assertFalse(expired)

    def test_cache_ttl_expiration(self):
        url = "https://api.github.com/repos/octocat/ttl-test"
        self.cache.set(url, "GET", None, {"status": "ok"}, ttl=1)

        data, _, expired = self.cache.get(url)
        self.assertFalse(expired)

        time.sleep(1.2)
        data, _, expired = self.cache.get(url)
        self.assertEqual(data, {"status": "ok"})
        self.assertTrue(expired)

    def test_cache_touch_revalidation(self):
        url = "https://api.github.com/repos/octocat/touch-test"
        self.cache.set(url, "GET", None, {"count": 10}, ttl=1)
        time.sleep(1.1)
        _, _, expired = self.cache.get(url)
        self.assertTrue(expired)

        # 304 revalidation touches the entry
        self.cache.touch(url, ttl=10)
        data, _, expired = self.cache.get(url)
        self.assertEqual(data, {"count": 10})
        self.assertFalse(expired)

    def test_clear_cache(self):
        self.cache.set("https://api.github.com/1", "GET", None, {"id": 1})
        self.cache.set("https://api.github.com/2", "GET", None, {"id": 2})
        count = self.cache.clear()
        self.assertEqual(count, 2)
        data, _, _ = self.cache.get("https://api.github.com/1")
        self.assertIsNone(data)


class TestAnalyzerCachingIntegration(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_fresh_cache_avoids_urlopen(self):
        analyzer = GitHubOrgActivityAnalyzer(
            token="dummy",
            owner="test-org",
            repo="repo1",
            cache_dir=self.test_dir,
            cache_ttl=60,
        )
        url = "https://api.github.com/repos/test-org/repo1"
        analyzer.cache.set(url, "GET", None, {"name": "repo1", "default_branch": "main"})

        # Urllib urlopen should not be called when unexpired cache hit exists
        import urllib.request
        orig_urlopen = urllib.request.urlopen
        try:
            urllib.request.urlopen = MagicMock(side_effect=AssertionError("Should not call urlopen on cache hit"))
            repos = analyzer.get_repositories()
            self.assertEqual(len(repos), 1)
            self.assertEqual(repos[0]["name"], "repo1")
        finally:
            urllib.request.urlopen = orig_urlopen


if __name__ == "__main__":
    unittest.main()
