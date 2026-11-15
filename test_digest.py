import unittest
from unittest.mock import patch, MagicMock
from digest import generate_markdown_digest, send_webhook_digest

class TestDigest(unittest.TestCase):
    def setUp(self):
        self.sample_report = {
            "scope": "octocat/hello-world",
            "target_type": "repository",
            "author_filter": "octocat",
            "pull_requests": [
                {
                    "number": 42,
                    "title": "Add exciting new feature",
                    "author": "octocat",
                    "url": "https://github.com/octocat/hello-world/pull/42",
                    "state": "OPEN",
                    "lines_added": 120,
                    "lines_deleted": 15,
                    "changed_files": 3,
                    "sla_status": "HEALTHY",
                    "reviews": [
                        {"reviewer": "alice", "state": "APPROVED"}
                    ],
                    "unresolved_threads_count": 1,
                    "review_threads": [
                        {
                            "is_resolved": False,
                            "path": "main.py",
                            "line": 10,
                            "thread_initiator": "alice",
                            "waiting_on": "author",
                            "comments": [
                                {"author": "alice", "body": "Please add docstring here"}
                            ]
                        }
                    ]
                }
            ],
            "issues": [
                {"number": 1, "title": "Bug in login"}
            ],
            "comments": [
                {"author": "octocat", "body": "Fixed in next commit"}
            ],
            "branches_without_pr": [
                {
                    "branch": "feat/experimental",
                    "status_label": "Never had a PR",
                    "matched_commits_count": 2
                }
            ]
        }

    def test_generate_markdown_digest(self):
        md = generate_markdown_digest(self.sample_report)
        self.assertIn("# 📊 GitHub Activity Digest: octocat/hello-world", md)
        self.assertIn("**Filtered Author**: `@octocat`", md)
        self.assertIn("## 📈 Executive Summary", md)
        self.assertIn("1 total (0 merged, 1 open, 0 closed)", md)
        self.assertIn("1 unresolved review discussion thread(s)", md)
        self.assertIn("## 💬 Review Bottlenecks & Unresolved Threads", md)
        self.assertIn("main.py:10", md)
        self.assertIn("Please add docstring here", md)
        self.assertIn("## 🚀 Pull Requests", md)
        self.assertIn("[#42 Add exciting new feature]", md)
        self.assertIn("SLA: `HEALTHY`", md)
        self.assertIn("## ⚠️ Branches Without Pull Requests", md)
        self.assertIn("feat/experimental", md)

    @patch("urllib.request.urlopen")
    def test_send_webhook_digest_slack(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        success = send_webhook_digest("https://hooks.slack.com/services/T00/B00/X00", "# Digest Content")
        self.assertTrue(success)
        self.assertTrue(mock_urlopen.called)

    @patch("urllib.request.urlopen")
    def test_send_webhook_digest_discord(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 204
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        success = send_webhook_digest("https://discord.com/api/webhooks/123/abc", "# Discord Digest")
        self.assertTrue(success)
        self.assertTrue(mock_urlopen.called)

    def test_send_webhook_empty_url(self):
        with self.assertRaises(ValueError):
            send_webhook_digest("", "content")

if __name__ == "__main__":
    unittest.main()
