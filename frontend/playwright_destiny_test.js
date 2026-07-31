import { chromium } from 'playwright';

async function run() {
  console.log('Launching browser for Destiny Strategy UI test...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => {
    console.log(`[BROWSER CONSOLE] ${msg.type().toUpperCase()}: ${msg.text()}`);
  });

  try {
    console.log('1. Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

    console.log('2. Logging in...');
    await page.locator('input[type="text"]').fill('admin');
    await page.locator('input[type="password"]').fill('pyramid123');
    await page.locator('button[type="submit"]').click();

    console.log('3. Waiting for dashboard...');
    await page.waitForTimeout(2000);

    console.log('4. Opening Settings modal...');
    await page.locator('button', { hasText: 'Settings' }).click();
    await page.waitForTimeout(1000);

    console.log('5. Selecting Strategy Destiny...');
    await page.locator('button', { hasText: 'Strategy Destiny' }).click();
    await page.waitForTimeout(500);

    console.log('6. Saving strategy settings...');
    await page.locator('button', { hasText: 'Save Parameters' }).click();
    await page.waitForTimeout(2000);

    console.log('7. Taking screenshot...');
    const screenshotPath = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/a3c30499-d5d3-46b7-aa74-dd85be305e9c/destiny_ui_test.png';
    await page.screenshot({ path: screenshotPath });
    console.log(`Saved screenshot to: ${screenshotPath}`);

    console.log('SUCCESS: Destiny Strategy UI test complete!');
  } catch (error) {
    console.error('Error occurred during UI test:', error);
  } finally {
    await browser.close();
  }
}

run();
