# Wger Mobile Apps Setup Guide

Complete guide for configuring Wger mobile apps to work with PMOVES.AI's self-hosted instance.

## Table of Contents

1. [Overview](#overview)
2. [Android Setup](#android-setup)
3. [iOS Setup](#ios-setup)
4. [HTTPS Configuration](#https-configuration)
5. [Tailscale Networking](#tailscale-networking)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)

---

## Overview

Wger provides official mobile apps for both Android and iOS platforms. These apps connect to self-hosted instances to track workouts, weight, and body measurements on the go.

### Prerequisites

- PMOVES.AI stack running with Wger service
- Wger UI accessible at `http://localhost:8000` or via HTTPS proxy
- Django admin account created
- REST API token generated

### Quick Start

1. Start PMOVES.AI Wger service: `make -C pmoves up-wger`
2. Generate API token from Wger UI
3. Install mobile app (Android or iOS)
4. Configure server URL
5. Login with Django credentials

---

## Android Setup

### Installation Methods

#### Option 1: F-Droid (Recommended)

1. Install F-Droid from [https://f-droid.org/](https://f-droid.org/)
2. Search for "Wger Workout Manager"
3. Install the app

#### Option 2: Google Play Store

1. Open Play Store
2. Search for "Wger Workout Manager"
3. Install the app

#### Option 3: APK Direct Download

1. Download from [GitHub Releases](https://github.com/wger-project/flutter-app/releases)
2. Enable "Install from unknown sources" in settings
3. Install the APK

### Configuration Steps

1. **Open Wger App**

2. **Enter Server URL**
   - Tap "Server URL" field
   - Enter one of:
     - `https://8000.localhost` (Pinokio HTTPS proxy - Recommended)
     - Your Tailscale URL (e.g., `https://100.x.y.z:8000`)
     - Your public URL (if configured with reverse proxy)

3. **Generate API Token**
   - Open browser to `http://localhost:8000/api/v2/token/`
   - Login with Django admin credentials
   - Click "Generate Token"
   - Copy the token string

4. **Login to App**
   - Enter Django username/email
   - Enter Django password
   - App will automatically use API token for data sync

### Testing Connection

1. Navigate to "Workouts" tab
2. You should see your existing workouts (if any)
3. Try creating a test workout
4. Sync should happen automatically

---

## iOS Setup

### Installation

1. Open App Store
2. Search for "Wger Workout Manager"
3. Install the app

### Configuration Steps

iOS setup is identical to Android, with the same server URL options.

### iOS-Specific Notes

- iOS requires HTTPS for all API connections
- Use Pinokio HTTPS proxy (`https://8000.localhost`) or Tailscale
- Self-signed certificates require profile installation (not recommended)

---

## HTTPS Configuration

Wger mobile apps require HTTPS for secure communication. PMOVES.AI provides two options:

### Option 1: Pinokio HTTPS Proxy (Recommended)

Pinokio automatically provides HTTPS endpoints for all HTTP services.

**Server URL:** `https://8000.localhost`

**How it works:**
- Pinokio creates an HTTPS reverse proxy
- Automatically handles SSL certificates
- Works on localhost without DNS configuration
- Port 8000 HTTP becomes `https://8000.localhost`

**Verification:**
```bash
# Test HTTPS proxy
curl -k https://8000.localhost/healthz/
# Expected: {"status": "healthy"}
```

### Option 2: Tailscale

Tailscale provides secure networking to your PMOVES.AI instance from anywhere.

**Setup Steps:**

1. **Install Tailscale on PMOVES.AI host**
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

2. **Get Tailscale IP**
   ```bash
   tailscale ip -4
   # Example: 100.x.y.z
   ```

3. **Configure Mobile App**
   - Server URL: `https://100.x.y.z:8000` (use your Tailscale IP)
   - Tailscale provides automatic HTTPS with valid certificates

4. **Install Tailscale on Mobile Device**
   - Install Tailscale app from App Store/Play Store
   - Login to same Tailscale account
   - Enable "VPN" to connect to PMOVES.AI network

**Benefits:**
- Access from anywhere (not just local network)
- Automatic HTTPS with valid certificates
- End-to-end encryption
- No port forwarding required

### Option 3: Reverse Proxy (Advanced)

For production deployments with public domain names.

**Prerequisites:**
- Public domain name (e.g., `wger.example.com`)
- DNS A record pointing to your server
- SSL certificate (Let's Encrypt recommended)

**Configuration Example:**

```bash
# Generate certificate
sudo certbot certonly --standalone -d wger.example.com

# Configure Nginx reverse proxy
sudo nano /etc/nginx/sites-available/wger
```

```nginx
server {
    listen 443 ssl;
    server_name wger.example.com;

    ssl_certificate /etc/letsencrypt/live/wger.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/wger.example.com/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Mobile App Configuration:**
- Server URL: `https://wger.example.com`

---

## Tailscale Networking

Tailscale is the recommended solution for remote access to PMOVES.AI services.

### Architecture

```
Mobile Device (Tailscale Client)
    ↓ (Tailscale VPN)
PMOVES.AI Host (Tailscale Node)
    ↓ (Docker Network)
Wger Container (port 8000)
```

### Setup Steps

1. **Install Tailscale on Host**
   ```bash
   # Linux
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up

   # macOS
   brew install tailscale
   sudo tailscale up
   ```

2. **Configure Tailscale**
   - Login to Tailscale account
   - Enable "Key expiry" for security
   - Note your Tailscale IP address

3. **Install Tailscale on Mobile**
   - iOS: Download from App Store
   - Android: Download from Play Store
   - Login to same Tailscale account

4. **Connect Mobile App**
   - Enable Tailscale VPN on mobile device
   - Configure Wger app with Tailscale URL: `https://<tailscale-ip>:8000`

5. **Test Connection**
   ```bash
   # From mobile device (with Tailscale connected)
   curl https://<tailscale-ip>:8000/healthz/
   # Expected: {"status": "healthy"}
   ```

### Tailscale ACLs (Optional)

For multi-user deployments, configure Tailscale ACLs to control access:

```json
{
  "acls": [
    {
      "action": "accept",
      "users": ["*"],
      "ports": ["wger-server:8000"]
    }
  ]
}
```

---

## Troubleshooting

### Connection Refused

**Problem:** App shows "Connection refused" error

**Solutions:**
1. Verify Wger service is running:
   ```bash
   docker ps | grep wger
   ```

2. Check service health:
   ```bash
   curl http://localhost:8000/healthz/
   ```

3. Verify port is exposed:
   ```bash
   netstat -tuln | grep 8000
   ```

4. Check firewall rules:
   ```bash
   # Windows
   netsh advfirewall firewall show rule name="Docker Port 8000"

   # Linux
   sudo ufw status
   ```

### SSL Certificate Errors

**Problem:** App shows "SSL certificate invalid" error

**Solutions:**
1. Use Pinokio HTTPS proxy: `https://8000.localhost`
2. Use Tailscale for valid certificates
3. Install proper reverse proxy with Let's Encrypt

### Authentication Failed

**Problem:** App shows "Authentication failed" error

**Solutions:**
1. Verify Django credentials:
   ```bash
   docker exec -it pmoves-wger python manage.py createsuperuser
   ```

2. Generate new API token:
   - Visit `http://localhost:8000/api/v2/token/`
   - Login with Django admin
   - Generate new token

3. Check `WGER_ENABLE_REGISTRATION` setting:
   ```bash
   grep WGER_ENABLE_REGISTRATION env.shared
   # Should be: WGER_ENABLE_REGISTRATION=true
   ```

### Sync Not Working

**Problem:** Data not syncing between app and server

**Solutions:**
1. Check NATS connection:
   ```bash
   docker logs pmoves-wger | grep NATS
   ```

2. Verify API token is valid:
   ```bash
   curl -H "Authorization: Token YOUR_TOKEN" http://localhost:8000/api/v2/workout/
   ```

3. Check app logs for errors:
   - Android: Settings → About → Debug Logs
   - iOS: Settings → Export Debug Logs

### Slow Performance

**Problem:** App is slow to load data

**Solutions:**
1. Check server response time:
   ```bash
   time curl http://localhost:8000/api/v2/workout/
   ```

2. Verify database performance:
   ```bash
   docker exec pmoves-wger-db pgbench -c 10 -j 2 -t 1000
   ```

3. Check network latency:
   - Use local Wi-Fi instead of cellular
   - Use Tailscale instead of public internet

---

## FAQ

### Q: Can I use multiple mobile devices with one account?

A: Yes, multiple devices can sync to the same Wger instance. Each device needs the server URL and your Django credentials.

### Q: Does the mobile app work offline?

A: Yes, Wger mobile apps support offline mode. Workouts logged offline will sync when connection is restored.

### Q: How do I backup my mobile app data?

A: Wger data is stored on the server, not the mobile app. Simply backup your Wger database:

```bash
# Backup Wger PostgreSQL database
docker exec pmoves-wger-db pg_dump -U wger wger > wger_backup.sql
```

### Q: Can I use the mobile app without the server?

A: No, the mobile app requires a connection to a Wger server. The app is a client interface, not a standalone app.

### Q: Is my data secure?

A: Yes, data is encrypted in transit (HTTPS) and at rest (PostgreSQL). Use Tailscale for additional security when accessing from public networks.

### Q: How do I update the mobile app?

A:
- **Android:** Check Play Store/F-Droid for updates
- **iOS:** Check App Store for updates
- Updates are released independently of the PMOVES.AI server

### Q: Can I sync data with other fitness apps?

A: Wger supports export to CSV/JSON, which can be imported into other fitness apps. Check Wger documentation for the latest integration options.

### Q: What if I forget my password?

A: Reset your Django password via the admin panel:
```bash
docker exec -it pmoves-wger python manage.py changepassword <username>
```

---

## Additional Resources

- **Wger Documentation:** [https://wger.readthedocs.io/](https://wger.readthedocs.io/)
- **PMOVES.AI Health Integration:** `PMOVES.AI_INTEGRATION.md`
- **Tailscale Documentation:** [https://tailscale.com/kb/](https://tailscale.com/kb/)
- **Pinokio Documentation:** `D:\pinokio\prototype\README.md`

## Support

For issues specific to PMOVES.AI integration:
1. Check `PMOVES.AI_INTEGRATION.md` for troubleshooting
2. Review service logs: `docker logs pmoves-wger`
3. Check health status: `curl http://localhost:8000/healthz/`

For issues with the mobile app itself:
- Report issues at [Wger GitHub Issues](https://github.com/wger-project/flutter-app/issues)
- Check [Wger Community Forum](https://community.wger.de/)

---

**Last Updated:** 2026-03-13
**PMOVES.AI Version:** Production (Stage P)
**Wger Version:** Latest PMOVES.AI Edition (Hardened)
