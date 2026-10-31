import { test, expect } from '@playwright/test';

test.describe('GitHub Activity & Review Analyzer Web Dashboard', () => {

  test('loads initial page and checks authentication status banner', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveTitle(/GitHub Activity & PR Review Analyzer/);
    await expect(page.locator('h1')).toContainText('GitHub Activity & PR Review Analyzer');

    const authBanner = page.locator('#authBanner');
    await expect(authBanner).toBeVisible();

    await expect(page.locator('#chipAuto')).toBeVisible();
    await expect(page.locator('#chipPat')).toBeVisible();
    await expect(page.locator('#chipApp')).toBeVisible();
  });

  test('switches authentication tabs smoothly', async ({ page }) => {
    await page.goto('/');

    await page.click('#chipPat');
    await expect(page.locator('#patInputGroup')).toBeVisible();
    await expect(page.locator('#appInputGroup')).not.toBeVisible();

    await page.click('#chipApp');
    await expect(page.locator('#appInputGroup')).toBeVisible();
    await expect(page.locator('#patInputGroup')).not.toBeVisible();

    await page.click('#chipAuto');
    await expect(page.locator('#patInputGroup')).not.toBeVisible();
    await expect(page.locator('#appInputGroup')).not.toBeVisible();
  });

  test('renders mock analysis results, comments, daily timeline, and graphs', async ({ page }) => {
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
            title: 'feat(ci): add comprehensive quality suite',
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
        comments: [
          {
            repo: 'mx-gp/portfolio',
            target_title: '#27 Bump embla-carousel-react',
            target_url: 'https://github.com/mx-gp/portfolio/pull/27',
            comment_url: 'https://github.com/mx-gp/portfolio/pull/27#issuecomment-1',
            author: 'mx-gp',
            created_at: '2026-10-31T13:57:53Z',
            body: '@dependabot rebase'
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
            matched_commits_count: 1,
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

    await page.fill('#targetInput', 'https://github.com/mx-gp/portfolio');
    await page.fill('#authorInput', 'mx-gp');
    await page.click('#runBtn');

    await expect(page.locator('#resultsArea')).toBeVisible();

    // Verify stats cards
    await expect(page.locator('#statPrs')).toHaveText('1');
    await expect(page.locator('#statApprovals')).toHaveText('1');
    await expect(page.locator('#statComments')).toHaveText('1');
    await expect(page.locator('#statCommits')).toHaveText('1');

    // Verify Visual Analytics & Graphs are rendered
    const velocityBarChart = page.locator('#velocityBarChart');
    await expect(velocityBarChart).toBeVisible();
    await expect(velocityBarChart.locator('.bar-column')).toHaveCount(1);

    const mixContainer = page.locator('#mixContainer');
    await expect(mixContainer).toBeVisible();
    await expect(mixContainer).toContainText('Pull Requests');
    await expect(mixContainer).toContainText('Branch Commits');

    // Verify Daily Work Breakdown timeline
    await expect(page.locator('#dailyTab')).toContainText('@dependabot rebase');

    // Switch to Comments tab
    await page.click('button:has-text("💬 Discussion Comments")');
    await expect(page.locator('#commentsTab')).toBeVisible();
    await expect(page.locator('#commentsTab')).toContainText('@dependabot rebase');
    await expect(page.locator('#commentsTab')).toContainText('#27 Bump embla-carousel-react');

    // Test quick date preset interaction
    await page.click('button:has-text("Today")');
    await expect(page.locator('#resultsArea')).toBeVisible();
  });

});
