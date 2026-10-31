import unittest
from unittest.mock import patch, MagicMock
from auth import GitHubAuthManager


class TestGitHubAuthManager(unittest.TestCase):

    def test_resolve_token_direct_input(self):
        token, method, meta = GitHubAuthManager.resolve_token(token_input="ghp_1234567890abcdef")
        self.assertEqual(token, "ghp_1234567890abcdef")
        self.assertEqual(method, "Personal Access Token (User Input)")
        self.assertEqual(meta["masked"], "ghp_...cdef")

    @patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_envtoken99999999"})
    def test_resolve_token_environment(self):
        token, method, meta = GitHubAuthManager.resolve_token()
        self.assertEqual(token, "ghp_envtoken99999999")
        self.assertEqual(method, "Environment Variable (GITHUB_TOKEN)")

    @patch("auth.GitHubAuthManager.get_gh_cli_token", return_value="gho_cli_token_abc")
    @patch.dict("os.environ", {}, clear=True)
    def test_resolve_token_gh_cli(self, mock_cli):
        token, method, meta = GitHubAuthManager.resolve_token()
        self.assertEqual(token, "gho_cli_token_abc")
        self.assertEqual(method, "GitHub CLI (gh auth)")

    @patch("auth.GitHubAuthManager.get_app_installation_token", return_value="ghs_app_installation_token")
    def test_resolve_token_github_app(self, mock_exchange):
        token, method, meta = GitHubAuthManager.resolve_token(
            app_id="12345",
            private_key_pem="fake-pem",
            installation_id="67890",
        )
        self.assertEqual(token, "ghs_app_installation_token")
        self.assertEqual(method, "GitHub App")
        self.assertEqual(meta["app_id"], "12345")
        self.assertEqual(meta["installation_id"], "67890")


if __name__ == "__main__":
    unittest.main()
