# PyramidStrategy — Developer Release Guide

This document tracks local version releases, documents the steps to check previous release history, and details the commands needed to compile and publish new versions.

---

## 1. Local Version History (Changelog)

This is a local record of the versions tagged and published in this repository:

| Version | Release Date | Trigger Branch | Description / Major Changes |
| :--- | :--- | :--- | :--- |
| **`v1.1.8`** | 2026-07-13 | `main` | Reduced minimum required account margin check from ₹50,000 to ₹15,000 in safety checks. |
| **`v1.1.7`** | 2026-07-13 | `main` | Fixed `AttributeError` for `'KiteService' object has no attribute 'kite'` by exposing a property wrapper on `KiteService`. |
| **`v1.1.6`** | 2026-07-13 | `main` | Fixed daily EOD PDF report to trigger immediately on force square-off. |
| **`v1.1.5`** | 2026-07-13 | `main` | Added emergency exit override kill-switch and restored blocked levels on engine start. |
| **`v1.1.4`** | 2026-07-08 | `main` | Fixed paper trade entry price discrepancy by fetching actual live price on entry when Kite ticker is active, and resolved status bar missing session start time. |
| **`v1.1.3`** | 2026-07-07 | `main` | Fixed paper trade post-exit tracking by removing the `mock_mode` early return in `on_option_tick`, and resolved PEP 8 continuation line indentation warnings in `strategy_engine.py`. |
| **`v1.1.2`** | 2026-07-07 | `main` | Fixed option LTP and post-exit tracking in paper trade mode (estimates option prices ONLY if live ticker is not running). |
| **`v1.1.1`** | 2026-07-07 | `main` | Fixed duplicate logging, Telegram EOD report markdown parsing, and Gemini fallback on 5xx errors. |
| **`v1.1.0`** | 2026-07-05 | `dev` | Added Live Option Leg Range Tracking (Active Extremes / Min-Max price range) with a visual progress bar on the Dashboard, an Active Range column in the Trade Log table, and corresponding database and CSV export fields. |
| **`v1.0.1`** | 2026-07-04 | `dev` | Fixed packaged executable run-time issue where fakeredis could not locate the commands.json metadata file. Bundled the missing JSON asset in the PyInstaller spec. |
| **`v1.0.0`** | 2026-07-04 | `dev` | Initial release setup. Fixed packaged executable UI loading, bypassed Uvicorn logging config errors, resolved CORS/domain origin mismatches, and created automated GitHub Release workflow. |

---

## 2. Managing Version Tags via Command Line

Git stores release tags directly in the local repository. You can use these commands to inspect them:

* **List all previous tags with their release messages:**
  ```powershell
  git tag -n
  ```
* **View the commit and details associated with a specific version tag (e.g. `v1.0.0`):**
  ```powershell
  git show v1.0.0
  ```
* **Fetch the latest tags from GitHub remote if working on a different machine:**
  ```powershell
  git fetch --tags
  ```

---

## 3. How to Release a New Version (Automated via GitHub Actions)

To release a new version of the app to your end users using GitHub Actions:

### Step 3.1: Commit and Push Your Code Changes
Make your changes, commit them, and push them to your repository:
```powershell
git add .
git commit -m "feat: Describe your new feature or bug fix"
git push origin dev
```

### Step 3.2: Tag the Code with a New Version Number
Increment your version based on the changes (e.g., from `v1.0.0` to `v1.0.1` or `v1.1.0`):
```powershell
# Create the local tag
git tag v1.0.1 -m "Release description message"

# Push the tag to GitHub
git push origin v1.0.1
```
*Once pushed, GitHub Actions automatically handles frontend compiling, PyInstaller packaging, zipping, and publishes `PyramidStrategy_Windows.zip` on your repository's **Releases** page.*

---

## 4. How to Build the Executable Manually (Local Environment)

If you ever need to compile the executable manually on your local computer instead of using GitHub:

### Step 4.1: Compile the Frontend UI
Ensure the React code is fully built into production assets first:
```powershell
cd frontend
npm run build
cd ..
```

### Step 4.2: Terminate any Running Instances
Close any background instances of `PyramidStrategy.exe` to unlock internal DLLs:
```powershell
taskkill /F /IM PyramidStrategy.exe
```

### Step 4.3: Compile the Backend using PyInstaller
Activate your virtual environment and run the PyInstaller command:
```powershell
cd backend
venv\Scripts\activate
cd ..
pyinstaller --clean -y PyramidStrategy.spec
```
*The compiled folder containing the entrypoint `PyramidStrategy.exe` and `_internal` files will be output to the `dist/PyramidStrategy` directory.*
