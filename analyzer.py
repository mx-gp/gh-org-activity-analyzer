import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from auth import GitHubAuthManager

GITHUB_REST_API = "https://api.github.com"
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"


class GitHubTargetScope:
    """Parses input strings into structured target scope:

    - Full URL: 'https://github.com/octocat/my-repo' -> owner='octocat', repo='my-repo'
    - 'owner/repo': 'octocat/my-repo' -> owner='octocat', repo='my-repo'
    - Single identifier: 'my-repo' (when default_owner provided) or 'my-org'
    """

    @staticmethod
    def parse(
        target: Optional[str],
        default_owner: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str], str]:
        """Returns (owner, repo_name, scope_kind)

        scope_kind in ['single_repo', 'org_or_user', 'all_user_repos']
        """
        if not target or not target.strip():
            return (default_owner, None, "all_user_repos" if default_owner else "all")

        clean = target.strip()
        clean = re.sub(r"\.git/?$", "", clean)
        clean = clean.rstrip("/")

        url_match = re.search(r"github\.com/([^/]+)/([^/]+)", clean)
        if url_match:
            return (url_match.group(1), url_match.group(2), "single_repo")

        if "/" in clean:
            parts = clean.split("/")
            if len(parts) == 2 and parts[0] and parts[1]:
                return (parts[0], parts[1], "single_repo")

        if default_owner and clean != default_owner:
            return (default_owner, clean, "single_repo")

        return (clean, None, "org_or_user")


