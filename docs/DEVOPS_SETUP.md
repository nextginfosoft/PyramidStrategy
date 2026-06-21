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

## 4. Docker Compose Override Configuration (Next Step)

To route Staging and Production frontends to ports **8080** and **8000** without changing the main `docker-compose.yml` file, configure Docker Compose Overrides directly on the VPS.

### 4.1 On Staging Server (`/opt/pyramidstrategy-test`)
Create `docker-compose.override.yml`:
```bash
nano /opt/pyramidstrategy-test/docker-compose.override.yml
```
Add the following content:
```yaml
services:
  frontend:
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
