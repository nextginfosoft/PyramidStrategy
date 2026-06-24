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

  try {
    console.log('Navigating to http://localhost:5173...');
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

    console.log('Entering login credentials...');
    await page.locator('input[type="text"]').fill('admin');
    await page.locator('input[type="password"]').fill('pyramid123');
    await page.locator('button[type="submit"]').click();

    // Wait for dashboard to load
    console.log('Waiting for dashboard to load...');
    await page.waitForTimeout(3000);

    const screenshotBefore = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/21b1a102-929d-42ce-8432-f53003798ac1/dashboard_before_reset.png';
    await page.screenshot({ path: screenshotBefore });
    console.log(`Saved screenshot before reset to: ${screenshotBefore}`);

    // If STOP button is visible, click it first to be able to reset
    const stopButton = page.locator('button', { hasText: 'STOP' });
    if (await stopButton.isVisible()) {
      console.log('Strategy is running. Stopping it first...');
      await stopButton.click();
      await page.waitForTimeout(500);
      await page.locator('#confirm-stop-btn').click();
      await page.waitForTimeout(2000);
    }

    // Locate the RESET button
    const resetButton = page.locator('button', { hasText: 'RESET' });
    const isResetVisible = await resetButton.isVisible();
    const isResetEnabled = await resetButton.isEnabled();
    console.log(`RESET button visibility: ${isResetVisible}, enabled: ${isResetEnabled}`);

    if (isResetVisible && isResetEnabled) {
      console.log('Clicking the RESET button...');
      await resetButton.click();

      // Wait for confirmation modal
      console.log('Waiting for confirmation modal...');
      await page.waitForTimeout(500);

      // Confirm RESET
      console.log('Confirming RESET action...');
      await page.locator('#confirm-reset-btn').click();

      // Wait for network requests and state transition
      console.log('Waiting for UI update after reset...');
      await page.waitForTimeout(2000);

      const screenshotAfter = 'C:/Users/SANTOSH/.gemini/antigravity-cli/brain/21b1a102-929d-42ce-8432-f53003798ac1/dashboard_after_reset.png';
      await page.screenshot({ path: screenshotAfter });
      console.log(`Saved screenshot after reset to: ${screenshotAfter}`);

      // Verify dashboard data is cleared
      console.log('Verifying UI data is cleared...');

      // 1. P&L verification
      const pnlText = await page.locator('div:has-text("TODAY\'s P&L") + div').first().innerText();
      console.log(`Today's P&L value in UI: ${pnlText}`);
      if (pnlText.includes('₹0') || pnlText.includes('0')) {
        console.log('✓ P&L successfully reset to 0.');
      } else {
        console.error('✗ P&L not reset to 0!');
      }

      // 2. Open positions verification
      const openPositionsCard = page.locator('.bg-navy-900', { has: page.locator('div:text-is("OPEN POSITIONS")') }).first();
      const openPositionsContent = await openPositionsCard.innerText();
      console.log(`Open positions text: "${openPositionsContent}"`);
      if (openPositionsContent.includes('No open positions')) {
        console.log('✓ Open positions successfully cleared.');
      } else {
        console.error('✗ Open positions not cleared!');
      }

      // 3. Trade log verification
      const tradeLogCard = page.locator('.bg-navy-900', { has: page.locator('span:text-is("TRADE LOG")') }).first();
      const tradeTableText = await tradeLogCard.innerText();
      console.log(`Trade table text: ${tradeTableText}`);
      if (tradeTableText.includes('No matching trades found') || tradeTableText.includes('No trades logged today')) {
        console.log('✓ Trade log successfully cleared.');
      } else {
        console.error('✗ Trade log not cleared!');
      }

      // 4. AI Observer verification
      const aiObserverCard = page.locator('.bg-navy-900', { has: page.locator('div:has-text("AI OBSERVER")') }).first();
      const aiObserverContent = await aiObserverCard.innerText();
      console.log(`AI Observer text: "${aiObserverContent}"`);
      if (aiObserverContent.includes('AI Observer watching') || aiObserverContent.includes('Suggestions appear')) {
        console.log('✓ AI Observer successfully cleared.');
      } else {
        console.error('✗ AI Observer suggestions not cleared!');
      }

    } else {
      console.error('RESET button is not visible or not enabled.');
    }

  } catch (error) {
    console.error('Error occurred during test:', error);
  } finally {
    await browser.close();
    console.log('Browser closed.');
  }
}

run();
