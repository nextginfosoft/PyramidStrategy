## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Type

- [ ] Feature
- [ ] Bug fix
- [ ] Refactor / chore
- [ ] Docs
- [ ] CI / deployment

## Checks

- [ ] `pytest tests/` passes (backend)
- [ ] `npm run build` passes (frontend: typecheck + build)
- [ ] New behaviour has tests

## Risk

- [ ] Touches **live-trading logic** (engines, order placement, exits, config loading). If checked, it must run through a live market session on `dev` before it is ported to `main` / `destiny`.
- [ ] Changes the **database schema** (new columns must be nullable with no default, added by the self-healing migration in `database.py`).
- [ ] Adds or changes an **environment variable** or deployment step (document it).
- [ ] Changes **strategy_config** fields: every writer and loader must carry the new field (see CONTRIBUTING.md).

## Rollback

<!-- How do we undo this if it misbehaves? e.g. "revert the PR", "set the new setting back to blank". -->
