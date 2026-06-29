import { test, expect } from '@playwright/test';

test.describe('nl_alert_input visual regression', () => {
    test('initial render matches baseline', async ({ page }) => {
        await page.goto('/e2e/fixtures/nl_alert_input.html');
        const component = page.locator('.nl-alert-input-component');
        await expect(component).toHaveScreenshot('nl-alert-input-initial.png');
    });

    test('error state matches baseline', async ({ page }) => {
        await page.goto('/e2e/fixtures/nl_alert_input.html');
        const component = page.locator('.nl-alert-input-component');
        await page.click('.nl-alert-submit');
        await expect(component).toHaveScreenshot('nl-alert-input-error.png');
    });
});
