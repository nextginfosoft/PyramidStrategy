import { chromium } from 'playwright';

async function testNiftyDataOnSwitch() {
  console.log('Starting Strategy Switch NIFTY Data Test...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  try {
    console.log('1. Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

    console.log('2. Performing UI Login...');
    await page.locator('input[type="text"]').fill('admin');
    await page.locator('input[type="password"]').fill('pyramid123');
    await page.locator('button[type="submit"]').click();
    await page.waitForTimeout(2000);

    console.log('3. Injecting simulated tick via API...');
    await page.evaluate(async () => {
      const tok = localStorage.getItem('pyramid_token');
      await fetch('http://localhost:8000/api/strategy/simulate-tick?nifty_price=24155.50', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${tok}` }
      });
    });
    await page.waitForTimeout(1000);

    const initialContent = await page.evaluate(() => document.body.innerText);
    console.log('Dashboard initial loaded. Has 24,155.50:', initialContent.includes('24,155.50') || initialContent.includes('24155.50'));

    console.log('4. Opening Settings from Sidebar...');
    await page.locator('nav button', { hasText: 'Settings' }).click();
    await page.waitForTimeout(1000);

    console.log('5. Switching to Strategy Destiny...');
    await page.locator('button', { hasText: 'Strategy Destiny' }).click();
    await page.waitForTimeout(500);

    console.log('6. Saving Destiny parameters...');
    await page.locator('button', { hasText: 'Save Parameters' }).click();
    await page.waitForTimeout(2000);

    console.log('7. Closing Settings modal...');
    await page.locator('button', { hasText: '✕' }).first().click();
    await page.waitForTimeout(1000);

    const postSwitchContent = await page.evaluate(() => document.body.innerText);
    const hasNiftyData = postSwitchContent.includes('24,155.50') || postSwitchContent.includes('24155.50');

    console.log('Post-switch Dashboard has NIFTY 24155.50:', hasNiftyData);

    const screenshotPath = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/150b95ce-9ed1-4d66-aa5c-25f80a8cda0d/switch_nifty_verification.png';
    await page.screenshot({ path: screenshotPath });
    console.log(`Saved screenshot to: ${screenshotPath}`);

    if (hasNiftyData) {
      console.log('✅ TEST SUCCESSFUL: NIFTY 50 live data is displaying on dashboard after strategy switch!');
    } else {
      console.error('❌ TEST FAILED: NIFTY data missing after strategy switch.');
    }

  } catch (err) {
    console.error('Error during test:', err);
  } finally {
    await browser.close();
  }
}

testNiftyDataOnSwitch();
