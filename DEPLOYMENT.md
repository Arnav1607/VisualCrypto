# VisualCrypto: Production Deployment Guide

This guide covers everything required to deploy **VisualCrypto** into production across multiple environments, including **Docker**, **Cloud Platforms (Render, Railway, Fly.io, Heroku)**, and **Traditional Linux / Windows Servers**.

---

## 🚀 Quick Reference: Deployment Matrix

| Platform | Deployment Type | Command / File | Recommended For |
| :--- | :--- | :--- | :--- |
| **Docker** | Containerized | `docker compose up -d` | Self-hosted, VPS, Kubernetes |
| **Render** | Cloud (PaaS) | [render.yaml](render.yaml) | Free & instant cloud hosting |
| **Railway / Heroku** | Cloud (PaaS) | [Procfile](Procfile) | Continuous Git deployment |
| **Linux VPS (Ubuntu)** | Nginx + Gunicorn | `gunicorn wsgi:app` | Dedicated infrastructure |
| **Windows Server** | Waitress WSGI | `python wsgi.py` | Windows on-premise servers |

---

## 1. Containerized Deployment (Docker & Docker Compose)

The repository includes a production-hardened `Dockerfile` running Python 3.11-slim, a non-root application user, built-in health monitoring, and Gunicorn WSGI.

### Single-Command Run with Docker Compose:
```cmd
docker compose up -d --build
```
The application will be live at: `http://localhost:5000`

### Manual Docker Build & Run:
```cmd
# 1. Build the production image
docker build -t visualcrypto:latest .

# 2. Run the container
docker run -d -p 5000:5000 --name visualcrypto visualcrypto:latest

# 3. Check container logs
docker logs -f visualcrypto

# 4. Check health status
curl http://localhost:5000/health
```

---

## 2. Deploying to Render.com (Free Tier Cloud Hosting)

Render provides free automated hosting directly connected to your GitHub repository.

### Option A: Using the Render Blueprint (`render.yaml`)
1. Push your repository to GitHub.
2. Log into [Render.com](https://render.com).
3. Click **New +** $\rightarrow$ **Blueprint**.
4. Select your `VisualCrypto` repository. Render will automatically read `render.yaml`, configure Python 3.11, set up environment variables, and launch the service.

### Option B: Manual Web Service Setup on Render
1. Click **New +** $\rightarrow$ **Web Service**.
2. Connect your GitHub repository.
3. Configure settings:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn wsgi:app`
   - **Health Check Path:** `/health`
4. Click **Deploy Web Service**.

---

## 3. Deploying to Railway or Heroku

VisualCrypto includes a standard `Procfile` (`web: gunicorn wsgi:app`):

### Railway:
1. Go to [railway.app](https://railway.app) $\rightarrow$ **New Project**.
2. Select **Deploy from GitHub Repo**.
3. Railway automatically detects the `Dockerfile` or `Procfile` and assigns a public URL.

### Heroku:
```cmd
# Login and create app
heroku login
heroku create visualcrypto-app

# Deploy code
git push heroku main

# Open deployed app
heroku open
```

---

## 4. Production Deployment on Linux VPS (Ubuntu / Debian)

For production on a VPS (DigitalOcean, AWS EC2, Linode, Hetzner), use **Systemd** + **Gunicorn** reverse-proxied by **Nginx**.

### Step 1: Install Dependencies
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv nginx
git clone https://github.com/coduri/VisualCrypto.git /var/www/visualcrypto
cd /var/www/visualcrypto

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Configure Systemd Service
Create service file `/etc/systemd/system/visualcrypto.service`:
```ini
[Unit]
Description=VisualCrypto Gunicorn Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/visualcrypto
Environment="PATH=/var/www/visualcrypto/venv/bin"
Environment="PORT=5000"
Environment="HOST=127.0.0.1"
Environment="MAX_CONTENT_LENGTH_MB=16"
ExecStart=/var/www/visualcrypto/venv/bin/gunicorn --workers 4 --threads 2 --bind 127.0.0.1:5000 wsgi:app

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable visualcrypto
sudo systemctl start visualcrypto
```

### Step 3: Configure Nginx Reverse Proxy
Create `/etc/nginx/sites-available/visualcrypto`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/visualcrypto /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 5. Running Production on Windows (Waitress WSGI)

On Windows servers where Gunicorn is not supported, VisualCrypto includes `waitress`:

```cmd
# 1. Install production dependencies
pip install -r requirements.txt

# 2. Run with Waitress
waitress-serve --listen=0.0.0.0:5000 wsgi:app
```

---

## 🔒 Security & Performance Features in Place

1. **Concurrency Isolation:** Every upload and cryptographic share generation uses unique UUID batch tags (`uuid.uuid4().hex[:10]`), preventing race conditions and cross-user data overwriting.
2. **Safe Filename Extraction:** File uploads are filtered through `secure_filename()` to eliminate path traversal vulnerabilities.
3. **Upload Rate & Size Throttling:** `MAX_CONTENT_LENGTH` restricts payload size (default 16MB) to prevent Denial-of-Service (DoS) memory spikes.
4. **Automated Ephemeral File Purge:** An integrated cleanup mechanism removes temporary files older than 1 hour, preventing server disk exhaustion.
5. **Health Probes:** Dedicated `/health` and `/api/health` endpoints return HTTP 200 for cloud load balancers and container restarts.
