import unittest
from unittest.mock import MagicMock
from analyzer import GitHubOrgActivityAnalyzer


class TestGitHubOrgActivityAnalyzer(unittest.TestCase):

    def test_analyze_pull_requests_review_parsing(self):
        analyzer = GitHubOrgActivityAnalyzer(token="dummy", org="test-org")

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
                        "repository": {"name": "repo1"},
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
                                {
                                    "author": {"login": "carol"},
                                    "state": "CHANGES_REQUESTED",
                                    "submittedAt": "2026-03-01T13:00:00Z",
                                    "body": "Please add tests",
                                },
                            ]
                        },
                        "reviewRequests": {
                            "nodes": [
                                {"requestedReviewer": {"login": "dave"}}
                            ]
                        },
                    }
                ],
            }
        }

        analyzer._graphql = MagicMock(return_value=mock_graphql_data)

        prs = analyzer.analyze_pull_requests(author="alice")
        self.assertEqual(len(prs), 1)
        pr = prs[0]
        self.assertEqual(pr["number"], 42)
        self.assertEqual(pr["repo"], "repo1")
        self.assertEqual(pr["lines_added"], 120)
        self.assertEqual(len(pr["reviews"]), 2)
        self.assertEqual(pr["reviews"][0]["reviewer"], "bob")
        self.assertEqual(pr["reviews"][0]["state"], "APPROVED")
        self.assertEqual(pr["reviews"][1]["reviewer"], "carol")
        self.assertEqual(pr["reviews"][1]["state"], "CHANGES_REQUESTED")
        self.assertEqual(pr["pending_reviewers"], ["dave"])

    def test_analyze_branches_without_prs_filtering(self):
        analyzer = GitHubOrgActivityAnalyzer(token="dummy", org="test-org")

        def mock_http_request(url, **kwargs):
            if "/pulls" in url:
                return [{"head": {"ref": "feature/branch-with-pr"}}]
            elif "/branches" in url:
                return [
                    {"name": "main"},
                    {"name": "feature/branch-with-pr"},
                    {"name": "feature/orphan-branch"},
                ]
            elif "/commits" in url:
                return [
                    {
                        "sha": "abc1234567890",
                        "author": {"login": "alice"},
                        "commit": {
                            "author": {"name": "Alice Developer", "date": "2026-03-02T08:00:00Z"},
                            "message": "Work in progress commit",
                        },
                    },
                    {
                        "sha": "def9876543210",
                        "author": {"login": "stranger"},
                        "commit": {
                            "author": {"name": "Stranger", "date": "2026-03-01T08:00:00Z"},
                            "message": "Other work",
                        },
                    },
                ]
            return []

        analyzer._http_request = MagicMock(side_effect=mock_http_request)

        unlinked = analyzer.analyze_branches_without_prs(
            repo="backend", default_branch="main", user_filter="alice"
        )

        self.assertEqual(len(unlinked), 1)
        branch = unlinked[0]
        self.assertEqual(branch["repo"], "backend")
        self.assertEqual(branch["branch"], "feature/orphan-branch")
        self.assertEqual(branch["matched_commits_count"], 1)
        self.assertEqual(branch["commits"][0]["author"], "alice")
        self.assertEqual(branch["commits"][0]["sha"], "abc1234")


if __name__ == "__main__":
    unittest.main()
