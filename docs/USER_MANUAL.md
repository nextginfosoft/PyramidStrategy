# PyramidStrategy User Manual
## End-User Setup & Pre-Trading Checklist

Welcome to **PyramidStrategy**, your automated platform for multi-user NIFTY options trading. This manual guides you through configuring your settings and preparing the system for live/paper trading.

---

## 1. Initial Login & Registration

Before doing anything else, you must log in to your account.
1. Open your browser and navigate to your secure domain: **`https://pyramid.nextginfosoft.com`** (or your designated server IP).
2. If this is a fresh setup or your first time logging in:
   * Click the **"Don't have an account? Sign Up"** link at the bottom of the form.
   * Enter your preferred username and password (at least 6 characters), then click **Sign Up**.
   * The system will create your account and automatically log you in.
3. For subsequent logins, simply enter your username and password, then click **Sign In**.

---

## 2. Broker Connection (Zerodha Kite API)

To stream market prices and execute trades, the system must connect to your **Zerodha Kite** developer account.

### Step 2.1: Save your API Credentials
1. Go to your Zerodha Developer Console and obtain your **API Key** and **API Secret**.
2. On the PyramidStrategy dashboard, click the **Settings** gear icon in the top right.
3. Select the **Zerodha** tab.
4. Paste your **API Key** and **API Secret** into the respective fields and click **Save**.
   * *Note: The system securely encrypts these keys before saving them to the database.*

### Step 2.2: Daily Authentication (Perform every morning)
> [!IMPORTANT]
> **Zerodha expires access tokens daily.** You must perform this login step **every morning** before the market opens (ideally between 8:00 AM and 9:00 AM).
1. In the **Zerodha Kite** control card on your dashboard, click **Authenticate**.
2. This opens the Zerodha login screen in a new browser tab.
3. Log in with your Zerodha Client ID, Password, and 2FA (Mobile App TOTP).
4. Once successfully logged in, the tab will close or redirect. Return to the PyramidStrategy dashboard tab.
5. Click the **Validate** button to verify the session token is active. The *Auth token* indicator dot will turn **green**.

### Step 2.3: Load NFO Instruments
Options contracts change daily. You must load the active contracts from the exchange:
1. Click the **Load NFO Instruments** button in the Zerodha card.
2. The *NFO instruments* indicator dot will turn **green**.

### Step 2.4: Start Live Feed
Once authenticated and instruments are loaded:
1. Click **Start Live Feed**.
2. The *WebSocket feed* and *Options streaming* indicator dots will turn **green**. You will now see live price updates on your dashboard!

---

## 3. Strategy Configuration & Parameters

Configure the math engine that dictates when buy/sell signals are generated.

1. Click the **Settings** gear icon in the top right and select the **Strategy** tab.
2. Configure the following parameters:

| Parameter | Type | Description |
| :--- | :--- | :--- |
| **R1, R2, R3** | *Price (Bullish)* | Resistance Levels (e.g. 23170, 23220, 23250). Used to generate long/entry signals on upward breakouts. |
| **S1, S2, S3** | *Price (Bearish)* | Support Levels (e.g. 23070, 23025, 22950). Used to generate short/entry signals on downward breakdowns. |
| **Lot Size** | *Integer* | Number of lots to buy (e.g., `1` lot = 65 shares). The engine handles conversions automatically. |
| **Target Points** | *Points* | Your target profit distance in index points (e.g. `20` points). |
| **Stop-Loss Points**| *Points* | Your protection cutoff distance in index points (e.g. `10` points). |

3. **Paper Trading Toggle:** 
   * **Keep this toggled ON** when testing. It simulates execution against live streaming ticks without risking real capital.
   * Turn this **OFF** only when you are ready to send live orders directly to your Zerodha account.
4. Click **Save** to apply your changes.

---

## 4. Activating the Strategy

When the broker feed is running and your parameters are set:
1. Locate the **Strategy Engine Status** card on the main dashboard.
2. Click the **Start Strategy** button.
3. The engine is now running. It will continuously monitor Nifty tick feeds, calculate support/resistance breaks, execute entry positions based on your lot size, and manage target/stop-loss exits automatically.
4. You can monitor active positions, open orders, and realized PnL directly from the dashboard view.

---

## 5. Optional Integrations (AI & Telegram)

Access these options in the **Settings** tabs to enhance your trading experience:

* **Telegram Notifications:**
  1. Open Settings -> **Telegram** tab.
  2. Input your **Telegram Bot Token** and your **Telegram Chat ID**.
  3. Click **Save** and then click **Test Connection** to receive a test message on your phone.
  4. Once configured, the system will send real-time notifications for every trade entry, target hit, and stop-loss event.

* **AI Market Analyzer:**
  1. Open Settings -> **AI** tab.
  2. Select your provider (`OpenAI`, `Anthropic`, or `Gemini`) and enter your **API Key**.
  3. Click **Save** and **Test Connection**.
  4. The dashboard will now display real-time, automated entry/exit suggestions generated by the AI parser based on your levels and active trades.

---

## 6. Daily Pre-Market Checklist (8:45 AM - 9:00 AM)

Make it a habit to check the system status every morning before the market opens at 9:15 AM:

- [ ] **Step 1:** Log in to your dashboard at `https://pyramid.nextginfosoft.com`.
- [ ] **Step 2:** Open **Settings** -> **Strategy** and verify/update your support/resistance levels based on morning global market indicators.
- [ ] **Step 3:** Under the Zerodha card, click **Authenticate** and complete the Zerodha login flow in the pop-up tab.
- [ ] **Step 4:** Click **Validate** to make sure the token status is active (Green dot).
- [ ] **Step 5:** Click **Load NFO Instruments** to fetch today's options contract tokens.
- [ ] **Step 6:** Click **Start Live Feed** to establish the WebSocket connection (verify options streaming count is greater than 0).
- [ ] **Step 7:** Verify your **Paper Trading** toggle status (ON for testing, OFF for live).
- [ ] **Step 8:** Click **Start Strategy** on the main dashboard.

---

## 7. Developer Releases & Executable Compilations

If you are a developer looking to package a new release version or compile the executable:
* Refer to the comprehensive developer release instructions at **[docs/RELEASE_GUIDE.md](file:///D:/PyramidStretagy_dev/docs/RELEASE_GUIDE.md)**.
* Git tag versions and build instructions are tracked there.

