# PyramidStrategy DevOps & VPS Setup Guide

This guide documents the complete end-to-end DevOps pipeline and server configuration for **PyramidStrategy**.

---

## 1. System Architecture

```mermaid
graph TD
    User([Developer]) -->|Push to dev| GitDev[GitHub: dev branch]
    User -->|Merge PR to main| GitMain[GitHub: main branch]

    subgraph GitHub Actions
        CI_Staging[CI & Staging CD]
        CD_Prod[Production CD]
    end

    GitDev --> CI_Staging
    GitMain --> CD_Prod

    subgraph Contabo VPS (Debian 12)
        NginxProxy[Host Nginx Reverse Proxy & SSL]
        
        subgraph Staging Environment
            StagingApp[Docker Containers]
            StagingPort[Mapped to Port 8080]
        end

        subgraph Production Environment
            ProdApp[Docker Containers]
            ProdPort[Mapped to Port 8000]
        end
    end

    CI_Staging -->|SSH Deploy| StagingApp
    CD_Prod -->|SSH Deploy| ProdApp

    NginxProxy -->|test.nextginfosoft.com| StagingPort
    NginxProxy -->|pyramid.nextginfosoft.com| ProdPort
```

---

## 2. VPS Preparation (Debian 12) - Completed

### 2.1 Update System Packages
```bash
apt update && apt upgrade -y
```

### 2.2 Install Nginx
```bash
apt install -y nginx
systemctl enable nginx
systemctl start nginx
```

### 2.3 Create Deployment Directories and Initial Clone
Create the workspaces on the VPS and perform the initial one-time git clones to establish the tracking repositories:
```bash
mkdir -p /opt/pyramidstrategy
mkdir -p /opt/pyramidstrategy-test

# Initial one-time git clones (run these on your VPS):
git clone -b dev https://github.com/nextginfosoft/PyramidStrategy.git /opt/pyramidstrategy-test
git clone -b main https://github.com/nextginfosoft/PyramidStrategy.git /opt/pyramidstrategy
```


### 2.4 Configure Nginx Reverse Proxy
Created `/etc/nginx/sites-available/pyramid` to route staging and production traffic to respective host ports:
```nginx
# 1. Staging configuration (test.nextginfosoft.com -> Port 8080)
server {
    listen 80;
    server_name test.nextginfosoft.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}

# 2. Production configuration (pyramid.nextginfosoft.com -> Port 8000)
server {
    listen 80;
    server_name pyramid.nextginfosoft.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

Enabled the site configuration and restarted Nginx:
```bash
ln -s /etc/nginx/sites-available/pyramid /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

### 2.5 Generate SSL Certificates (Let's Encrypt)
Secured both domains with HTTPS:
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d test.nextginfosoft.com -d pyramid.nextginfosoft.com
```

---

## 3. SSH Key Configuration - Completed

### 3.1 Generate SSH Key Pair (Local Machine)
Run in PowerShell on your local machine to generate the key:
```powershell
ssh-keygen -t rsa -b 4096 -f "$HOME/.ssh/id_rsa"
```
*(Left passphrase empty by hitting Enter twice)*

### 3.2 Register Public Key on the VPS
1. Print the public key on your local machine:
   ```powershell
   Get-Content C:\Users\SANTOSH\.ssh\id_rsa.pub
   ```
2. Log into the VPS as root and add the public key string to the authorized keys list:
   ```bash
   mkdir -p ~/.ssh
   nano ~/.ssh/authorized_keys
   # Paste key, save and exit (Ctrl+O, Enter, Ctrl+X)
   chmod 700 ~/.ssh
   chmod 600 ~/.ssh/authorized_keys
   ```

---

## 4. Docker Compose Override Configuration

To route Staging and Production frontends to ports **8080** and **8000** without conflicts, we have removed the default `ports` mapping (`80:80`) from the base `docker-compose.yml`. In addition, we removed hardcoded `container_name` attributes and database/redis `ports` mapping from the base configuration so multiple environments can run on the same Docker host concurrently.

> [!NOTE]
> **Why are overrides needed?**
> Docker Compose merges list fields (like `ports`) by **appending** instead of overwriting them. Removing host-bound ports (like 5432, 6379, 8000) and using `docker-compose.override.yml` for host-facing HTTP ports prevents port conflicts between instances. Deleting the `container_name` entries allows Docker to automatically namespace container names dynamically.

### 4.1 On Staging Server (`/opt/pyramidstrategy-test`)
Create `docker-compose.override.yml`:
```bash
nano /opt/pyramidstrategy-test/docker-compose.override.yml
```
Add the following content (specifying the staging API URLs to build with):
```yaml
services:
  frontend:
    build:
      context: ./frontend
      args:
        - VITE_API_BASE_URL=https://test.nextginfosoft.com/api
        - VITE_WS_URL=wss://test.nextginfosoft.com/ws
    ports:
      - "8080:80"
