/**
 * Playwright test: Broker role RBAC enforcement (#243).
 *
 * Verifies that a broker user is redirected to /portal/broker when
 * attempting to navigate to any internal page.
 */
import { test, expect } from '@playwright/test';

const INTERNAL_PAGES = [
  '/executive',
  '/compliance',
  '/finance',
  '/workbench/underwriting',
  '/workbench/actuarial',
  '/workbench/claims',
  '/decisions',
  '/analytics/claims',
  '/analytics/underwriting',
  '/submissions',
  '/policies',
  '/claims',
  '/knowledge',
  '/products',
  '/escalations',
];

test.describe('Broker RBAC — route restrictions (#243)', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate as broker by setting localStorage before navigating
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('openinsure_role', 'broker');
    });
  });

  for (const route of INTERNAL_PAGES) {
    test(`broker navigating to ${route} should redirect to /portal/broker`, async ({ page }) => {
      await page.goto(route);
      await page.waitForURL('**/portal/broker', { timeout: 5_000 });
      expect(page.url()).toContain('/portal/broker');
    });
  }

  test('broker can access /portal/broker', async ({ page }) => {
    await page.goto('/portal/broker');
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain('/portal/broker');
  });
});
