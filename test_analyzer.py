import unittest
from unittest.mock import MagicMock
from analyzer import GitHubOrgActivityAnalyzer, GitHubTargetScope


class TestGitHubTargetScope(unittest.TestCase):

    def test_parse_url(self):
        owner, repo, kind = GitHubTargetScope.parse("https://github.com/octocat/my-repo")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "my-repo")
        self.assertEqual(kind, "single_repo")

    def test_parse_owner_repo(self):
        owner, repo, kind = GitHubTargetScope.parse("octocat/my-repo")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "my-repo")
        self.assertEqual(kind, "single_repo")

    def test_parse_short_repo_with_default_owner(self):
        owner, repo, kind = GitHubTargetScope.parse("my-repo", default_owner="octocat")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "my-repo")
        self.assertEqual(kind, "single_repo")

    def test_parse_org(self):
        owner, repo, kind = GitHubTargetScope.parse("google")
        self.assertEqual(owner, "google")
        self.assertIsNone(repo)
        self.assertEqual(kind, "org_or_user")


class TestGitHubOrgActivityAnalyzer(unittest.TestCase):

    def test_analyze_pull_requests_review_parsing(self):
        analyzer = GitHubOrgActivityAnalyzer(token="dummy", owner="test-org", repo="repo1")

        mock_graphql_data = {
            "search": {
                "issueCount": 1,
                "nodes": [
                    {
                        "number": 42,
                        "title": "Add telemetry",
                        "url": "https://github.com/test-org/repo1/pull/42",
                        "state": "OPEN",
                        "createdAt": "2026-03-01T10:00:00Z",
                        "mergedAt": None,
                        "closedAt": None,
                        "repository": {"name": "repo1", "owner": {"login": "test-org"}},
                        "author": {"login": "alice"},
                        "additions": 120,
                        "deletions": 15,
                        "changedFiles": 4,
                        "reviews": {
                            "nodes": [
                                {
                                    "author": {"login": "bob"},
                                    "state": "APPROVED",
                                    "submittedAt": "2026-03-01T12:00:00Z",
                                    "body": "LGTM",
                                },
                            ]
                        },
                        "reviewRequests": {
                            "nodes": [
                                {"requestedReviewer": {"login": "dave"}}
                            ]
                        },
                        "reviewThreads": {
                            "nodes": [
                                {
                                    "id": "thread_1",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "path": "auth.py",
                                    "line": 42,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "c1",
                                                "author": {"login": "carol"},
                                                "body": "Check token expiration edge case",
                                                "createdAt": "2026-03-01T11:00:00Z",
                                                "url": "https://github.com/test-org/repo1/pull/42#r1",
                                            }
                                        ]
                                    },
                                },
                                {
                                    "id": "thread_2",
                                    "isResolved": True,
                                    "isOutdated": False,
                                    "path": "main.py",
                                    "line": 10,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "id": "c2",
                                                "author": {"login": "bob"},
                                                "body": "Typo in comment",
                                                "createdAt": "2026-03-01T11:30:00Z",
                                                "url": "https://github.com/test-org/repo1/pull/42#r2",
                                            }
                                        ]
                                    },
                                },
                            ]
                        },
                    }
                ],
            }
        }

        analyzer._graphql = MagicMock(return_value=mock_graphql_data)

        prs = analyzer.analyze_pull_requests(author_filter="alice")
        self.assertEqual(len(prs), 1)
        pr = prs[0]
        self.assertEqual(pr["number"], 42)
        self.assertEqual(pr["repo"], "test-org/repo1")
        self.assertEqual(pr["lines_added"], 120)
        self.assertEqual(len(pr["reviews"]), 1)
        self.assertEqual(pr["reviews"][0]["reviewer"], "bob")
        self.assertEqual(pr["reviews"][0]["state"], "APPROVED")

        # Verify unresolved review threads observability
        self.assertEqual(pr["unresolved_threads_count"], 1)
        self.assertEqual(pr["resolved_threads_count"], 1)
        self.assertEqual(len(pr["review_threads"]), 2)
        self.assertEqual(pr["reviewer_unresolved_counts"], {"carol": 1})
        unresolved_thread = [t for t in pr["review_threads"] if not t["is_resolved"]][0]
        self.assertEqual(unresolved_thread["thread_initiator"], "carol")
        self.assertEqual(unresolved_thread["waiting_on"], "author")


if __name__ == "__main__":
    unittest.main()
