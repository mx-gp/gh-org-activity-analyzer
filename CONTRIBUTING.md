# Contributing to GitHub Activity & PR Review Analyzer

We welcome community contributions, bug fixes, and feature enhancements!

## Getting Started

1. **Fork the Repository** on GitHub.
2. **Clone your fork**:
   ```bash
   git clone https://github.com/<your-username>/gh-org-activity-analyzer.git
   cd gh-org-activity-analyzer
   ```
3. **Run Unit Tests**:
   ```bash
   python3 test_analyzer.py
   python3 test_auth.py
   ```
4. **Run End-to-End Tests**:
   ```bash
   npm test
   ```

## Development Guidelines

- Keep the core Python library zero-dependency wherever possible (standard `urllib`, `json`, `argparse`, `unittest`).
- Write unit tests for new features in `test_analyzer.py` or `test_auth.py`.
- Ensure all CI tests pass before opening a Pull Request.

## Submitting Pull Requests

1. Create a feature branch (`git checkout -b feat/your-feature-name`).
2. Commit your changes with descriptive commit messages.
3. Push to your branch (`git push origin feat/your-feature-name`).
4. Open a Pull Request against the default branch.
