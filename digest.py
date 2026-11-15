"""Executive Activity & PR Review Digest Generator.

Provides Markdown formatting and optional Slack/Discord webhook delivery
for GitHub activity analysis reports. Zero external dependencies.
"""

from datetime import datetime, timezone
import json
import urllib.request
import urllib.error


def generate_markdown_digest(report: dict) -> str:
    """Formats an analyzer report dictionary into clean, executive Markdown."""
    scope = report.get("scope", "Repository")
    target_type = report.get("target_type", "repo")
    author_filter = report.get("author_filter")
    prs = report.get("pull_requests", [])
    issues = report.get("issues", [])
    comments = report.get("comments", [])
    orphan_branches = report.get("branches_without_pr", [])

    total_prs = len(prs)
    merged_prs = sum(1 for p in prs if p.get("state") == "MERGED")
    open_prs = sum(1 for p in prs if p.get("state") == "OPEN")
    closed_prs = sum(1 for p in prs if p.get("state") == "CLOSED")

    total_additions = sum(p.get("lines_added", 0) for p in prs)
    total_deletions = sum(p.get("lines_deleted", 0) for p in prs)
    total_approvals = sum(
        sum(1 for r in p.get("reviews", []) if r.get("state") == "APPROVED")
        for p in prs
    )
    total_unresolved = sum(p.get("unresolved_threads_count", 0) for p in prs)

    lines = [
        f"# 📊 GitHub Activity Digest: {scope}",
        f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
    ]
    if author_filter:
        lines.append(f"**Filtered Author**: `@{author_filter}`")
    lines.extend([
        "",
        "## 📈 Executive Summary",
        f"- **Pull Requests**: {total_prs} total ({merged_prs} merged, {open_prs} open, {closed_prs} closed)",
        f"- **Code Volume**: +{total_additions:,} / -{total_deletions:,} lines",
        f"- **Reviews & Approvals**: {total_approvals} approvals logged",
        f"- **Review Debt**: {total_unresolved} unresolved review discussion thread(s)",
        f"- **Author Comments / Discussions**: {len(comments)} comment(s)",
        f"- **Issues**: {len(issues)} open/active issue(s)",
        f"- **Unattached / Orphan Branches**: {len(orphan_branches)} branch(es)",
        "",
    ])

    # Unresolved Review Threads & Debt
    unresolved_threads_pr = [p for p in prs if p.get("unresolved_threads_count", 0) > 0]
    if unresolved_threads_pr:
        lines.append("## 💬 Review Bottlenecks & Unresolved Threads")
        for p in unresolved_threads_pr:
            lines.append(f"### [#{p['number']} {p['title']}]({p['url']})")
            lines.append(f"- **Author**: `@{p['author']}` | **Status**: {p.get('state')}")
            for thread in p.get("review_threads", []):
                if not thread.get("is_resolved", False):
                    initiator = thread.get("thread_initiator", "unknown")
                    waiting_on = thread.get("waiting_on", "reviewer")
                    file_loc = f"{thread.get('path', 'file')}:{thread.get('line', '?')}"
                    last_body = thread.get("comments", [{}])[-1].get("body", "").strip().replace("\n", " ")
                    if len(last_body) > 120:
                        last_body = last_body[:117] + "..."
                    lines.append(f"  - **{file_loc}** (opened by `@{initiator}`, waiting on `{waiting_on}`): \"{last_body}\"")
        lines.append("")

    # Pull Requests List
    if prs:
        lines.append("## 🚀 Pull Requests")
        for p in prs:
            state_emoji = "🟣" if p.get("state") == "MERGED" else ("🟢" if p.get("state") == "OPEN" else "🔴")
            sla_text = f" | SLA: `{p.get('sla_status')}`" if p.get("sla_status") and p.get("sla_status") != "N/A" else ""
            lines.append(f"- {state_emoji} [#{p['number']} {p['title']}]({p['url']}) by `@{p['author']}` ({p.get('state')}{sla_text})")
            lines.append(f"  - Diff: `+{p.get('lines_added', 0)} / -{p.get('lines_deleted', 0)}` across {p.get('changed_files', 0)} file(s)")
            if p.get("reviews"):
                review_states = [f"@{r['reviewer']}: {r['state']}" for r in p["reviews"]]
                lines.append(f"  - Reviews: {', '.join(review_states)}")
        lines.append("")

    # Branches without PR
    if orphan_branches:
        lines.append("## ⚠️ Branches Without Pull Requests")
        for b in orphan_branches:
            branch_name = b.get("branch", "unknown")
            label = b.get("status_label", "No PR")
            commits_cnt = b.get("matched_commits_count", len(b.get("commits", [])))
            lines.append(f"- `{branch_name}` ({label}): {commits_cnt} commit(s)")
        lines.append("")

    return "\n".join(lines).strip()


def send_webhook_digest(webhook_url: str, markdown_content: str, title: str = "GitHub Activity Digest") -> bool:
    """Sends the formatted digest to Slack or Discord webhook endpoint."""
    if not webhook_url:
        raise ValueError("Webhook URL cannot be empty")

    # Adapt payload for Slack vs Discord
    is_discord = "discord.com" in webhook_url or "discordapp.com" in webhook_url

    # Keep text length within Discord/Slack limits per message block (Slack: 3000 chars, Discord: 2000 chars)
    max_len = 1900 if is_discord else 2900
    display_content = markdown_content
    if len(display_content) > max_len:
        display_content = display_content[:max_len - 30] + "\n\n_... (truncated for message limit)_"

    if is_discord:
        payload = {
            "content": f"**{title}**\n\n{display_content}"
        }
    else:
        # Standard Slack incoming webhook payload
        payload = {
            "text": f"*{title}*\n\n{display_content}",
            "mrkdwn": True,
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "GitHub-Org-Activity-Analyzer-Digest"}
    )

    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status in (200, 204)
