import { test, expect } from '@playwright/test';

test.describe('GitHub Activity & Review Analyzer Web Dashboard', () => {

  test('loads initial page and checks authentication status banner', async ({ page }) => {
    await page.goto('/');

    // Check title and header
    await expect(page).toHaveTitle(/GitHub Activity & PR Review Analyzer/);
    await expect(page.locator('h1')).toContainText('GitHub Activity & PR Review Analyzer');

    // Check active session banner exists
    const authBanner = page.locator('#authBanner');
    await expect(authBanner).toBeVisible();

    // Check auth toggle chips
    await expect(page.locator('#chipAuto')).toBeVisible();
    await expect(page.locator('#chipPat')).toBeVisible();
    await expect(page.locator('#chipApp')).toBeVisible();
  });

  test('switches authentication tabs smoothly', async ({ page }) => {
    await page.goto('/');

    // Switch to Personal Access Token
    await page.click('#chipPat');
    await expect(page.locator('#patInputGroup')).toBeVisible();
    await expect(page.locator('#appInputGroup')).not.toBeVisible();

    // Switch to GitHub App
    await page.click('#chipApp');
    await expect(page.locator('#appInputGroup')).toBeVisible();
    await expect(page.locator('#patInputGroup')).not.toBeVisible();

    // Switch back to Auto-Detect
    await page.click('#chipAuto');
    await expect(page.locator('#patInputGroup')).not.toBeVisible();
    await expect(page.locator('#appInputGroup')).not.toBeVisible();
  });

  test('renders mock analysis results, daily timeline, and date filters', async ({ page }) => {
    // Intercept backend API call to test UI deterministically
    await page.route('/api/analyze', async (route) => {
      const mockResponse = {
        scope: 'mx-gp/portfolio',
        target_type: 'repository',
        author_filter: 'mx-gp',
        auth_method: 'GitHub CLI (gh auth)',
        auth_user: 'mx-gp',
        pull_requests: [
          {
            repo: 'mx-gp/portfolio',
            number: 28,
            title: 'feat(ci): add comprehensive quality, performance, and security CI suite',
            author: 'mx-gp',
            url: 'https://github.com/mx-gp/portfolio/pull/28',
            state: 'MERGED',
            created_at: '2026-10-31T12:00:00Z',
            merged_at: '2026-10-31T13:00:00Z',
            lines_added: 450,
            lines_deleted: 20,
            changed_files: 8,
            reviews: [
              {
                reviewer: 'lead-dev',
                state: 'APPROVED',
                submitted_at: '2026-10-31T12:30:00Z'
              }
            ],
            pending_reviewers: []
          }
        ],
        issues: [
          {
            repo: 'mx-gp/portfolio',
            number: 1,
            title: 'Add dark mode support',
            author: 'mx-gp',
            url: 'https://github.com/mx-gp/portfolio/issues/1',
            state: 'OPEN',
            created_at: '2026-10-31T10:00:00Z',
            comments_count: 2
          }
        ],
        branches_without_pr: [
          {
            repo: 'mx-gp/portfolio',
            branch: 'feature/dark-mode',
            pr_status: 'NO_PR_EVER',
            status_label: 'Never had a PR',
            associated_pr: null,
            matched_commits_count: 2,
            commits: [
              {
                sha: 'f1a2b3c',
                author: 'mx-gp',
                date: '2026-10-31T09:00:00Z',
                message: 'initial dark mode tokens'
              }
            ]
          }
        ]
      };
      await route.fulfill({ json: mockResponse });
    });

    await page.goto('/');

    // Fill in target
    await page.fill('#targetInput', 'https://github.com/mx-gp/portfolio');
    await page.fill('#authorInput', 'mx-gp');

    // Run analysis
    await page.click('#runBtn');

    // Wait for results
    await expect(page.locator('#resultsArea')).toBeVisible();

    // Verify stats cards
    await expect(page.locator('#statPrs')).toHaveText('1');
    await expect(page.locator('#statApprovals')).toHaveText('1');
    await expect(page.locator('#statCommits')).toHaveText('1');

    // Check Daily Work Breakdown tab
    await expect(page.locator('#dailyTab')).toContainText('Daily Work Breakdown');
    await expect(page.locator('#dailyTab')).toContainText('feat(ci): add comprehensive quality');

    // Switch to Pull Requests tab
    await page.click('button:has-text("Pull Requests & Review Telemetry")');
    await expect(page.locator('#prsTab')).toBeVisible();
    await expect(page.locator('#prsTab')).toContainText('#28 feat(ci)');
    await expect(page.locator('#prsTab')).toContainText('@lead-dev');
    await expect(page.locator('#prsTab')).toContainText('APPROVED');

    // Switch to Branches tab
    await page.click('button:has-text("Branch & PR Lifecycle Audit")');
    await expect(page.locator('#orphansTab')).toBeVisible();
    await expect(page.locator('#orphansTab')).toContainText('feature/dark-mode');
    await expect(page.locator('#orphansTab')).toContainText('Never had a PR');

    // Switch to Issues tab
    await page.click('button:has-text("Issues")');
    await expect(page.locator('#issuesTab')).toBeVisible();
    await expect(page.locator('#issuesTab')).toContainText('#1 Add dark mode support');
  });

});
