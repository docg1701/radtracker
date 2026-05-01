# Research: Self-Hosted Streamlit Deployment with Docker + Ansible

## Summary

Deploying the radtracker Streamlit app to a VPS with Docker and Ansible has clear, well-documented patterns as of 2025-2026. The recommended stack is: **Streamlit in Docker with a multi-stage build, Traefik as reverse proxy with Let's Encrypt TLS and BasicAuth middleware, SQLite persisted via a bind-mount volume, and Ansible playbooks for cleanup/deploy/update/health/backup**. For authentication, streamlit-authenticator (v0.4.3, actively maintained) provides in-app login, while Traefik's BasicAuth middleware offers a zero-code application-agnostic alternative. SQLite backups are safest via `docker exec` + `sqlite3 .backup` (the SQLite Backup API), which produces consistent snapshots without stopping the container.

---

## Findings

### 1. Streamlit + Docker Best Practices

1. **Official Dockerfile pattern** — Streamlit docs recommend a single-stage build using `python:3.x-slim`, installing dependencies from `requirements.txt`, exposing port 8501, and using the built-in `/_stcore/health` endpoint for Docker HEALTHCHECK. [Source](https://docs.streamlit.io/deploy/tutorials/docker)

   ```dockerfile
   FROM python:3.12-slim
   WORKDIR /app
   RUN apt-get update && apt-get install -y \
       curl \
       && rm -rf /var/lib/apt/lists/*
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   EXPOSE 8501
   HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
   ENTRYPOINT ["streamlit", "run", "streamlit_app.py", \
       "--server.port=8501", "--server.address=0.0.0.0"]
   ```

2. **Multi-stage builds** — For production, separate build and runtime stages reduce image size ~80%. The build stage installs compilers (gcc, build-essential), the runtime stage copies only the venv from the builder. Python 3.12+ with Debian bookworm-slim is the current best base. Non-root user recommended. [Source](https://kowashlab.com/blog/docker-multi-stage-builds-python)

   ```dockerfile
   FROM python:3.12-slim AS builder
   RUN apt-get update && apt-get install -y build-essential curl \
       && rm -rf /var/lib/apt/lists/*
   RUN python -m venv /opt/venv
   ENV PATH="/opt/venv/bin:$PATH"
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   FROM python:3.12-slim AS runtime
   RUN apt-get update && apt-get install -y curl \
       && rm -rf /var/lib/apt/lists/*
   COPY --from=builder /opt/venv /opt/venv
   ENV PATH="/opt/venv/bin:$PATH"
   RUN useradd -m -u 1000 streamlit
   USER streamlit
   WORKDIR /app
   COPY --chown=streamlit:streamlit . .
   EXPOSE 8501
   HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
       CMD curl --fail http://localhost:8501/_stcore/health
   ENTRYPOINT ["streamlit", "run", "streamlit_app.py", \
       "--server.port=8501", "--server.address=0.0.0.0"]
   ```

3. **SQLite persistence with Docker volumes** — Use a bind-mount volume to persist the SQLite database outside the container. The database directory must be writable by the container user (UID 1000 in the non-root example above). In docker-compose:

   ```yaml
   volumes:
     - ./data:/app/data  # SQLite DB lives in /app/data
   ```

4. **Streamlit production config** — Create `.streamlit/config.toml` with production settings. Key options: `server.headless = true`, `server.port`, `server.address`, `browser.gatherUsageStats = false`. The newer `server.corsAllowedOrigins` option (PR #11377) allows specifying allowed origins instead of disabling CORS entirely. [Source](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)

   ```toml
   [server]
   headless = true
   port = 8501
   address = "0.0.0.0"
   enableCORS = false        # Only if behind same-origin reverse proxy
   enableXsrfProtection = false  # Only if behind same-origin reverse proxy
   maxUploadSize = 200

   [browser]
   gatherUsageStats = false
   serverAddress = "localhost"  # or empty for default
   ```

5. **Resource limits and health checks** — Docker Compose `deploy.resources` section for memory/CPU limits. HEALTHCHECK uses Streamlit's built-in `/_stcore/health` endpoint (returns 200 when app is running). The official Docker docs for the Streamlit guide confirm this exact endpoint. [Source](https://docs.streamlit.io/deploy/tutorials/docker)

   ```yaml
   healthcheck:
     test: ["CMD", "curl", "--fail", "http://localhost:8501/_stcore/health"]
     interval: 30s
     timeout: 10s
     retries: 3
     start_period: 10s
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: "1.0"
   ```

### 2. Ansible Automation for VPS Deployment

1. **Playbook structure** — For a single-server app, use a flat playbook-per-operation structure (not heavy roles). Community consensus favors `community.docker.docker_compose_v2` module (the v2 variant, not the deprecated v1 module). Each playbook targets the same host group. [Source](https://www.ansiblepilot.com/articles/ansible-docker-compose-guide) | [Source](https://www.ansiblebyexample.com/articles/ansible-docker-build-run-manage-containers)

   ```
   ansible/
   ├── ansible.cfg
   ├── inventory.yml
   ├── group_vars/
   │   └── all.yml
   ├── playbooks/
   │   ├── cleanup.yml
   │   ├── deploy.yml
   │   ├── update.yml
   │   ├── health.yml
   │   └── backup.yml
   └── templates/
       ├── docker-compose.yml.j2
       ├── .streamlit.config.toml.j2
       └── traefik.yml.j2
   ```

2. **VPS cleanup/fresh-state pattern** — Use `community.docker.docker_compose_v2` with `state: absent` to tear down the app, then `community.docker.docker_prune` to remove unused Docker objects. For system-level cleanup, use `ansible.builtin.apt` with `autoremove: true`. Important: preserve the data volume directory. [Source](https://docs.ansible.com/ansible/latest/collections/community/docker/docker_prune_module.html)

   ```yaml
   # cleanup.yml
   - name: Stop and remove radtracker containers
     community.docker.docker_compose_v2:
       project_src: /opt/radtracker
       state: absent
       remove_orphans: true

   - name: Prune Docker system (preserve volumes)
     community.docker.docker_prune:
       containers: true
       images: true
       networks: true
       builder_cache: true

   - name: System package cleanup
     ansible.builtin.apt:
       autoremove: true
       autoclean: true
   ```

3. **Deploy playbook** — Template the docker-compose.yml and config files, install Docker if not present, pull images, start the compose stack. For a fresh VPS, the first step installs Docker using the official convenience script or the `geerlingguy.docker` role. [Source](https://www.ansiblepilot.com/articles/ansible-docker-compose-guide)

   ```yaml
   # deploy.yml
   - name: Install Docker
     block:
       - name: Install prerequisites
         ansible.builtin.apt:
           name: [ca-certificates, curl]
           state: present
       - name: Add Docker GPG key and repo
         # ... standard Docker install steps ...
       - name: Install Docker packages
         ansible.builtin.apt:
           name: [docker-ce, docker-ce-cli, containerd.io,
                  docker-buildx-plugin, docker-compose-plugin]
           state: present

   - name: Create project directory
     ansible.builtin.file:
       path: /opt/radtracker
       state: directory
       mode: "0755"

   - name: Template docker-compose.yml
     ansible.builtin.template:
       src: docker-compose.yml.j2
       dest: /opt/radtracker/docker-compose.yml

   - name: Deploy with Docker Compose
     community.docker.docker_compose_v2:
       project_src: /opt/radtracker
       state: present
       pull: always
   ```

4. **Update playbook (no data loss)** — Pull new image, then restart only the app container. The key insight: `docker-compose up -d` with `pull: always` only recreates containers whose image or config changed. The SQLite volume (bind mount) is NOT touched during container recreation. [Source](https://www.ansiblebyexample.com/articles/ansible-docker-build-run-manage-containers)

   ```yaml
   # update.yml
   - name: Pull latest image and recreate app container
     community.docker.docker_compose_v2:
       project_src: /opt/radtracker
       state: present
       pull: always
       remove_orphans: true
     # The bind-mounted ./data directory is NEVER removed.
     # Only the app container is recreated.

   - name: Wait for app to become healthy
     ansible.builtin.uri:
       url: "http://localhost:8501/_stcore/health"
       status_code: 200
     register: health_check
     until: health_check.status == 200
     retries: 12
     delay: 5
   ```

5. **Health check playbook** — Verify container is running and the health endpoint responds. Can also check Traefik dashboard or the public URL. [Source](https://docs.streamlit.io/deploy/tutorials/docker)

   ```yaml
   # health.yml
   - name: Check container is running
     community.docker.docker_container_info:
       name: radtracker
     register: container_info

   - name: Assert container state
     ansible.builtin.assert:
       that:
         - container_info.exists
         - container_info.container.State.Status == "running"
         - container_info.container.State.Health.Status == "healthy"

   - name: Check endpoint responds
     ansible.builtin.uri:
       url: "https://{{ domain }}/_stcore/health"
       status_code: 200
       validate_certs: true
   ```

6. **Backup playbook** — Execute `sqlite3 .backup` inside the running container, copy the backup file to the Ansible control node or a remote backup location. Uses the SQLite Online Backup API which is safe on live databases. [Source](https://selfhosting.sh/foundations/backup-docker-volumes/)

   ```yaml
   # backup.yml
   - name: Create timestamped backup inside container
     ansible.builtin.command:
       cmd: >
         docker exec radtracker sqlite3 /app/data/radtracker.db
         ".backup /tmp/backup_{{ ansible_date_time.epoch }}.db"
     changed_when: true

   - name: Copy backup from container
     ansible.builtin.command:
       cmd: >
         docker cp radtracker:/tmp/backup_{{ ansible_date_time.epoch }}.db
         /opt/radtracker/backups/radtracker-{{ ansible_date_time.date }}.db
     changed_when: true

   - name: Rotate backups (keep 30 days)
     ansible.builtin.shell: |
       find /opt/radtracker/backups -name "*.db" -mtime +30 -delete
     changed_when: false
   ```

### 3. Simple Authentication for Streamlit

1. **streamlit-authenticator** — Actively maintained as of 2025-2026. Latest release: **v0.4.3** (via safetycli changelog) / **v0.4.2** (PyPI, 2025-03-01). 2,075 GitHub stars, MIT license. Supports login, logout, registration, password reset, forgot password/username, 2FA, and OAuth2 (guest login for Microsoft). Works entirely locally with a YAML config file—no external SaaS. [Source](https://github.com/mkhorasani/Streamlit-Authenticator) | [Source](https://pypi.org/project/streamlit-authenticator/)

   - **Pros**: In-app login UI, user registration, password reset, config-file-based (YAML), no external dependencies
   - **Cons**: Adds Python dependency, requires code changes to your Streamlit app, config file must be managed
   - **Simple usage**:
     ```python
     import streamlit_authenticator as stauth

     # One-time: generate hashed passwords
     # hashed = stauth.Hasher.hash(["password1", "password2"])

     config = {
         "credentials": {
             "usernames": {
                 "admin": {
                     "name": "Admin User",
                     "password": "$2b$12$...",  # pre-hashed
                 }
             }
         },
         "cookie": {"name": "radtracker", "key": "some_signature_key", "expiry_days": 30},
     }

     authenticator = stauth.Authenticate(
         config["credentials"],
         config["cookie"]["name"],
         config["cookie"]["key"],
         config["cookie"]["expiry_days"],
     )
     authenticator.login()
     if st.session_state["authentication_status"]:
         authenticator.logout()
         st.write(f"Welcome {st.session_state['name']}")
         # ... your app logic ...
     elif st.session_state["authentication_status"] is False:
         st.error("Username/password is incorrect")
     ```

2. **Nginx basic auth (htpasswd)** — Works with Streamlit but requires careful WebSocket header forwarding. The known issue (#8223) is that Streamlit's WebSocket connection (used for live reload, widget state) breaks behind basic auth unless `proxy_http_version`, `Upgrade`, and `Connection` headers are set. The fix is well-documented. The `andfanilo/streamlit-nginx-basicauth` repo (2023) provides a working example. [Source](https://github.com/streamlit/streamlit/issues/8223) | [Source](https://github.com/andfanilo/streamlit-nginx-basicauth)

   - **Required nginx config for Streamlit websockets behind basic auth**:
     ```nginx
     server {
         listen 80;
         server_name your-domain.com;

         auth_basic "Restricted";
         auth_basic_user_file /etc/nginx/.htpasswd;

         location / {
             proxy_pass http://streamlit:8501;
             proxy_http_version 1.1;
             proxy_set_header Upgrade $http_upgrade;
             proxy_set_header Connection "upgrade";
             proxy_set_header Host $host;
             proxy_set_header X-Real-IP $remote_addr;
             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
             proxy_set_header X-Forwarded-Proto $scheme;
         }
     }
     ```

3. **Traefik BasicAuth middleware** — The simplest approach for Traefik-based setups. Uses Docker labels or dynamic config. Generate the `users` string with `htpasswd -nb admin password`. Traefik v3.4 is the current version. No code changes to the Streamlit app needed. [Source](https://doc.traefik.io/traefik/middlewares/http/basicauth/) | [Source](https://github.com/JensKnipper/traefik-examples/blob/master/authentication/basic-authentication/docker-compose.yml)

   ```yaml
   # Docker Compose labels on the streamlit service:
   labels:
     - "traefik.http.routers.radtracker.middlewares=radtracker-auth"
     - "traefik.http.middlewares.radtracker-auth.basicauth.users=admin:$$2y$$12$$..."
   ```
   The `$$` is needed in docker-compose YAML to escape the `$` in bcrypt hashes.

4. **Streamlit's built-in auth** — Streamlit has **no built-in authentication**. The core team has consistently deferred this to external solutions. The `secrets.toml` mechanism is for API keys and config values, not user auth. [Source - confirmed by absence in config docs](https://docs.streamlit.io/develop/api-reference/configuration/config.toml)

5. **Recommendation for radtracker**: Use **Traefik BasicAuth** as the primary auth layer (zero code changes, one config line). Add **streamlit-authenticator** only if you need multiple user accounts with different access levels. For a single-user dashboard, Traefik BasicAuth alone is the simplest option.

### 4. Docker + Reverse Proxy (Traefik vs Nginx)

1. **Minimal docker-compose.yml with Traefik + Streamlit** — Traefik is the recommended choice for simplicity: it auto-discovers Docker containers via labels, auto-provisions Let's Encrypt certificates, and BasicAuth is a single label. Traefik v3.4 is the current release. [Source](https://doc.traefik.io/traefik/v3.4/user-guides/docker-compose/basic-example/)

   ```yaml
   # docker-compose.yml
   services:
     traefik:
       image: traefik:v3.4
       container_name: traefik
       restart: unless-stopped
       command:
         - "--providers.docker=true"
         - "--providers.docker.exposedbydefault=false"
         - "--entrypoints.web.address=:80"
         - "--entrypoints.websecure.address=:443"
         - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
         - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}"
         - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - "/var/run/docker.sock:/var/run/docker.sock:ro"
         - "./letsencrypt:/letsencrypt"

     streamlit:
       image: ghcr.io/youruser/radtracker:latest
       # or build: .
       container_name: radtracker
       restart: unless-stopped
       volumes:
         - "./data:/app/data"
       labels:
         - "traefik.enable=true"
         - "traefik.http.routers.radtracker.rule=Host(`${DOMAIN}`)"
         - "traefik.http.routers.radtracker.entrypoints=websecure"
         - "traefik.http.routers.radtracker.tls.certresolver=letsencrypt"
         - "traefik.http.routers.radtracker.middlewares=radtracker-auth"
         - "traefik.http.middlewares.radtracker-auth.basicauth.users=${BASICAUTH_USERS}"
   ```

   Environment variables (`.env`):
   ```
   DOMAIN=radtracker.example.com
   ACME_EMAIL=you@example.com
   BASICAUTH_USERS=admin:$$2y$$12$$...hashedpassword...
   ```

2. **TLS/SSL via Let's Encrypt — HTTP Challenge alternative** — The HTTP challenge doesn't require port 443 to be open to the internet initially, only port 80. Switch `tlschallenge` to `httpchallenge` in the Traefik command:
   ```yaml
   - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
   - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
   ```

3. **Nginx + Certbot alternative** — For those who prefer nginx, the `wmnnd/nginx-certbot` repo provides a battle-tested boilerplate. The `JonasAlfredsson/docker-nginx-certbot` image (updated 2025) wraps nginx + certbot in a single container, which is simpler than separate containers. [Source](https://github.com/wmnnd/nginx-certbot) | [Source](https://github.com/JonasAlfredsson/docker-nginx-certbot)

4. **Comparison**:

   | Aspect | Traefik | Nginx + Certbot |
   |--------|---------|-----------------|
   | Setup complexity | Low (labels, auto-discovery) | Medium (nginx config files) |
   | Let's Encrypt | Built-in, auto-renewal | certbot companion container |
   | Basic auth | Single label | nginx config directive |
   | Docker integration | Native (Docker provider) | Manual (port mapping) |
   | Learning curve | Medium (Traefik concepts) | Low (familiar nginx syntax) |
   | Resource usage | ~50MB RAM | ~20MB RAM |

   **Recommendation**: Traefik for this project—the Docker-native integration and auto-TLS eliminate entire categories of configuration.

### 5. SQLite Backup Strategies for Docker

1. **Safe backup from running container — `.backup` command** — The `sqlite3 .backup` dot-command uses SQLite's Online Backup API, which creates a consistent snapshot even while the database is being written to. This is the recommended approach for live databases. Unlike `cp` or `rsync`, it handles WAL mode correctly (doesn't produce corrupt snapshots from partial WAL files). [Source](https://www.sqlite.org/backup.html) | [Source](https://selfhosting.sh/foundations/backup-docker-volumes/)

   ```bash
   # One-liner: backup from running container to host
   docker exec radtracker sh -c "sqlite3 /app/data/radtracker.db '.backup /tmp/backup.db'" && \
   docker cp radtracker:/tmp/backup.db ./backups/radtracker-$(date +%Y%m%d).db
   ```

   **Verification**:
   ```bash
   sqlite3 ./backups/radtracker-20260501.db "PRAGMA integrity_check;"
   # Expected output: ok
   ```

2. **Litestream for continuous replication** — Litestream streams SQLite WAL changes to S3-compatible storage (or local path) in near-real-time (every second). It can run as a sidecar container or as a parent process wrapping the app. [Source](https://litestream.io/guides/docker/) | [Source](https://litestream.io/tips)

   - **Pros**: Point-in-time recovery, automatic, battle-tested (used by Fly.io), can restore from S3
   - **Cons for single-server radtracker**:
     - Adds operational complexity (sidecar container, S3 bucket config)
     - Requires `busy_timeout` pragma to avoid `SQLITE_BUSY` errors during Litestream checkpoints
     - Overkill for a single-user dashboard where nightly `.backup` is sufficient
   - **When Litestream is appropriate**: Multi-region deployments, zero RPO requirements, disaster recovery to cloud

   ```yaml
   # Litestream sidecar pattern (for reference):
   services:
     litestream:
       image: litestream/litestream:0.3.13
       command: replicate
       volumes:
         - ./data:/data
         - ./litestream.yml:/etc/litestream.yml
   ```

3. **Simple cron-based approach (recommended)** — A host-level cron job that runs `docker exec` + `sqlite3 .backup`. This is the simplest approach and fully adequate for a single-user dashboard. [Source](https://selfhosting.sh/foundations/backup-docker-volumes/)

   ```bash
   # /etc/cron.daily/radtracker-backup
   #!/bin/bash
   BACKUP_DIR="/opt/radtracker/backups"
   RETENTION_DAYS=30
   CONTAINER="radtracker"
   DB_PATH="/app/data/radtracker.db"

   mkdir -p "$BACKUP_DIR"
   TS=$(date +%Y%m%d_%H%M%S)

   docker exec "$CONTAINER" sqlite3 "$DB_PATH" ".backup /tmp/backup_$TS.db"
   docker cp "$CONTAINER:/tmp/backup_$TS.db" "$BACKUP_DIR/radtracker-$TS.db"
   docker exec "$CONTAINER" rm "/tmp/backup_$TS.db"

   # Verify backup
   if sqlite3 "$BACKUP_DIR/radtracker-$TS.db" "PRAGMA integrity_check;" | grep -q "ok"; then
       echo "Backup OK: $TS"
   else
       echo "BACKUP CORRUPT: $TS" >&2
       exit 1
   fi

   # Rotate
   find "$BACKUP_DIR" -name "*.db" -mtime +"$RETENTION_DAYS" -delete
   ```

4. **WAL mode warning** — If the SQLite database uses WAL mode (default in many modern setups), NEVER use `cp` or `rsync` to copy just the `.db` file—this will produce a corrupt snapshot because it ignores the `.db-wal` and `.db-shm` files. Always use `.backup` or `.dump`. [Source](https://scottspence.com/posts/sqlite-corruption-fs-copyfile-issue)

5. **Recommendation for radtracker**: Start with the cron-based `.backup` approach managed by the Ansible `backup.yml` playbook. Add Litestream only if point-in-time recovery becomes a requirement. The cron approach is dead simple and reliable.

---

## Sources

### Kept
- **Streamlit Docs: Deploy using Docker** (https://docs.streamlit.io/deploy/tutorials/docker) — Official Dockerfile pattern, HEALTHCHECK, EXPOSE, entrypoint
- **Streamlit Docs: config.toml** (https://docs.streamlit.io/develop/api-reference/configuration/config.toml) — All production config options (headless, port, CORS, etc.)
- **streamlit-authenticator v0.4.2 on PyPI** (https://pypi.org/project/streamlit-authenticator/) — Current version, install instructions, changelog
- **mkhorasani/Streamlit-Authenticator on GitHub** (https://github.com/mkhorasani/Streamlit-Authenticator) — Source, 2K+ stars, actively maintained (last push Feb 2026)
- **Traefik v3.4 Docker Compose Basic Example** (https://doc.traefik.io/traefik/v3.4/user-guides/docker-compose/basic-example/) — Official minimal docker-compose with Traefik
- **Traefik BasicAuth Middleware** (https://doc.traefik.io/traefik/middlewares/http/basicauth/) — Official docs for BasicAuth with htpasswd
- **SQLite Backup API** (https://www.sqlite.org/backup.html) — The `.backup` command's underlying C API, safe for live databases
- **Backing Up Docker Volumes (selfhosting.sh)** (https://selfhosting.sh/foundations/backup-docker-volumes/) — Practical patterns for docker exec + sqlite3 .backup
- **Ansible Docker Compose Guide (ansiblepilot)** (https://www.ansiblepilot.com/articles/ansible-docker-compose-guide) — Complete walkthrough for docker_compose_v2 module
- **Ansible Docker Prune Module** (https://docs.ansible.com/ansible/latest/collections/community/docker/docker_prune_module.html) — Official module docs
- **Ansible by Example: Docker** (https://www.ansiblebyexample.com/articles/ansible-docker-build-run-manage-containers) — Updated 2026 patterns for docker_compose_v2
- **GitHub: streamlit/streamlit#8223** (https://github.com/streamlit/streamlit/issues/8223) — Nginx htpasswd WebSocket issue and fix
- **GitHub: andfanilo/streamlit-nginx-basicauth** (https://github.com/andfanilo/streamlit-nginx-basicauth) — Working example of Streamlit + Nginx basic auth with WebSocket fix
- **KowashLab: Docker Multi-Stage Builds** (https://kowashlab.com/blog/docker-multi-stage-builds-python) — Multi-stage Python Dockerfile pattern with 80% size reduction
- **Litestream Docker Guide** (https://litestream.io/guides/docker/) — Sidecar and same-container patterns
- **scottspence: SQLite WAL Corruption** (https://scottspence.com/posts/sqlite-corruption-fs-copyfile-issue) — Why cp/rsync corrupts WAL mode SQLite DBs

### Dropped
- Medium/LinkedIn blog posts — SEO-heavy, often outdated, not primary sources
- Rockyourcode Streamlit Docker post — Covers basics but no production patterns
- GitHub: `Stars-streamlit-example` — Too minimal, no production config
- Coolify docs (Traefik) — Platform-specific, not a general reference
- DigitalOcean community post — Resolved by the official Streamlit + Nginx websocket pattern
- Older ansible `docker_compose` (v1) module docs — Deprecated in favor of docker_compose_v2

---

## Gaps

1. **Traefik BasicAuth + Streamlit WebSocket interaction** — Need to verify that Traefik's BasicAuth middleware doesn't cause the same WebSocket issue as nginx's auth_basic. Traefik handles WebSocket proxying automatically by default (unlike nginx where `proxy_http_version 1.1` and `Upgrade` headers must be set explicitly), so this is likely fine, but should be tested.

2. **Ansible Docker install on different Linux distros** — The research covers Ubuntu/Debian. If targeting Rocky Linux or Alpine, the Docker install tasks need adjustment. The `geerlingguy.docker` Ansible role handles multi-distro, but adds a dependency.

3. **Streamlit memory baseline for radtracker** — No benchmark data for the actual radtracker app. The 512MB limit suggested is a sensible default for a Streamlit + SQLite dashboard, but should be tuned with real usage data.

4. **streamlit-authenticator compatibility with latest Streamlit** — v0.4.3 was released March 2025 and is compatible with current Streamlit. However, if Streamlit ships breaking changes to session state or component APIs, the library may lag.

5. **Local network deployment without domain** — If the app is deployed on a local network without a public domain, Let's Encrypt won't work (requires DNS validation). For LAN-only deployments, either use self-signed certs + browser trust, or skip TLS entirely and use HTTP with Traefik + BasicAuth. This pattern should be documented as an alternative configuration.

---

## Pi-intercom handoff

*No safe intercom target configured. Completing normally.*
