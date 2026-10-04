#!/usr/bin/env bash
# Deploy / manage the BANKNIFTY (paper) stack on the shared Hostinger VPS.
#
#   ./deploy.sh preflight   read-only checks; changes nothing
#   ./deploy.sh deploy      sync code, build, start the isolated stack, add the Caddy site, smoke-test
#                           (BUILD=local builds here and ships images instead of building on the VPS; CI does this)
#   ./deploy.sh status      container + HTTPS status
#   ./deploy.sh sites       HTTP status of every OTHER site behind the shared Caddy (read-only; used by CI)
#   ./deploy.sh rollback    remove the Caddy site and stop the stack (data volumes kept)
#   ./deploy.sh purge       rollback + delete this app's data volumes and files (asks first)
#
# Run from a clean checkout of the branch you want to ship (the committed tree is what gets deployed).
# Override with env: VPS_HOST, VPS_USER, VPS_KEY, DOMAIN, APP_DIR.
#
# What it touches on the VPS (nothing else):
#   /opt/banknifty-app/            this app's code and .env.local
#   docker project `banknifty-app` containers, volumes, private network
#   /opt/edge/Caddyfile            ONE marked site block (backed up first, validated, graceful reload)
set -euo pipefail

VPS_HOST="${VPS_HOST:-194.238.23.79}"
VPS_USER="${VPS_USER:-root}"
VPS_KEY="${VPS_KEY:-$HOME/.ssh/claude_vps}"
DOMAIN="${DOMAIN:-banknifty.nextginfosoft.com}"
APP_DIR="${APP_DIR:-/opt/banknifty-app}"
CADDYFILE="${CADDYFILE:-/opt/edge/Caddyfile}"
CADDY_CONTAINER="${CADDY_CONTAINER:-edge-caddy}"
PROJECT="banknifty-app"

ssh_vps() { ssh -o BatchMode=yes -o ConnectTimeout=15 -i "$VPS_KEY" "$VPS_USER@$VPS_HOST" "$@"; }
say() { printf '\n== %s\n' "$*"; }

preflight() {
  say "Pre-flight (read-only) on $VPS_HOST for $DOMAIN"
  ssh_vps bash -s -- "$DOMAIN" "$APP_DIR" "$CADDYFILE" "$CADDY_CONTAINER" <<'REMOTE'
DOMAIN="$1"; APP_DIR="$2"; CADDYFILE="$3"; CADDY="$4"
fail=0
ok()   { echo "[ OK ] $*"; }
bad()  { echo "[FAIL] $*"; fail=1; }
warn() { echo "[WARN] $*"; }

command -v docker >/dev/null && ok "docker $(docker --version | awk '{print $3}' | tr -d ,)" || bad "docker missing"
docker compose version >/dev/null 2>&1 && ok "docker compose present" || bad "docker compose missing"
docker network inspect edge >/dev/null 2>&1 && ok "shared network 'edge' exists" || bad "network 'edge' missing"
[ "$(docker inspect -f '{{.State.Running}}' "$CADDY" 2>/dev/null)" = "true" ] && ok "$CADDY is running" || bad "$CADDY not running"
[ -w "$CADDYFILE" ] && ok "$CADDYFILE writable" || bad "$CADDYFILE not writable"

clash=$(docker ps -a --format '{{.Names}}' | grep -E '^(banknifty-|banknifty_)' | grep -v '^banknifty-app-' || true)
[ -z "$clash" ] && ok "no container-name clashes" || bad "name clash: $clash"
if docker compose ls -a --format json 2>/dev/null | grep -q '"Name":"banknifty-app"'; then warn "compose project banknifty-app already exists (redeploy)"; else ok "compose project name free"; fi

if [ -e "$APP_DIR" ] && [ ! -e "$APP_DIR/.banknifty-app" ]; then bad "$APP_DIR exists and is not ours"; else ok "$APP_DIR free or ours"; fi

if grep -q "$DOMAIN" "$CADDYFILE" && ! grep -q '# >>> banknifty-app' "$CADDYFILE"; then bad "$DOMAIN already routed in Caddyfile by something else"; else ok "$DOMAIN not routed by another app"; fi

ips=$(hostname -I 2>/dev/null); dns=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | sort -u | head -3 | tr '\n' ' ')
case " $ips " in *" ${dns%% *} "*) ok "DNS $DOMAIN -> ${dns}(this server)";; *) bad "DNS $DOMAIN -> '${dns}' is not this server ($ips)";; esac

