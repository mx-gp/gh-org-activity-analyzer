import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from auth import GitHubAuthManager

GITHUB_REST_API = "https://api.github.com"
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"


class GitHubOrgActivityAnalyzer:
    """Comprehensive analyzer for GitHub organizations and individual user accounts:

    - Pull requests by author & detailed review audit.
    - Issues by author.
    - Commits across repositories by author.
    - Branches without PRs and unmerged commits by author/users.
    """

    def __init__(self, token: str, org: Optional[str] = None, user: Optional[str] = None):
        self.org = org.strip() if org and org.strip() else None
        self.user = user.strip() if user and user.strip() else None
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gh-org-activity-analyzer",
            "Content-Type": "application/json",
        }

    @property
    def target_owner(self) -> str:
        """Returns the active scope (organization name or personal user handle)."""
        return self.org or self.user or ""

    def _http_request(self, url: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Any:
        encoded_data = json.dumps(data).encode("utf-8") if data else None
        req = urllib.request.Request(url, data=encoded_data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
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

    def get_organization_repositories(self, include_forks: bool = False) -> List[Dict[str, Any]]:
        """Dynamically list all active repositories across the organization or user account."""
        repos = []
        page = 1
        seen_names = set()

        while True:
            if self.org:
                url = f"{GITHUB_REST_API}/orgs/{self.org}/repos?type=all&per_page=100&page={page}"
            else:
                # If personal user scope: fetch all repositories accessible to the user (including private & affiliated)
                url = f"{GITHUB_REST_API}/user/repos?affiliation=owner,collaborator,organization_member&per_page=100&page={page}"

            items = self._http_request(url)
            if not items or not isinstance(items, list):
                # If /user/repos fails or returns empty because token is unauthenticated, fallback to public /users/{user}/repos
                if not self.org and self.user and page == 1:
                    fallback_url = f"{GITHUB_REST_API}/users/{self.user}/repos?type=all&per_page=100&page=1"
                    items = self._http_request(fallback_url)
                    if not items or not isinstance(items, list):
                        break
                else:
                    break

            for repo in items:
                repo_owner = repo.get("owner", {}).get("login", "")
                # If scoped to a specific user, filter to that owner
                if self.user and repo_owner.lower() != self.user.lower():
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

    def analyze_pull_requests(self, author: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Audit PRs by author and analyze reviewers, review states, timestamps, and conversation comments."""
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
                repository { name }
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
        scope_filter = f"org:{self.org}" if self.org else f"user:{self.user}" if self.user else ""
        search_query = f"{scope_filter} type:pr author:{author}".strip()
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

            analyzed_prs.append({
                "repo": pr["repository"]["name"],
                "number": pr["number"],
                "title": pr["title"],
                "url": pr["url"],
                "state": pr["state"],
                "created_at": pr["createdAt"],
                "merged_at": pr["mergedAt"],
                "lines_added": pr.get("additions", 0),
                "lines_deleted": pr.get("deletions", 0),
                "changed_files": pr.get("changedFiles", 0),
                "reviews": reviews_data,
                "pending_reviewers": pending_reviewers,
            })
        return analyzed_prs

    def analyze_issues(self, author: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Audit issues created by author."""
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
                repository { name }
                comments { totalCount }
              }
            }
          }
        }
        """
        scope_filter = f"org:{self.org}" if self.org else f"user:{self.user}" if self.user else ""
        search_query = f"{scope_filter} type:issue author:{author}".strip()
        res = self._graphql(query, {"searchQuery": search_query, "limit": limit})
        nodes = res.get("search", {}).get("nodes", [])

        analyzed_issues = []
        for issue in nodes:
            analyzed_issues.append({
                "repo": issue["repository"]["name"],
                "number": issue["number"],
                "title": issue["title"],
                "url": issue["url"],
                "state": issue["state"],
                "created_at": issue["createdAt"],
                "closed_at": issue["closedAt"],
                "comments_count": issue.get("comments", {}).get("totalCount", 0),
            })
        return analyzed_issues

    def analyze_branches_without_prs(
        self, repo: str, default_branch: str, user_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Detect branches lacking PRs or having unmerged work, with full PR association audit."""
        owner = self.target_owner
        if not owner:
            return []

        # 1. Fetch all PRs (both open and closed) to map branch relationship accurately
        all_prs_url = f"{GITHUB_REST_API}/repos/{owner}/{repo}/pulls?state=all&per_page=100"
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

        # 2. Fetch all branches
        branches_url = f"{GITHUB_REST_API}/repos/{owner}/{repo}/branches?per_page=100"
        branches = self._http_request(branches_url)
        if not isinstance(branches, list):
            return []

        audit_branches = []
        for b in branches:
            branch_name = b["name"]
            if branch_name == default_branch:
                continue

            associated_pr = pr_map.get(branch_name)
            
            # Determine branch status:
            # - "NO_PR_EVER": Branch has never had a PR created for it
            # - "CLOSED_UNMERGED": PR was closed without merging
            # - "MERGED_STALE": PR was merged, but branch was not deleted
            # - "OPEN_PR": Currently has an active open PR
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

            # 3. Retrieve commits on this branch
            commits_url = f"{GITHUB_REST_API}/repos/{owner}/{repo}/commits?sha={urllib.parse.quote(branch_name)}&per_page=30"
            commits = self._http_request(commits_url)
            if not isinstance(commits, list):
                continue

            matched_commits = []
            for c in commits:
                login = c.get("author", {}).get("login") if c.get("author") else None
                author_name = c.get("commit", {}).get("author", {}).get("name", "")
                commit_author = login or author_name

                if user_filter:
                    filter_lower = user_filter.lower()
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
                    "repo": repo,
                    "branch": branch_name,
                    "pr_status": pr_status,
                    "status_label": status_label,
                    "associated_pr": associated_pr,
                    "matched_commits_count": len(matched_commits),
                    "commits": matched_commits,
                })

        return audit_branches


