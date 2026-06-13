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

  // Capture failed requests
  page.on('requestfailed', request => {
    console.log(`[FAILED REQUEST] ${request.url()} failed: ${request.failure()?.errorText}`);
  });

  // Capture response status
  page.on('response', response => {
    if (response.status() >= 400) {
      console.log(`[HTTP ERROR] ${response.url()} returned status ${response.status()}`);
    }
  });

  try {
    console.log('Navigating to pyramid-strategy.vercel.app...');
    await page.goto('https://pyramid-strategy.vercel.app', { waitUntil: 'networkidle' });

    console.log('Page title:', await page.title());

    // Take a screenshot
    const screenshotPath = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/5313f8d4-bbb0-4eb4-9173-20b5d374266a/vercel_screenshot.png';
    console.log(`Taking screenshot and saving to: ${screenshotPath}`);
    await page.screenshot({ path: screenshotPath });

    // Look for login components or input elements
    const inputs = await page.locator('input').all();
    console.log(`Found ${inputs.length} input elements on the page.`);
    for (let i = 0; i < inputs.length; i++) {
      const type = await inputs[i].getAttribute('type');
      const val = await inputs[i].inputValue();
      console.log(`Input ${i + 1}: type="${type}", value="${val}"`);
    }

    // Try to enter admin/pyramid123 and login
    console.log('Attempting to log in with default credentials...');
    const usernameInput = page.locator('input[type="text"]');
    const passwordInput = page.locator('input[type="password"]');
    const submitButton = page.locator('button[type="submit"]');

    if (await usernameInput.isVisible() && await passwordInput.isVisible()) {
      await usernameInput.fill('admin');
      await passwordInput.fill('pyramid123');
      console.log('Filled credentials, clicking Sign In...');
      await submitButton.click();
      
      // Wait for a second or for any network request to fail
      await page.waitForTimeout(3000);
      
      const loggedInScreenshot = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/5313f8d4-bbb0-4eb4-9173-20b5d374266a/vercel_after_login.png';
      await page.screenshot({ path: loggedInScreenshot });
      console.log(`Took post-login screenshot and saved to: ${loggedInScreenshot}`);
    } else {
      console.log('Login form not visible.');
    }

  } catch (error) {
    console.error('Error occurred:', error);
  } finally {
    await browser.close();
    console.log('Browser closed.');
  }
}

run();