```

### 4.2 On Production Server (`/opt/pyramidstrategy`)
Create `docker-compose.override.yml`:
```bash
nano /opt/pyramidstrategy/docker-compose.override.yml
```
Add the following content:
```yaml
services:
  frontend:
    ports:
      - "8000:80"
```

---

## 5. GitHub Repository Secrets Setup - Completed

Secrets have been added to the repository page on **GitHub → Settings → Secrets and variables → Actions**.

### Configure Secrets List:
| Secret Name | Value |
| :--- | :--- |
| `TEST_VPS_HOST` | Staging VPS IP |
| `TEST_VPS_USER` | `root` |
| `TEST_VPS_SSH_KEY` | Contents of `C:\Users\SANTOSH\.ssh\id_rsa` on your local machine |
| `PROD_VPS_HOST` | Production VPS IP |
| `PROD_VPS_USER` | `root` |
| `PROD_VPS_SSH_KEY` | Contents of `C:\Users\SANTOSH\.ssh\id_rsa` on your local machine |
| `DB_PASSWORD` | Strong password for Postgres DB |

> [!NOTE]
> **Important Paste Location Warning:**
> When adding `TEST_VPS_SSH_KEY` or `PROD_VPS_SSH_KEY`, ensure you paste the key name (`TEST_VPS_SSH_KEY`) in the **Name** input field, and paste the actual key text (including headers and footers) in the large **Secret** text box. Paste names cannot contain special characters like dashes or beginning hyphens.


---

## 6. GitHub Actions Workflows

Create these configuration files inside your repository:

### 6.1 `.github/workflows/ci.yml` (CI + Staging CD)
Save to `.github/workflows/ci.yml`:
```yaml
name: CI/CD — Staging Pipeline

on:
  push:
    branches: [dev]
  pull_request:
    branches: [main]

jobs:
  test-and-validate:
    runs-on: ubuntu-latest
    name: test-and-validate

    steps:
      - uses: actions/checkout@v4

      # --- BACKEND ---
      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: 'backend/requirements.txt'

      - name: Install backend dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt flake8

      - name: Backend Lint Check
        run: flake8 backend/app/ --max-line-length=120 --ignore=E501,W293,W291,W503,W292,E712,E302,E303,E305,E402,E701,E127,E261,F401,F811,F841,F541

      - name: Run Backend Tests
        env:
          DATABASE_URL: "sqlite:///:memory:"
          USE_FAKE_REDIS: true
          ENVIRONMENT: test
          MOCK_TIME: "10:00"
        run: |
          cd backend
          pytest tests/ -v --tb=short

      # --- FRONTEND ---
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: 'frontend/package-lock.json'

      - name: Install frontend dependencies
        run: |
          cd frontend
          npm ci

      - name: Frontend Build check
        run: |
          cd frontend
          npm run build

      # --- DOCKER BUILD CHECKS ---
      - name: Docker build backend check
        run: docker build -t pyramid-backend ./backend

      - name: Docker build frontend check
        run: docker build -t pyramid-frontend ./frontend

  deploy-staging:
    needs: test-and-validate
    if: github.event_name == 'push' && github.ref == 'refs/heads/dev'
    runs-on: ubuntu-latest

    steps:
      - name: Deploy to Staging VPS via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.TEST_VPS_HOST }}
          username: ${{ secrets.TEST_VPS_USER }}
          key: ${{ secrets.TEST_VPS_SSH_KEY }}
          script: |
            cd /opt/pyramidstrategy-test
            git pull origin dev
            docker compose build --no-cache
            docker compose up -d
            docker system prune -f
            echo "✅ Deployed to Staging (test.nextginfosoft.com) at $(date)"
