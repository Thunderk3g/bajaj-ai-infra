# Certificates

Place CA / TLS certificates required by the VM here. This directory is tracked
(via `.gitkeep`) but the certificate files themselves are **git-ignored**
(`*.pem`, `*.crt`, `*.key`) — never commit private keys.

## How to add certs

1. Copy your organization's CA bundle onto the VM:

   ```bash
   sudo cp my-ca.crt /opt/shared/certs/
   ```

2. If a container needs to trust the CA, mount it in that container's
   `docker-compose.yml`, e.g.:

   ```yaml
   volumes:
     - ./certs/my-ca.crt:/etc/ssl/certs/my-ca.crt:ro
   ```

3. For TLS termination at nginx, place `server.crt` / `server.key` here and
   reference them from `shared/nginx.conf` (add a `listen 443 ssl;` server).

## Files (all git-ignored)

| File          | Purpose                          |
|---------------|----------------------------------|
| `*.crt`       | Public certificate / CA bundle   |
| `*.pem`       | PEM-encoded cert or chain        |
| `*.key`       | Private key — keep secret        |
