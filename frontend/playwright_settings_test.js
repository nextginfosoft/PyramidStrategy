import { chromium } from 'playwright';

async function run() {
  console.log('Launching browser...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Capture console messages
  page.on('console', msg => {
    console.log(`[BROWSER CONSOLE] ${msg.type().toUpperCase()}: ${msg.text()}`);
  });

  // Capture request failures and status responses
  page.on('response', response => {
    if (response.url().includes('/config/api-keys')) {
      console.log(`[API RESPONSE] url: ${response.url()}, status: ${response.status()}`);
      response.text().then(text => console.log(`[API RESPONSE BODY]: ${text}`)).catch(() => {});
    }
  });

  page.on('requestfailed', request => {
    console.log(`[FAILED REQUEST] ${request.url()} failed: ${request.failure()?.errorText}`);
  });

  try {
    console.log('Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

    console.log('Entering login credentials...');
    await page.locator('input[type="text"]').fill('admin');
    await page.locator('input[type="password"]').fill('pyramid123');
    await page.locator('button[type="submit"]').click();

    // Wait for dashboard to load
    console.log('Waiting for dashboard...');
    await page.waitForTimeout(3000);

    // Open settings modal
    console.log('Opening settings...');
    await page.locator('button', { hasText: 'Settings' }).click();
    await page.waitForTimeout(1000);

    // Click AI Observer tab
    console.log('Clicking AI Observer tab...');
    await page.locator('button', { hasText: 'AI Observer' }).click();
    await page.waitForTimeout(500);

    // Select Gemini provider
    console.log('Selecting Gemini provider...');
    await page.locator('button', { hasText: 'Gemini' }).click();
    await page.waitForTimeout(500);

    // Try to enter and save AI API Key
    console.log('Entering AI API Key...');
    await page.locator('input[placeholder*="Enter API Key"]').fill('AIzaSyTestKey1234567890abcdef');
    await page.waitForTimeout(500);

    console.log('Clicking Save Key...');
    await page.locator('button', { hasText: 'Save Key' }).click();
    
    // Wait for response and toast status
    await page.waitForTimeout(3000);

    const screenshotPath = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/3fe4336b-4a19-4370-a2f1-727775178db6/settings_save_result.png';
    await page.screenshot({ path: screenshotPath });
    console.log(`Saved screenshot to: ${screenshotPath}`);

  } catch (error) {
    console.error('Error occurred during settings test:', error);
  } finally {
    await browser.close();
    console.log('Browser closed.');
  }
}

run();
