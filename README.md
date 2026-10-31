# GitHub Organization Activity & PR/Review Analyzer

A dynamic, zero-dependency Python tool to audit developer activity across all repositories in a GitHub Organization.

## Key Features

- **Dynamic Organization Scope**: Scans all active repositories across an entire GitHub organization without requiring manual repository lists.
- **Dynamic PR Author & Review Audit**: Evaluates PRs authored by targeted users and provides breakdown of reviewers, review decisions (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`), submitted timestamps, and pending reviewers.
- **Branches Without PRs (Orphan/Unmerged Branches)**: Discovers branches across all org repos that do not have active PRs and isolates commits authored by targeted team members.
- **Issue Audit**: Fetches issues opened by the author with comment counts and current states.
- **Zero Third-Party Dependencies**: Built exclusively using standard Python 3 libraries (`urllib`, `json`, `argparse`, `unittest`).

## Supported Authentication Methods

The analyzer dynamically supports 3 primary authentication modes and clearly shows you which one is in use:

1. **⚡ Automatic GitHub CLI Detection (`gh auth`)**:
   - If you have GitHub CLI installed and logged in (`gh auth login`), the analyzer automatically detects and uses your local session.
2. **🏢 GitHub App (Enterprise / Organization Friendly)**:
   - Provide an **App ID**, **Installation ID**, and **Private Key (.pem)**.
   - Generates RS256 JWTs and exchanges them for temporary installation tokens on the fly without external libraries.
3. **🔑 Personal Access Token (PAT)**:
   - Either through `export GITHUB_TOKEN="ghp_..."` or entered into the UI/CLI.

## Web UI Frontend

A lightweight, GitHub dark-themed dashboard is included so you can review activities and reviews interactively from your browser without installing Node.js or external dependencies.

### Launching the Frontend
```bash
python3 server.py 8080
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser.

- Shows a **Live Authentication Banner** at the top indicating whether your local GitHub CLI or Environment token was auto-detected.
- Lets you switch seamlessly between **Auto-Detect**, **Personal Access Token**, and **GitHub App** credentials.
- After running analysis, highlights the **exact authentication method** used to query GitHub.

Features on the UI:
- **Interactive Form**: Enter organization, author handle, and optional token.
- **Summary Metric Cards**: Instant count of PRs, review submissions, issues, and unlinked branches.
- **Pull Requests & Review Telemetry Tab**: Color-coded review pills (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`), dates, diff stats (+/- lines), and pending reviewer requests.
- **Branches Without PRs Tab**: Lists orphan feature branches with commit SHAs, timestamps, and commit messages authored by the member.
- **Issues Tab**: Full history of issues and comment engagement.

## CLI Usage

### 1. Set GitHub Token
```bash
export GITHUB_TOKEN="ghp_yourPersonalAccessTokenHere"
```

### 2. Run Analysis
```bash
# Analyze PRs and Issues for a specific author in an organization
python3 analyzer.py --org <ORG_NAME> --author <GITHUB_USERNAME>

# Include scanning of branches without PRs across all repositories
python3 analyzer.py --org <ORG_NAME> --author <GITHUB_USERNAME> --include-branches-without-pr

# Export results as JSON
python3 analyzer.py --org <ORG_NAME> --author <GITHUB_USERNAME> --include-branches-without-pr --json
```

## Running Tests
```bash
python3 test_analyzer.py
```
