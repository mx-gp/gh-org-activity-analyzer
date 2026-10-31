import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

GITHUB_REST_API = "https://api.github.com"
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"


class GitHubOrgActivityAnalyzer:
    """Comprehensive analyzer for GitHub organizations (Zero external dependencies).

    Capabilities:
    - Dynamic organization-wide repo scanning
    - PR analytics by author with detailed reviewer audit (who, status, timestamps)
    - Issue analytics by author
    - Detection of unmerged branches without open PRs and commit analysis by author/user
    """

    def __init__(self, token: str, org: str):
        self.org = org
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "gh-org-activity-analyzer",
            "Content-Type": "application/json",
        }

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
        """Dynamically list all active repositories across the organization."""
        repos = []
        page = 1
        while True:
            url = f"{GITHUB_REST_API}/orgs/{self.org}/repos?type=all&per_page=100&page={page}"
            items = self._http_request(url)
            if not items or not isinstance(items, list):
                break
            for repo in items:
                if repo.get("archived"):
                    continue
                if not include_forks and repo.get("fork"):
                    continue
                repos.append({
                    "name": repo["name"],
                    "default_branch": repo.get("default_branch", "main"),
                    "private": repo.get("private", False),
                })
            page += 1
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
        search_query = f"org:{self.org} type:pr author:{author}"
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
        search_query = f"org:{self.org} type:issue author:{author}"
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
        """Detect branches lacking PRs and audit commits by user/author filter."""
        # 1. Fetch active PR head branches for this repo
        open_prs_url = f"{GITHUB_REST_API}/repos/{self.org}/{repo}/pulls?state=open&per_page=100"
        open_prs = self._http_request(open_prs_url)
        open_pr_heads = set()
        if isinstance(open_prs, list):
            for pr in open_prs:
                if pr.get("head") and pr["head"].get("ref"):
                    open_pr_heads.add(pr["head"]["ref"])

        # 2. Fetch all branches
        branches_url = f"{GITHUB_REST_API}/repos/{self.org}/{repo}/branches?per_page=100"
        branches = self._http_request(branches_url)
        if not isinstance(branches, list):
            return []

        orphan_branches = []
        for b in branches:
            branch_name = b["name"]
            if branch_name == default_branch or branch_name in open_pr_heads:
                continue

            # 3. Retrieve commits on this branch
            commits_url = f"{GITHUB_REST_API}/repos/{self.org}/{repo}/commits?sha={urllib.parse.quote(branch_name)}&per_page=30"
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
                orphan_branches.append({
                    "repo": repo,
                    "branch": branch_name,
                    "matched_commits_count": len(matched_commits),
                    "commits": matched_commits,
                })

        return orphan_branches


def main():
    parser = argparse.ArgumentParser(description="GitHub Organization Activity, Review & Branch Analyzer")
    parser.add_argument("--org", required=True, help="Target GitHub Organization")
    parser.add_argument("--author", required=True, help="Target author/user handle to filter")
    parser.add_argument("--include-branches-without-pr", action="store_true", help="Scan unlinked branches without PRs")
    parser.add_argument("--json", action="store_true", help="Output results formatted as JSON")
    args = parser.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is required.", file=sys.stderr)
        sys.exit(1)

    analyzer = GitHubOrgActivityAnalyzer(token, args.org)

    output = {"org": args.org, "author": args.author}

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
    print(f" Organization Activity Report: {args.org} | Filter: @{args.author}")
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
        print(f"\n--- [3] BRANCHES WITHOUT PRS ({len(unlinked)} branches with commits by @{args.author}) ---")
        for b in unlinked:
            print(f"\n* Repo: {b['repo']} | Branch: {b['branch']} ({b['matched_commits_count']} commits)")
            for c in b["commits"]:
                print(f"    [{c['sha']}] {c['date']} by @{c['author']}: {c['message']}")


if __name__ == "__main__":
    main()
