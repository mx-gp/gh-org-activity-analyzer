# GitHub Organization Activity & PR/Review Analyzer

A dynamic, zero-dependency Python tool to audit developer activity across all repositories in a GitHub Organization.

## Key Features

- **Dynamic Organization Scope**: Scans all active repositories across an entire GitHub organization without requiring manual repository lists.
- **Dynamic PR Author & Review Audit**: Evaluates PRs authored by targeted users and provides breakdown of reviewers, review decisions (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`), submitted timestamps, and pending reviewers.
- **Branches Without PRs (Orphan/Unmerged Branches)**: Discovers branches across all org repos that do not have active PRs and isolates commits authored by targeted team members.
- **Issue Audit**: Fetches issues opened by the author with comment counts and current states.
- **Zero Third-Party Dependencies**: Built exclusively using standard Python 3 libraries (`urllib`, `json`, `argparse`, `unittest`).

## Usage

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
