# GitHub Activity & PR Review Analyzer 🚀

[![CI & Build Verification](https://github.com/octocat/gh-org-activity-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/octocat/gh-org-activity-analyzer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Playwright: Enabled](https://img.shields.io/badge/Playwright-E2E%20Tested-green.svg)](https://playwright.dev/)

An open-source, zero-external-dependency developer telemetry and code review audit platform for **GitHub Organizations**, **Individual User Accounts**, and **Single Repositories**.

---

## ✨ Features

- **🎯 Flexible Scope**:
  - Full GitHub URL: `https://github.com/octocat/my-repo`
  - `owner/repo`: `octocat/my-repo`
  - Short repo name: `my-repo` (auto-scoped to your logged-in user)
  - Entire Organization or User: `google`, `meta`, `octocat`
  - All user repositories across your account (when left blank).
- **📅 Daily Work Breakdown**:
  - Chronological timeline grouping pull requests, reviews, branch commits, and issues by date.
- **⚡ Dynamic Date Range Filters**:
  - Presets for **Today**, **Past 7 Days**, **Past 30 Days**, or custom **From / To** date pickers.
- **🧐 Deep Pull Request & Review Audit**:
  - Color-coded review badges (`APPROVED`, `CHANGES_REQUESTED`, `COMMENTED`), reviewer handles, timestamps, and diff additions/deletions.
- **🌿 Branch & PR Lifecycle Telemetry**:
  - Detects true orphan branches (`Never had a PR`), merged stale branches (`PR Merged, branch not deleted`), closed unmerged work, and active PRs.
- **🔐 Multi-Source Seamless Authentication**:
  - **Auto-Detect**: Seamless GitHub CLI session (`gh auth token`) or `GITHUB_TOKEN` environment variable.
  - **GitHub App**: Enterprise-grade App ID + Installation ID + `.pem` private key authentication.
  - **Personal Access Token**: Interactive web form entry.
- **⚡ Zero External Backend Dependencies**:
  - Built with pure standard Python 3 (`urllib`, `json`, `argparse`, `unittest`).

---

## 🚀 Quick Start

### Option 1: Web Dashboard (Interactive Frontend)

```bash
git clone https://github.com/octocat/gh-org-activity-analyzer.git
cd gh-org-activity-analyzer

# Start the web server (uses Python 3 builtin http.server)
python3 server.py 8080
```
Open **[http://localhost:8080](http://localhost:8080)** in your browser.

---

### Option 2: CLI Usage

```bash
# Analyze a specific repository
python3 analyzer.py --target "https://github.com/octocat/my-repo"

# Filter by a specific author
python3 analyzer.py --target "my-repo" --author "octocat"

# Analyze an entire organization
python3 analyzer.py --target "my-org" --author "octocat"

# Export results as JSON
python3 analyzer.py --target "my-repo" --json
```

---

## 🧪 Testing

### 1. Python Unit Tests (Zero dependencies)
```bash
python3 test_analyzer.py
python3 test_auth.py
```

### 2. Playwright End-to-End Tests
```bash
npm install
npx playwright install --with-deps chromium
npm run test:e2e
```

---

## 🤝 Community & Contributing

Contributions are welcome! Please check our [Contributing Guide](CONTRIBUTING.md) and feel free to open issues or submit Pull Requests.

## 📄 License

This project is licensed under the [MIT License](LICENSE).
