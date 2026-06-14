# Docker Deployment Troubleshooting Guide

This guide documents key troubleshooting steps, root causes, and resolutions for issues encountered during the Docker containerization and VPS deployment of **PyramidStrategy**.

---

## 1. Authentication failed — please try again (UI Login Error)

### Symptom:
When attempting to log in to the dashboard via the VPS browser URL, the UI displays `Authentication failed — please try again` or does not respond.

### Root Causes & Solutions:

#### Cause A: Empty PostgreSQL Database on Initial Startup
* **Explanation:** Unlike your local development environment which might contain pre-existing SQLite data, spinning up Docker Compose for the first time starts a completely fresh PostgreSQL database container (`pyramid_db`). Tables are created automatically, but no user accounts exist.
* **Resolution:**
  1. On the dashboard login page, click **"Don't have an account? Sign Up"** at the bottom.
  2. Register your desired username and password.
  3. Switch back to "Sign In" and log in with your newly registered credentials.

#### Cause B: API Calls Routed to `localhost` instead of VPS IP
* **Explanation:** In `docker-compose.yml`, the frontend build arguments (`VITE_API_BASE_URL`) compile the React application at build-time. If configured as `http://localhost`, the frontend in your browser will try to contact `http://localhost/api/session/login` (your local computer) instead of the VPS IP, triggering a connection failure.
* **Resolution:**
  1. Open `docker-compose.yml` on your VPS.
  2. Update the `frontend` service build arguments to use your VPS IP or public domain:
     ```yaml
     frontend:
       build:
         context: ./frontend
         args:
           - VITE_API_BASE_URL=http://your_vps_ip/api
           - VITE_WS_URL=ws://your_vps_ip/ws
     ```
  3. Rebuild the frontend container:
     ```bash
     sudo docker compose up -d --build
     ```

---

## 2. Backend Crashing: `ModuleNotFoundError: No module named 'psycopg2'`

### Symptom:
The `pyramid_backend` container continuously restarts. Checking `docker compose logs backend` reveals a Python traceback ending with:
`ModuleNotFoundError: No module named 'psycopg2'`

### Root Cause:
* **Explanation:** In local development, the application defaults to SQLite (which uses Python's built-in `sqlite3`/`aiosqlite` drivers). In production, Docker Compose connects to PostgreSQL. Python requires the PostgreSQL adapter library (`psycopg2`) to establish this connection, but it was missing from `requirements.txt`.

### Resolution:
1. Append the pre-compiled PostgreSQL driver to `backend/requirements.txt`:
   ```text
   # PostgreSQL driver for production Docker
   psycopg2-binary>=2.9.9
   ```
2. Pull and rebuild the containers on your VPS:
   ```bash
   git pull
   sudo docker compose down
   sudo docker compose up -d --build
   ```

---

## 3. Backend Crashing: `ModuleNotFoundError: No module named 'pytz'`

### Symptom:
The `pyramid_backend` container continuously restarts. Checking `docker compose logs backend` reveals a traceback ending with:
`ModuleNotFoundError: No module named 'pytz'` inside `time_rules.py`.

### Root Cause:
* **Explanation:** Timezone-aware functions in `app/core/time_rules.py` depend on the `pytz` package. While this package was present in local virtual environments, it was not explicitly pinned in `backend/requirements.txt`, preventing it from installing inside the clean Docker environment.

### Resolution:
1. Append `pytz` to `backend/requirements.txt`:
   ```text
   # Timezone support
   pytz>=2024.1
   ```
2. Pull and rebuild the containers on your VPS:
   ```bash
   git pull
   sudo docker compose down
   sudo docker compose up -d --build
   ```

---

## 4. Local Virtual Environment and Cache Pollution

### Symptom:
Weird architecture mismatch errors, outdated Python files executing, or container build slowdowns.

### Root Cause:
* **Explanation:** Without a `.dockerignore` file, when the Docker engine runs `COPY . .` inside `backend/Dockerfile` or `frontend/Dockerfile`, it copies the local development directories (like `venv/`, `node_modules/`, and `.pytest_cache/`) from the host machine directly into the Docker context. This pollutes the build environment and can cause unexpected cross-platform runtime bugs.

### Resolution:
Created and added `.dockerignore` files at the root, `backend/`, and `frontend/` contexts to ignore:
* Python virtual environments (`venv/`, `.venv/`)
* JavaScript dependency folders (`node_modules/`)
* Build caches (`.pytest_cache/`, `dist/`, `__pycache__/`)
* Local SQLite databases (`*.db`) and execution logs (`*.log`)

Ensure these files are pulled on your VPS before doing any subsequent container builds.