```

### 6.2 `.github/workflows/cd.yml` (Production CD)
Save to `.github/workflows/cd.yml`:
```yaml
name: CD — Production Pipeline

on:
  push:
    branches: [main]

jobs:
  deploy-production:
    runs-on: ubuntu-latest

    steps:
      - name: Deploy to Production VPS via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PROD_VPS_HOST }}
          username: ${{ secrets.PROD_VPS_USER }}
          key: ${{ secrets.PROD_VPS_SSH_KEY }}
          script: |
            cd /opt/pyramidstrategy
            git pull origin main
            docker compose build --no-cache
            docker compose up -d
            docker system prune -f
            echo "✅ Deployed to Production (pyramid.nextginfosoft.com) at $(date)"
```

---

## 7. Troubleshooting & Common Gotchas

These are the real-world formatting and configuration issues encountered during the setting up of the Staging environment and their permanent fixes.

### 7.1 Nginx Startup Crash: `host not found in upstream "backend"`
* **Symptoms**: The `pyramid_frontend` container keeps restarting and logs `[emerg] host not found in upstream "backend"`.
* **Cause**: Nginx starts up so fast that it attempts to resolve the Docker hostname `backend` before the internal Docker DNS resolver has initialized it on the network. If Nginx fails to resolve it at start, it immediately crashes.
* **Fix**: Change `frontend/nginx.conf` to resolve the host dynamically using variables and specifying the Docker resolver (`127.0.0.11`):
  ```nginx
  location /api/ {
      resolver 127.0.0.11 ipv6=off valid=30s;
      set $upstream_api http://backend:8000;
      rewrite ^/api/(.*)$ /$1 break;
      proxy_pass $upstream_api;
  }
  ```

### 7.2 Docker Compose Port Concatenation (Port 80 address already in use)
* **Symptoms**: Running `docker compose up -d` fails with `failed to bind host port 0.0.0.0:80/tcp: address already in use` even though the override lists `"8080:80"`.
* **Cause**: Docker Compose merges arrays/lists (like `ports:`) by **concatenating (appending)** them instead of overwriting them. Therefore, Nginx tries to bind to both `80:80` and `8080:80`.
* **Fix**: Remove the default `ports: - "80:80"` section from the base `docker-compose.yml`. Keep the port mappings completely isolated in the staging/production `docker-compose.override.yml` files.

### 7.3 Invalid Indentation in `docker-compose.override.yml`
* **Symptoms**: Docker compose up throws `services must be a mapping` or silently ignores overrides.
* **Cause**: YAML requires root-level keywords (such as `services:`) to have **0 indentation spaces** at the start of the line.
* **Fix**: Ensure the override file starts with `services:` aligned to column 0:
  ```yaml
  services:
    frontend:
      ports:
        - "8080:80"
  ```
  *(To write the override file cleanly from terminal without copy-paste formatting issues, run: `printf "services:\n  frontend:\n    ports:\n      - \"8080:80\"\n" > docker-compose.override.yml`)*

### 7.4 Invalid YAML Workflow File Syntax: Colons in Unquoted Strings
* **Symptoms**: GitHub Actions throws `Invalid workflow file: You have an error in your yaml syntax`.
* **Cause**: The YAML parser interprets unquoted colons inside strings (such as `sqlite:///:memory:`) as keys/delimiters, failing the parsing check.
* **Fix**: Wrap strings containing colons in double quotes:
  ```yaml
  DATABASE_URL: "sqlite:///:memory:"
  ```

### 7.5 GitHub Secret Names Error
* **Symptoms**: GitHub throws validation error: `Secret names can only contain alphanumeric characters...`.
* **Cause**: Pasting the entire multiline SSH key block in the **Name** input field instead of the **Value (Secret)** field, or having trailing/leading spaces in the secret name.
* **Fix**: Type the secret name (e.g., `TEST_VPS_SSH_KEY`) manually in the Name field without copy-pasting to prevent copying trailing spaces, and paste the actual key block in the large Secret/Value input area.