free_gb=$(df -BG --output=avail / | tail -1 | tr -dc 0-9); [ "${free_gb:-0}" -ge 8 ] && ok "disk free ${free_gb}G" || bad "disk free only ${free_gb}G"
mem_mb=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo); [ "${mem_mb:-0}" -ge 2500 ] && ok "memory available ${mem_mb}M" || bad "memory available only ${mem_mb}M"

echo "-- current edge sites:"; grep -E '^[a-z0-9.-]+ \{' "$CADDYFILE" | sed 's/ {//' | sed 's/^/     /'
[ $fail -eq 0 ] && echo "PRE-FLIGHT PASSED" || { echo "PRE-FLIGHT FAILED"; exit 1; }
REMOTE
}

deploy() {
  preflight
  say "Syncing committed tree of $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"
  [ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "Working tree has uncommitted changes; commit first."; exit 1; }
  git archive --format=tar HEAD backend frontend deploy | ssh_vps "cat > /tmp/banknifty-src.tar"
  ssh_vps bash -s -- "$APP_DIR" <<'REMOTE'
set -e
APP_DIR="$1"
mkdir -p "$APP_DIR"; touch "$APP_DIR/.banknifty-app"
rm -rf "$APP_DIR/src.new"; mkdir -p "$APP_DIR/src.new"
tar -x -C "$APP_DIR/src.new" -f /tmp/banknifty-src.tar; rm -f /tmp/banknifty-src.tar
rm -rf "$APP_DIR/src.old"; [ -d "$APP_DIR/src" ] && mv "$APP_DIR/src" "$APP_DIR/src.old"
mv "$APP_DIR/src.new" "$APP_DIR/src"
echo "synced to $APP_DIR/src"
REMOTE

  say "Secrets (.env.local on the server; generated once, never printed)"
  ssh_vps bash -s -- "$APP_DIR" <<'REMOTE'
set -e
f="$1/.env.local"
if [ -f "$f" ]; then echo ".env.local exists - keeping it"; exit 0; fi
umask 077
{
  echo "POSTGRES_PASSWORD=$(openssl rand -hex 24)"
  echo "SECRET_KEY=$(openssl rand -hex 32)"
  echo "ENCRYPTION_KEY=$(openssl rand -hex 16)"
  echo "SUPER_ADMIN_USERNAME=santosh"
  echo "SUPER_ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-20)"
} > "$f"
chmod 600 "$f"; echo "created $f (mode 600)"
REMOTE

  local up_flag="--build"
  if [ "${BUILD:-remote}" = "local" ]; then
    # Build on THIS machine (CI runner), ship the images: the shared VPS never compiles anything.
    say "Build images locally, ship to VPS (docker save | docker load)"
    ( cd deploy/banknifty && POSTGRES_PASSWORD=build SECRET_KEY=build ENCRYPTION_KEY=0123456789abcdef         SUPER_ADMIN_PASSWORD=build docker compose build )
    docker save banknifty-app-backend:latest banknifty-app-frontend:latest | gzip -1 | ssh_vps "gunzip | docker load"
    up_flag="--no-build"
  fi

  say "Start isolated stack (project $PROJECT)"
  ssh_vps bash -s -- "$APP_DIR" "$up_flag" <<'REMOTE'
set -e
cd "$1/src/deploy/banknifty"
docker compose --env-file "$1/.env.local" up -d "$2"
echo "waiting for backend health..."
for i in $(seq 1 40); do
  s=$(docker inspect -f '{{.State.Health.Status}}' banknifty-app-banknifty-backend-1 2>/dev/null || echo none)
  [ "$s" = healthy ] && { echo "backend healthy"; break; }
  [ "$i" = 40 ] && { echo "backend did not become healthy"; docker logs --tail 40 banknifty-app-banknifty-backend-1; exit 1; }
  sleep 5
done
echo "internal smoke test via frontend container:"
docker exec banknifty-app-banknifty-frontend-1 wget -qO- http://127.0.0.1/api/health
echo
REMOTE

  say "Route $DOMAIN in the shared Caddy (backup -> append -> validate -> graceful reload)"
  ssh_vps bash -s -- "$DOMAIN" "$CADDYFILE" "$CADDY_CONTAINER" <<'REMOTE'
set -e
DOMAIN="$1"; F="$2"; C="$3"
if grep -q '# >>> banknifty-app' "$F"; then echo "Caddy block already present - nothing to do"; exit 0; fi
BK="$F.bak-banknifty-$(date +%Y%m%d-%H%M%S)"; cp -p "$F" "$BK"; echo "backup: $BK"
# append in place (keeps the bind-mounted inode)
cat >> "$F" <<BLOCK

# >>> banknifty-app
$DOMAIN {
    reverse_proxy banknifty-frontend:80
}
# <<< banknifty-app
BLOCK
if docker exec "$C" caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
  docker exec "$C" caddy reload --config /etc/caddy/Caddyfile && echo "Caddy reloaded"
else
  echo "Caddy validation FAILED - restoring backup"; cat "$BK" > "$F"; exit 1
fi
REMOTE

  say "External smoke test (certificate issuance can take ~30s)"
  for i in $(seq 1 12); do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://$DOMAIN/api/health" || true)
    echo "attempt $i: HTTP $code"; [ "$code" = 200 ] && break; sleep 10
  done
  echo "Done. Admin password is in $APP_DIR/.env.local on the server (SUPER_ADMIN_PASSWORD)."
}

