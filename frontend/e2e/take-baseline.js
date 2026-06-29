import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const baseUrl = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:8080';

async function main() {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });

    await page.goto(`${baseUrl}/e2e/fixtures/nl_alert_input.html`);
    const component = page.locator('.nl-alert-input-component');

    const outDir = join(__dirname, '__screenshots__');
    await mkdir(outDir, { recursive: true });

    await component.screenshot({ path: join(outDir, 'nl-alert-input-initial.png') });

    await page.click('.nl-alert-submit');
    await component.screenshot({ path: join(outDir, 'nl-alert-input-error.png') });

    await browser.close();
    console.log('Visual baselines written to', outDir);
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});
