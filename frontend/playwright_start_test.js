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
    console.log('Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

    console.log('Page title:', await page.title());

    // Enter credentials
    console.log('Entering login credentials...');
    await page.locator('input[type="text"]').fill('admin');
    await page.locator('input[type="password"]').fill('pyramid123');
    await page.locator('button[type="submit"]').click();

    // Wait for dashboard to load
    console.log('Waiting for dashboard to load...');
    await page.waitForTimeout(3000);

    const screenshotPath1 = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/98f23bb9-c34d-42f7-973f-8834ee211412/dashboard_before_start.png';
    await page.screenshot({ path: screenshotPath1 });
    console.log(`Saved screenshot before starting to: ${screenshotPath1}`);

    // Find the START button
    const startButton = page.locator('button', { hasText: '▶ START' });
    const isVisible = await startButton.isVisible();
    const isEnabled = await startButton.isEnabled();
    console.log(`START button visibility: ${isVisible}, enabled: ${isEnabled}`);

    if (isVisible && isEnabled) {
      console.log('Clicking the START button...');
      await startButton.click();
      
      // Wait for a second for state transition
      await page.waitForTimeout(2000);

      const screenshotPath2 = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/98f23bb9-c34d-42f7-973f-8834ee211412/dashboard_after_start.png';
      await page.screenshot({ path: screenshotPath2 });
      console.log(`Saved screenshot after starting to: ${screenshotPath2}`);

      // Verify button status (should show STOP now)
      const stopButton = page.locator('button', { hasText: '⏹ STOP' });
      const isStopVisible = await stopButton.isVisible();
      console.log(`STOP button visibility after click: ${isStopVisible}`);

      if (isStopVisible) {
        console.log('Clicking the STOP button...');
        await stopButton.click();

        // Wait for state transition
        await page.waitForTimeout(2000);

        const isStartVisible = await startButton.isVisible();
        console.log(`START button visibility after STOP click: ${isStartVisible}`);
      }
    } else {
      console.log('Cannot click START button (either invisible or disabled).');
    }

  } catch (error) {
    console.error('Error occurred:', error);
  } finally {
    await browser.close();
    console.log('Browser closed.');
  }
}

run();