class GitHubOrgActivityAnalyzer:
    """Comprehensive developer activity, code review, and branch telemetry analyzer."""

    def __init__(
        self,
        token: str,
        owner: Optional[str] = None,
        repo: Optional[str] = None,
        is_org: bool = False,
    ):
        self.token = token
        self.owner = owner.strip() if owner and owner.strip() else None
        self.repo = repo.strip() if repo and repo.strip() else None
        self.is_org = is_org
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gh-org-activity-analyzer",
            "Content-Type": "application/json",
        }

    def _http_request(self, url: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Any:
        if not url.startswith("https://api.github.com"):
            raise ValueError(f"Untrusted URL scheme or host: {url}")

        encoded_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=encoded_data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:  # nosec B310
                resp_bytes = resp.read()
                if not resp_bytes:
                    return None
                return json.loads(resp_bytes.decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} error for {url}: {err_body}")

    def _graphql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        data = self._http_request(
            GITHUB_GRAPHQL_API,
            method="POST",
            data={"query": query, "variables": variables},
        )
        if not data:
            return {}
        if "errors" in data:
            raise RuntimeError(f"GraphQL error: {data['errors']}")
        return data.get("data", {})

    def get_repositories(self, include_forks: bool = False) -> List[Dict[str, Any]]:
        """Dynamically list all targeted repositories."""
        if self.owner and self.repo:
            url = f"{GITHUB_REST_API}/repos/{self.owner}/{self.repo}"
            try:
                repo_data = self._http_request(url)
                if repo_data and "name" in repo_data:
                    return [{
                        "name": repo_data["name"],
                        "owner": repo_data.get("owner", {}).get("login", self.owner),
                        "full_name": repo_data.get("full_name", f"{self.owner}/{self.repo}"),
                        "default_branch": repo_data.get("default_branch", "main"),
                        "private": repo_data.get("private", False),
                    }]
            except Exception:
                pass
            return [{
                "name": self.repo,
                "owner": self.owner,
                "full_name": f"{self.owner}/{self.repo}",
                "default_branch": "main",
                "private": False,
            }]

        repos = []
        page = 1
        seen_names = set()

        while True:
            if self.is_org and self.owner:
                url = f"{GITHUB_REST_API}/orgs/{self.owner}/repos?type=all&per_page=100&page={page}"
            else:
                url = f"{GITHUB_REST_API}/user/repos?affiliation=owner,collaborator,organization_member&per_page=100&page={page}"

            items = self._http_request(url)
            if not items or not isinstance(items, list):
                if not self.is_org and self.owner and page == 1:
                    fallback_url = f"{GITHUB_REST_API}/users/{self.owner}/repos?type=all&per_page=100&page=1"
                    items = self._http_request(fallback_url)
                    if not items or not isinstance(items, list):
                        break
                else:
                    break

            for repo in items:
                repo_owner = repo.get("owner", {}).get("login", "")
                if self.owner and not self.is_org and repo_owner.lower() != self.owner.lower():
                    continue

                if repo.get("archived"):
                    continue
                if not include_forks and repo.get("fork"):
                    continue

                repo_name = repo["name"]
                if repo_name in seen_names:
                    continue
                seen_names.add(repo_name)

                repos.append({
                    "name": repo_name,
                    "owner": repo_owner,
                    "full_name": repo.get("full_name", f"{repo_owner}/{repo_name}"),
                    "default_branch": repo.get("default_branch", "main"),
                    "private": repo.get("private", False),
                })
            page += 1
            if len(items) < 100:
                break
        return repos

    def analyze_pull_requests(self, author_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Audit PRs with reviewer decisions, turnaround timestamps, and lines modified."""
        query = """
        query($searchQuery: String!, $limit: Int!) {
          search(query: $searchQuery, type: ISSUE, first: $limit) {
            issueCount
            nodes {
              ... on PullRequest {
                number
                title
                url
                state
                createdAt
                mergedAt
                closedAt
                repository { name, owner { login } }
                author { login }
                additions
                deletions
                changedFiles
                reviews(first: 50) {
                  nodes {
                    author { login }
                    state
                    submittedAt
                    body
                  }
                }
                reviewRequests(first: 20) {
                  nodes {
                    requestedReviewer {
                      ... on User { login }
                      ... on Team { name }
                    }
                  }
                }
              }
            }
          }
        }
        """
        parts = ["type:pr"]
        if self.owner and self.repo:
            parts.append(f"repo:{self.owner}/{self.repo}")
        elif self.is_org and self.owner:
            parts.append(f"org:{self.owner}")
        elif self.owner:
            parts.append(f"user:{self.owner}")

        if author_filter and author_filter.strip():
            parts.append(f"author:{author_filter.strip()}")

        search_query = " ".join(parts)
        res = self._graphql(query, {"searchQuery": search_query, "limit": limit})
        nodes = res.get("search", {}).get("nodes", [])

        analyzed_prs = []
        for pr in nodes:
            reviews_data = []
            for r in pr.get("reviews", {}).get("nodes", []):
                reviews_data.append({
                    "reviewer": r.get("author", {}).get("login", "unknown") if r.get("author") else "ghost",
                    "state": r.get("state"),
                    "submitted_at": r.get("submittedAt"),
                })

            pending_reviewers = []
            for req in pr.get("reviewRequests", {}).get("nodes", []):
                rev = req.get("requestedReviewer") or {}
                pending_reviewers.append(rev.get("login") or rev.get("name") or "unknown")

            repo_info = pr.get("repository") or {}
            repo_owner = repo_info.get("owner", {}).get("login", "")
            repo_name = repo_info.get("name", "")
            full_repo = f"{repo_owner}/{repo_name}" if repo_owner else repo_name
            author_login = pr.get("author", {}).get("login", "unknown") if pr.get("author") else "ghost"

            analyzed_prs.append({
                "repo": full_repo,
                "number": pr["number"],
                "title": pr["title"],
                "author": author_login,
                "url": pr["url"],
                "state": pr["state"],
                "created_at": pr["createdAt"],
                "merged_at": pr["mergedAt"],
                "closed_at": pr.get("closedAt"),
                "lines_added": pr.get("additions", 0),
                "lines_deleted": pr.get("deletions", 0),
                "changed_files": pr.get("changedFiles", 0),
                "reviews": reviews_data,
                "pending_reviewers": pending_reviewers,
            })
        return analyzed_prs

    def analyze_issues(self, author_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Audit issues with optional author filter."""
        query = """
        query($searchQuery: String!, $limit: Int!) {
          search(query: $searchQuery, type: ISSUE, first: $limit) {
            issueCount
            nodes {
              ... on Issue {
                number
                title
                url
                state
                createdAt
                closedAt
                repository { name, owner { login } }
                author { login }
                comments { totalCount }
              }
            }
          }
        }
        """
        parts = ["type:issue"]
        if self.owner and self.repo:
            parts.append(f"repo:{self.owner}/{self.repo}")
        elif self.is_org and self.owner:
            parts.append(f"org:{self.owner}")
        elif self.owner:
            parts.append(f"user:{self.owner}")

        if author_filter and author_filter.strip():
            parts.append(f"author:{author_filter.strip()}")

        search_query = " ".join(parts)
        res = self._graphql(query, {"searchQuery": search_query, "limit": limit})
        nodes = res.get("search", {}).get("nodes", [])

        analyzed_issues = []
        for issue in nodes:
            repo_info = issue.get("repository") or {}
            repo_owner = repo_info.get("owner", {}).get("login", "")
            repo_name = repo_info.get("name", "")
            full_repo = f"{repo_owner}/{repo_name}" if repo_owner else repo_name
            author_login = issue.get("author", {}).get("login", "unknown") if issue.get("author") else "ghost"

            analyzed_issues.append({
                "repo": full_repo,
                "number": issue["number"],
                "title": issue["title"],
                "author": author_login,
                "url": issue["url"],
                "state": issue["state"],
                "created_at": issue["createdAt"],
                "closed_at": issue["closedAt"],
                "comments_count": issue.get("comments", {}).get("totalCount", 0),
            })
        return analyzed_issues

    def analyze_author_comments(self, author_filter: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
        """Extract individual conversation and review discussion comments written by the author on PRs and Issues."""
        parts = []
        if self.owner and self.repo:
            parts.append(f"repo:{self.owner}/{self.repo}")
        elif self.is_org and self.owner:
            parts.append(f"org:{self.owner}")
        elif self.owner:
            parts.append(f"user:{self.owner}")

        if author_filter and author_filter.strip():
            parts.append(f"commenter:{author_filter.strip()}")

        if not parts:
            return []

        search_query = " ".join(parts)
        query = """
        query($searchQuery: String!, $limit: Int!) {
          search(query: $searchQuery, type: ISSUE, first: $limit) {
            issueCount
            nodes {
              ... on PullRequest {
                number
                title
                url
                repository { name, owner { login } }
                comments(last: 20) {
                  nodes {
                    author { login }
                    body
                    createdAt
                    url
                  }
                }
              }
              ... on Issue {
                number
                title
                url
                repository { name, owner { login } }
                comments(last: 20) {
                  nodes {
                    author { login }
                    body
                    createdAt
                    url
                  }
                }
              }
            }
          }
        }
        """
        res = self._graphql(query, {"searchQuery": search_query, "limit": limit})
        nodes = res.get("search", {}).get("nodes", [])

        user_filter_lower = author_filter.strip().lower() if author_filter else None
        extracted_comments = []

        for item in nodes:
            repo_info = item.get("repository") or {}
            repo_owner = repo_info.get("owner", {}).get("login", "")
            repo_name = repo_info.get("name", "")
            full_repo = f"{repo_owner}/{repo_name}" if repo_owner else repo_name
            target_title = f"#{item.get('number')} {item.get('title')}"
            target_url = item.get("url")

            for c in item.get("comments", {}).get("nodes", []):
                comm_author = c.get("author", {}).get("login", "unknown") if c.get("author") else "ghost"
                if user_filter_lower and comm_author.lower() != user_filter_lower:
                    continue

                extracted_comments.append({
                    "repo": full_repo,
                    "target_title": target_title,
                    "target_url": target_url,
                    "author": comm_author,
                    "comment_url": c.get("url"),
                    "created_at": c.get("createdAt"),
                    "body": c.get("body", "").strip(),
                })

        # Sort descending by date
        extracted_comments.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return extracted_comments

    def analyze_branches(
        self, repo_owner: str, repo_name: str, default_branch: str, user_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect branches, audit commits with optional author filter, and determine full PR relationship."""
        all_prs_url = f"{GITHUB_REST_API}/repos/{repo_owner}/{repo_name}/pulls?state=all&per_page=100"
        prs_items = self._http_request(all_prs_url)
        pr_map = {}
        if isinstance(prs_items, list):
            for pr in prs_items:
                head_ref = pr.get("head", {}).get("ref")
                if head_ref and head_ref not in pr_map:
                    pr_map[head_ref] = {
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "state": pr.get("state"),
                        "is_merged": bool(pr.get("merged_at")),
                        "url": pr.get("html_url"),
                    }

        branches_url = f"{GITHUB_REST_API}/repos/{repo_owner}/{repo_name}/branches?per_page=100"
        branches = self._http_request(branches_url)
        if not isinstance(branches, list):
            return []

        audit_branches = []
        for b in branches:
            branch_name = b["name"]
            if branch_name == default_branch:
                continue

            associated_pr = pr_map.get(branch_name)
            if not associated_pr:
                pr_status = "NO_PR_EVER"
                status_label = "Never had a PR"
            elif associated_pr["is_merged"]:
                pr_status = "MERGED_STALE"
                status_label = f"PR #{associated_pr['number']} Merged (Branch not deleted)"
            elif associated_pr["state"] == "closed":
                pr_status = "CLOSED_UNMERGED"
                status_label = f"PR #{associated_pr['number']} Closed Unmerged"
            else:
                pr_status = "OPEN_PR"
                status_label = f"Active Open PR #{associated_pr['number']}"

            commits_url = f"{GITHUB_REST_API}/repos/{repo_owner}/{repo_name}/commits?sha={urllib.parse.quote(branch_name)}&per_page=30"
            commits = self._http_request(commits_url)
            if not isinstance(commits, list):
                continue

            matched_commits = []
            for c in commits:
                login = c.get("author", {}).get("login") if c.get("author") else None
                author_name = c.get("commit", {}).get("author", {}).get("name", "")
                commit_author = login or author_name

                if user_filter and user_filter.strip():
                    filter_lower = user_filter.strip().lower()
                    if filter_lower not in str(login or "").lower() and filter_lower not in author_name.lower():
                        continue

                matched_commits.append({
                    "sha": c["sha"][:7],
                    "author": commit_author,
                    "date": c.get("commit", {}).get("author", {}).get("date"),
                    "message": c.get("commit", {}).get("message", "").split("\n")[0],
                })

            if matched_commits:
                audit_branches.append({
                    "repo": f"{repo_owner}/{repo_name}",
                    "branch": branch_name,
                    "pr_status": pr_status,
                    "status_label": status_label,
                    "associated_pr": associated_pr,
                    "matched_commits_count": len(matched_commits),
                    "commits": matched_commits,
                })

        return audit_branches


def main():
    parser = argparse.ArgumentParser(description="GitHub Activity, Review & Branch Analyzer")
    parser.add_argument("--target", help="Repository URL (https://github.com/owner/repo), owner/repo, or Org name")
    parser.add_argument("--author", help="Author/user handle filter (optional: leave empty for all authors)")
    parser.add_argument("--org", help="Explicit Organization name")
    parser.add_argument("--token", help="Direct GitHub Personal Access Token")
    parser.add_argument("--app-id", help="GitHub App ID")
    parser.add_argument("--private-key-file", help="Path to GitHub App private key (.pem) file")
    parser.add_argument("--installation-id", help="GitHub App Installation ID")
    parser.add_argument("--include-branches", action="store_true", default=True, help="Scan branches")
    parser.add_argument("--json", action="store_true", help="Output results formatted as JSON")
    args = parser.parse_args()

    private_pem = None
    if args.private_key_file:
        with open(args.private_key_file, "r") as f:
            private_pem = f.read()

    try:
        token, auth_method, meta = GitHubAuthManager.resolve_token(
            token_input=args.token,
            app_id=args.app_id,
            private_key_pem=private_pem,
            installation_id=args.installation_id,
        )
    except Exception as e:
        print(f"Authentication Error: {e}", file=sys.stderr)
        sys.exit(1)

    auth_user = meta.get("user_login")
    owner, repo, scope_kind = GitHubTargetScope.parse(args.target or args.org, default_owner=auth_user)
    is_org = bool(args.org)

    analyzer = GitHubOrgActivityAnalyzer(token=token, owner=owner, repo=repo, is_org=is_org)

    repos = analyzer.get_repositories()
    prs = analyzer.analyze_pull_requests(author_filter=args.author)
    issues = analyzer.analyze_issues(author_filter=args.author)
    comments = analyzer.analyze_author_comments(author_filter=args.author)

    all_branches = []
    if args.include_branches:
        for r in repos:
            b_list = analyzer.analyze_branches(
                repo_owner=r.get("owner", owner),
                repo_name=r["name"],
                default_branch=r["default_branch"],
                user_filter=args.author
            )
            all_branches.extend(b_list)

    scope_display = f"Repo: {owner}/{repo}" if repo else f"Owner: {owner}" if owner else "All User Repos"

    output = {
        "scope": scope_display,
        "author_filter": args.author or "ALL",
        "auth_method": auth_method,
        "pull_requests": prs,
        "issues": issues,
        "comments": comments,
        "branches": all_branches,
    }

    if args.json:
        print(json.dumps(output, indent=2))
        return

    print(f"\n========================================================")
    print(f" Target Scope: {scope_display} | Author Filter: {args.author or 'ALL'}")
    print(f" Active Authentication: {auth_method} (User: @{auth_user or 'unknown'})")
    print(f"========================================================\n")

    print(f"--- [1] PULL REQUESTS & REVIEW AUDIT ({len(prs)} found) ---")
    for pr in prs:
        print(f"\n* [{pr['repo']}] PR #{pr['number']} ({pr['state']}) by @{pr['author']}: {pr['title']}")
        print(f"  Diff: +{pr['lines_added']} / -{pr['lines_deleted']} lines across {pr['changed_files']} files")
        if pr["reviews"]:
            print("  Reviews:")
            for r in pr["reviews"]:
                print(f"    - @{r['reviewer']}: {r['state']} (at {r['submitted_at']})")

    print(f"\n--- [2] COMMENTS POSTED ({len(comments)} found) ---")
    for c in comments:
        print(f"* [{c['repo']}] On {c['target_title']} by @{c['author']}: {c['body'][:60]}... ({c['created_at']})")

    print(f"\n--- [3] ISSUES AUDIT ({len(issues)} found) ---")
    for issue in issues:
        print(f"* [{issue['repo']}] Issue #{issue['number']} ({issue['state']}) by @{issue['author']}: {issue['title']}")

    print(f"\n--- [4] BRANCHES AUDIT ({len(all_branches)} branches) ---")
    for b in all_branches:
        print(f"\n* Repo: {b['repo']} | Branch: {b['branch']} [{b['status_label']}] ({b['matched_commits_count']} commits)")


if __name__ == "__main__":
    main()
