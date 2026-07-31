import { chromium } from 'playwright';

async function testStrategySwitching() {
  console.log('Starting Strategy Switching UI Test...');
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
    await page.waitForTimeout(2000);

    console.log('3. Opening Settings...');
    await page.locator('button', { hasText: 'Settings' }).click();
    await page.waitForTimeout(1000);

    console.log('4. Switching to Strategy Destiny...');
    await page.locator('button', { hasText: 'Strategy Destiny' }).click();
    await page.waitForTimeout(500);

    console.log('5. Saving Destiny parameters...');
    await page.locator('button', { hasText: 'Save Parameters' }).click();
    await page.waitForTimeout(2000);

    console.log('6. Closing Settings modal to inspect Main Dashboard...');
    await page.locator('button', { hasText: '✕' }).first().click();
    await page.waitForTimeout(1000);

    const destinyScreenshot = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/a3c30499-d5d3-46b7-aa74-dd85be305e9c/destiny_dashboard.png';
    await page.screenshot({ path: destinyScreenshot });
    console.log(`Saved Destiny Dashboard screenshot to: ${destinyScreenshot}`);

    console.log('7. Re-opening Settings and switching back to Pyramid Strategy...');
    await page.locator('button', { hasText: 'Settings' }).click();
    await page.waitForTimeout(1000);
    await page.locator('button', { hasText: 'Pyramid Strategy' }).click();
    await page.waitForTimeout(500);
    await page.locator('button', { hasText: 'Save Parameters' }).click();
    await page.waitForTimeout(2000);

    console.log('8. Closing Settings modal to inspect Pyramid Dashboard...');
    await page.locator('button', { hasText: '✕' }).first().click();
    await page.waitForTimeout(1000);

    const pyramidScreenshot = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/a3c30499-d5d3-46b7-aa74-dd85be305e9c/pyramid_dashboard.png';
    await page.screenshot({ path: pyramidScreenshot });
    console.log(`Saved Pyramid Dashboard screenshot to: ${pyramidScreenshot}`);

    console.log('SUCCESS: Strategy switching UI test completed successfully!');
  } catch (err) {
    console.error('Error during strategy switching test:', err);
  } finally {
    await browser.close();
  }
}

testStrategySwitching();
