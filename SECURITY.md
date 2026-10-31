# Security Policy

## Supported Versions

We release security updates for the active release version of `gh-org-activity-analyzer`.

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability within this project:

1. **Do not create a public GitHub issue.**
2. Send an email to the maintainers or report it privately through GitHub's [Advisory Reporting Feature](https://github.com/mx-gp/gh-org-activity-analyzer/security/advisories/new).
3. Please include:
   - Type of vulnerability (e.g., token leakage, injection, SSRF, dependency CVE)
   - Step-by-step reproduction instructions or proof-of-concept
   - Impact assessment

## Security Practices in this Project

- **Zero Hardcoded Secrets**: All GitHub authentication tokens are resolved dynamically at runtime and never persisted in source files.
- **Automated Security Scanning**: Automated CI runs `pip-audit`, `bandit` (SAST), and `npm audit` on every push and pull request.
- **Fine-Grained Permissions**: CI workflows run with minimal required GitHub token permissions (`contents: read`).
