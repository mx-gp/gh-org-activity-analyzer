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

  test('renders mock analysis results, comments, daily timeline, and date filters', async ({ page }) => {
    await page.route('/api/analyze', async (route) => {
      const mockResponse = {
        scope: 'octocat/my-repo',
        target_type: 'repository',
        author_filter: 'octocat',
        auth_method: 'GitHub CLI (gh auth)',
        auth_user: 'octocat',
        pull_requests: [
          {
            repo: 'octocat/my-repo',
            number: 28,
            title: 'feat(ci): add comprehensive quality suite',
            author: 'octocat',
            url: 'https://github.com/octocat/my-repo/pull/28',
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
            pending_reviewers: [],
            unresolved_threads_count: 1,
            resolved_threads_count: 0,
            reviewer_unresolved_counts: {
              'lead-dev': 1
            },
            review_threads: [
              {
                id: 'th_1',
                is_resolved: false,
                is_outdated: false,
                path: 'src/ci.py',
                line: 25,
                thread_initiator: 'lead-dev',
                last_commenter: 'lead-dev',
                waiting_on: 'author',
                comments: [
                  {
                    author: 'lead-dev',
                    body: 'Please double-check timeout parameter',
                    created_at: '2026-10-31T12:35:00Z',
                    url: 'https://github.com/octocat/my-repo/pull/28#discussion_r123'
                  }
                ]
              }
            ]
          }
        ],
        comments: [
          {
            repo: 'octocat/my-repo',
            target_title: '#27 Bump embla-carousel-react',
            target_url: 'https://github.com/octocat/my-repo/pull/27',
            comment_url: 'https://github.com/octocat/my-repo/pull/27#issuecomment-1',
            author: 'octocat',
            created_at: '2026-10-31T13:57:53Z',
            body: '@dependabot rebase'
          }
        ],
        issues: [
          {
            repo: 'octocat/my-repo',
            number: 1,
            title: 'Add dark mode support',
            author: 'octocat',
            url: 'https://github.com/octocat/my-repo/issues/1',
            state: 'OPEN',
            created_at: '2026-10-31T10:00:00Z',
            comments_count: 2
          }
        ],
        branches_without_pr: [
          {
            repo: 'octocat/my-repo',
            branch: 'feature/dark-mode',
            pr_status: 'NO_PR_EVER',
            status_label: 'Never had a PR',
            associated_pr: null,
            matched_commits_count: 1,
            commits: [
              {
                sha: 'f1a2b3c',
                author: 'octocat',
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

    await page.fill('#targetInput', 'https://github.com/octocat/my-repo');
    await page.fill('#authorInput', 'octocat');
    await page.click('#runBtn');

    await expect(page.locator('#resultsArea')).toBeVisible();

    await expect(page.locator('#statPrs')).toHaveText('1');
    await expect(page.locator('#statApprovals')).toHaveText('1');
    await expect(page.locator('#statComments')).toHaveText('1');
    await expect(page.locator('#statCommits')).toHaveText('1');
    await expect(page.locator('#statUnresolved')).toHaveText('1');

    // Daily breakdown contains comment
    await expect(page.locator('#dailyTab')).toContainText('@dependabot rebase');

    // Check PRs tab displays unresolved review thread badges
    await page.click('button:has-text("Pull Requests & Review Telemetry")');
    await expect(page.locator('#prsTab')).toBeVisible();
    await expect(page.locator('#prsTab')).toContainText('1 Unresolved Thread');
    await expect(page.locator('#prsTab')).toContainText('@lead-dev: 1 pending');

    // Check Review Threads & Debt tab
    await page.click('button:has-text("💬 Review Threads & Debt")');
    await expect(page.locator('#threadsTab')).toBeVisible();
    await expect(page.locator('#threadsTab')).toContainText('Review Debt Observability Matrix');
    await expect(page.locator('#threadsTab')).toContainText('@lead-dev');
    await expect(page.locator('#threadsTab')).toContainText('Please double-check timeout parameter');

    // Check Comments tab
    await page.click('button:has-text("💬 Discussion Comments")');
    await expect(page.locator('#commentsTab')).toBeVisible();
    await expect(page.locator('#commentsTab')).toContainText('@dependabot rebase');
    await expect(page.locator('#commentsTab')).toContainText('#27 Bump embla-carousel-react');
  });

});