def main():
    parser = argparse.ArgumentParser(description="GitHub Activity, Review & Branch Analyzer (Org or User Scope)")
    parser.add_argument("--org", help="Target GitHub Organization (leave empty for personal user account)")
    parser.add_argument("--user", help="Target GitHub Username/Owner (if analyzing personal/individual user repos)")
    parser.add_argument("--author", required=True, help="Target author/user handle to filter")
    parser.add_argument("--token", help="Direct GitHub Personal Access Token (optional if using gh cli / env / app)")
    parser.add_argument("--app-id", help="GitHub App ID")
    parser.add_argument("--private-key-file", help="Path to GitHub App private key (.pem) file")
    parser.add_argument("--installation-id", help="GitHub App Installation ID")
    parser.add_argument("--include-branches-without-pr", action="store_true", help="Scan unlinked branches without PRs")
    parser.add_argument("--json", action="store_true", help="Output results formatted as JSON")
    args = parser.parse_args()

    target_scope = args.org or args.user
    if not target_scope:
        print("Note: Neither --org nor --user was specified. Defaulting scope to author: " + args.author)
        args.user = args.author

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

    analyzer = GitHubOrgActivityAnalyzer(token=token, org=args.org, user=args.user)

    scope_type = "Organization" if args.org else "User Account"
    scope_name = args.org or args.user

    output = {
        "scope_type": scope_type,
        "scope_name": scope_name,
        "author": args.author,
        "auth_method": auth_method,
        "auth_details": meta,
    }

    # Audit PRs & Reviews
    prs = analyzer.analyze_pull_requests(args.author)
    output["pull_requests"] = prs

    # Audit Issues
    issues = analyzer.analyze_issues(args.author)
    output["issues"] = issues

    # Audit Branches without PRs
    if args.include_branches_without_pr:
        repos = analyzer.get_organization_repositories()
        all_unlinked = []
        for r in repos:
            unlinked = analyzer.analyze_branches_without_prs(
                repo=r["name"], default_branch=r["default_branch"], user_filter=args.author
            )
            all_unlinked.extend(unlinked)
        output["branches_without_pr"] = all_unlinked

    if args.json:
        print(json.dumps(output, indent=2))
        return

    # Formatted Plain Text Output
    print(f"\n========================================================")
    print(f" Activity Report: [{scope_type}: {scope_name}] | Author: @{args.author}")
    print(f" Active Authentication: {auth_method}")
    print(f"========================================================\n")

    print(f"--- [1] PULL REQUESTS & REVIEW AUDIT ({len(prs)} found) ---")
    for pr in prs:
        print(f"\n* [{pr['repo']}] PR #{pr['number']} ({pr['state']}): {pr['title']}")
        print(f"  URL: {pr['url']}")
        print(f"  Diff: +{pr['lines_added']} / -{pr['lines_deleted']} lines across {pr['changed_files']} files")
        if pr["reviews"]:
            print("  Reviews:")
            for r in pr["reviews"]:
                print(f"    - @{r['reviewer']}: {r['state']} (at {r['submitted_at']})")
        else:
            print("  Reviews: No completed reviews")
        if pr["pending_reviewers"]:
            print(f"  Pending Requested Reviewers: {', '.join(pr['pending_reviewers'])}")

    print(f"\n--- [2] ISSUES AUDIT ({len(issues)} found) ---")
    for issue in issues:
        print(f"* [{issue['repo']}] Issue #{issue['number']} ({issue['state']}): {issue['title']} (Comments: {issue['comments_count']})")

    if args.include_branches_without_pr:
        unlinked = output.get("branches_without_pr", [])
        print(f"\n--- [3] BRANCHES AUDIT ({len(unlinked)} branches containing commits by @{args.author}) ---")
        for b in unlinked:
            print(f"\n* Repo: {b['repo']} | Branch: {b['branch']} [{b['status_label']}] ({b['matched_commits_count']} commits)")
            for c in b["commits"][:10]:
                print(f"    [{c['sha']}] {c['date']} by @{c['author']}: {c['message']}")


if __name__ == "__main__":
    main()
