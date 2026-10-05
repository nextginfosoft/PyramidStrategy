# Security policy

This project places real orders on a broker account and stores broker credentials, so security reports are taken seriously.

## Reporting a vulnerability

**Please do not open a public issue or pull request for a security problem.**

Use GitHub's private reporting instead: open the repository's **Security** tab and choose **Report a vulnerability**
(or go to `https://github.com/nextginfosoft/PyramidStrategy/security/advisories/new`).

Include, where you can:

- what you found and which component it affects (backend API, engine, frontend, deployment config);
- steps or a proof of concept to reproduce it;
- the impact you expect (account takeover, data exposure, unintended order placement, ...).

You will get an acknowledgement as soon as possible, and we will keep you updated until it is fixed.
Please give us a reasonable chance to fix the problem before disclosing it publicly.

## Supported versions

Only the latest code on `main` (production) is supported. Fixes land on `dev` first and are then promoted.

## Handling secrets

- Never commit `.env` files, API keys, broker tokens, TOTP secrets or database dumps. `backend/.env.example` lists the variable *names* only.
- Production, staging and every other deployment **must** set their own strong `SECRET_KEY`, `ENCRYPTION_KEY` and `POSTGRES_PASSWORD`. Any value that appears in this repository is public and must not be relied on.
- If a secret is ever committed or leaked, treat it as compromised: rotate it first, then clean up.
- Do not expose the database or Redis ports to the internet; keep them on the private Docker network or bind them to `127.0.0.1`.

## Scope

In scope: this repository's backend, frontend, CI/CD workflows and deployment configuration.
Out of scope: Zerodha / Kite Connect itself, third-party services, and findings that need physical access or a compromised user device.