status() {
  ssh_vps "docker ps --filter name=banknifty-app --format 'table {{.Names}}\t{{.Status}}'; grep -c '# >>> banknifty-app' $CADDYFILE | sed 's/^/caddy block present: /'"
  curl -s -o /dev/null -w "https://$DOMAIN/api/health -> HTTP %{http_code}\n" --max-time 10 "https://$DOMAIN/api/health" || true
}

# HTTP status of every other site routed by the shared Caddy (excluding ours). Read-only.
# Retries a few times so a single network blip is not reported as an outage.
sites() {
  local hosts h code try
  hosts=$(ssh_vps "grep -E '^[A-Za-z0-9.-]+ \{' $CADDYFILE | sed 's/ {//'")
  for h in $hosts; do
    [ "$h" = "$DOMAIN" ] && continue
    for try in 1 2 3; do
      code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://$h/" || true)
      case "$code" in 2*|3*) break ;; esac
      sleep 3
    done
    echo "$h $code"
  done | sort
}

rollback() {
  say "Rollback: remove Caddy site, stop stack (volumes kept)"
  ssh_vps bash -s -- "$CADDYFILE" "$CADDY_CONTAINER" "$APP_DIR" <<'REMOTE'
set -e
F="$1"; C="$2"; APP_DIR="$3"
if grep -q '# >>> banknifty-app' "$F"; then
  BK="$F.bak-banknifty-rollback-$(date +%Y%m%d-%H%M%S)"; cp -p "$F" "$BK"
  sed '/# >>> banknifty-app/,/# <<< banknifty-app/d' "$BK" > /tmp/Caddyfile.rollback
  cat /tmp/Caddyfile.rollback > "$F"; rm -f /tmp/Caddyfile.rollback
  if docker exec "$C" caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
    docker exec "$C" caddy reload --config /etc/caddy/Caddyfile && echo "Caddy block removed, reloaded"
  else echo "validation failed - restoring"; cat "$BK" > "$F"; exit 1; fi
fi
[ -d "$APP_DIR/src/deploy/banknifty" ] && (cd "$APP_DIR/src/deploy/banknifty" && docker compose --env-file "$APP_DIR/.env.local" down) || true
REMOTE
}

purge() {
  read -r -p "Delete ALL banknifty-app data (database volume, files)? type 'purge': " a; [ "$a" = purge ] || exit 1
  rollback
  ssh_vps "docker volume rm banknifty-app_pgdata banknifty-app_applogs 2>/dev/null; rm -rf $APP_DIR; echo purged"
}

case "${1:-}" in
  sites)     sites ;;
  preflight) preflight ;;
  deploy)    deploy ;;
  status)    status ;;
  rollback)  rollback ;;
  purge)     purge ;;
  *) sed -n '2,13p' "$0"; exit 1 ;;
esac
