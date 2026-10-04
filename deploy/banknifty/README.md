# BANKNIFTY deployment (Hostinger VPS)

Live at https://banknifty.nextginfosoft.com — paper trading only.

## How deploys happen

**Every push to `banknifty` deploys automatically** (`.github/workflows/banknifty.yml`):

1. `test` — flake8, backend tests, frontend type-check + build, deploy-package checks.
2. `deploy` (only if tests pass, only on push / manual run, never on PRs):
   - snapshot the HTTP status of every *other* site behind the shared Caddy
   - pre-flight on the VPS (name/port/DNS/disk/memory checks; aborts without changes if any fail)
   - **build the images on the GitHub runner** and ship them (`docker save | docker load`), so the
     VPS never compiles anything — safe at any hour, including market hours
   - start the isolated `banknifty-app` stack, add/keep its single Caddy block, smoke-test HTTPS
   - re-check the other sites; if any changed, our Caddy block and stack are removed again

Pushes that only touch docs/other paths don't trigger it. Manual run: Actions → *CI/CD — BANKNIFTY* → *Run workflow*.

What a deploy can touch on the VPS: `/opt/banknifty-app/`, the `banknifty-app` Docker project
(containers, network, volumes) and one marked block in `/opt/edge/Caddyfile` (backed up first,
validated, graceful reload). Nothing else.

## One-time setup (needed before the first automatic deploy)

The pipeline uses its **own** SSH key (not your personal one) so it can be revoked on its own.

```bash
# 1. dedicated key pair (no passphrase; used only by CI)
ssh-keygen -t ed25519 -N "" -C "banknifty-ci-deploy" -f ~/.ssh/banknifty_ci_deploy

# 2. authorise it on the VPS (appends one line; run with a key that already has access)
ssh -i ~/.ssh/claude_vps root@194.238.23.79 \
  "cat >> ~/.ssh/authorized_keys" < ~/.ssh/banknifty_ci_deploy.pub

# 3. record the VPS host key so CI can verify it is talking to the right server
ssh-keyscan -t ed25519 194.238.23.79 > /tmp/bn_known_hosts

# 4. repository secrets + protected environment
gh secret set BANKNIFTY_VPS_HOST        --repo nextginfosoft/PyramidStrategy --body "194.238.23.79"
gh secret set BANKNIFTY_VPS_USER        --repo nextginfosoft/PyramidStrategy --body "root"
gh secret set BANKNIFTY_VPS_SSH_KEY     --repo nextginfosoft/PyramidStrategy < ~/.ssh/banknifty_ci_deploy
gh secret set BANKNIFTY_VPS_KNOWN_HOSTS --repo nextginfosoft/PyramidStrategy < /tmp/bn_known_hosts
gh api -X PUT repos/nextginfosoft/PyramidStrategy/environments/banknifty-production
```

Optional hardening: in GitHub → Settings → Environments → `banknifty-production`, restrict
deployment branches to `banknifty` (and add required reviewers if you want a manual approval gate —
that turns every push into "tests, then wait for approval").

## Day-to-day

| Need | Command |
|---|---|
| Status | `bash deploy/banknifty/deploy.sh status` |
| Other sites' status | `bash deploy/banknifty/deploy.sh sites` |
| Manual deploy from your machine (builds on the VPS) | `bash deploy/banknifty/deploy.sh deploy` |
| Take the app down (data kept) | `bash deploy/banknifty/deploy.sh rollback` |
| Delete everything incl. data | `bash deploy/banknifty/deploy.sh purge` |

Local overrides: `VPS_HOST`, `VPS_USER`, `VPS_KEY`, `DOMAIN`. Add `BUILD=local` to build on your
machine (what CI does).

Secrets for the app itself (database password, JWT key, admin password) are generated once on
the server into `/opt/banknifty-app/.env.local` (mode 600) and are never in Git or CI.
