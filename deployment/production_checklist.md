# Shamsi Smart — Production Deployment Checklist

*Run this checklist before every production deployment. Check each item.*

---

## Pre-Deployment (Local / Staging)

### Code Quality
- [ ] `python3 -B -m pytest tests/ -v` — all 62 tests passing
- [ ] `flake8 . --max-line-length=100 --exclude=venv,migrations` — zero errors
- [ ] `python3 -B scripts/validate_with_case_studies.py` — mean MAPE < 5%, verdict PASS
- [ ] No uncommitted changes: `git status` is clean
- [ ] Version tag created: `git tag v{MAJOR}.{MINOR}.{PATCH}`

### Security
- [ ] No secrets in code — run `grep -r "SECRET\|PASSWORD\|API_KEY" . --include="*.py" --exclude-dir=venv`
- [ ] `.env` is in `.gitignore` — verify: `git check-ignore -v .env`
- [ ] Django `DEBUG=False` in production settings
- [ ] `ALLOWED_HOSTS` contains only `shamsi.ai`, `api.shamsi.ai`
- [ ] `SECRET_KEY` is a 50+ character random string (not the Django default)
- [ ] Database password is 20+ characters, stored in Railway environment variable only

### Dependencies
- [ ] `pip freeze > requirements.txt` committed with new versions
- [ ] No packages with known CVEs: `pip audit` (install with `pip install pip-audit`)
- [ ] Python version matches production: `python3 --version` → 3.10.x

---

## Railway Deployment

### Environment Variables (verify in Railway dashboard)
- [ ] `DATABASE_URL` — PostgreSQL connection string
- [ ] `DJANGO_SECRET_KEY` — 50+ char random string
- [ ] `DJANGO_ALLOWED_HOSTS` — `shamsi.ai,api.shamsi.ai,www.shamsi.ai`
- [ ] `DJANGO_DEBUG` — `False`
- [ ] `REDIS_URL` — Redis connection string (for Celery, if enabled)
- [ ] `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — S3 for user uploads (if enabled)
- [ ] `ZENODO_TOKEN` — for dataset upload script (optional, deployment-time only)

### Deployment Steps
1. [ ] Push to `main` branch: `git push origin main`
2. [ ] Monitor Railway build log — no errors in pip install
3. [ ] Monitor Railway deploy log — `collectstatic` completes, migrations run
4. [ ] Check Railway health: service shows "Active" in dashboard

---

## Post-Deployment Verification

### Smoke Tests (run within 5 minutes of deploy)
- [ ] `curl -s https://shamsi.ai/api/v1/health/` → `{"status": "ok", "version": "X.Y.Z"}`
- [ ] `curl -s https://shamsi.ai/api/v1/cities/` → returns list of 5 Egyptian cities
- [ ] POST `/api/v1/optimise/` with Cairo test payload → returns 5 Pareto solutions
- [ ] POST `/api/v1/export/pdf/` with test design → returns valid PDF (200 OK, Content-Type: application/pdf)
- [ ] POST `/api/v1/export/pvsyst/` with test design → returns valid ZIP

### User-Facing
- [ ] `https://shamsi.ai` loads — landing page renders
- [ ] `https://shamsi.ai/demo` loads — demo interface renders
- [ ] Login flow works — test with `testuser@shamsi.ai` account
- [ ] Free tier optimisation works end-to-end (upload → optimise → PDF export)

### Monitoring
- [ ] Sentry error rate is zero in the 15 minutes post-deploy
- [ ] Railway CPU/memory within normal bounds (CPU < 50%, memory < 80%)
- [ ] Response times: P95 < 2s for optimisation, P95 < 500ms for API

---

## Rollback Procedure

If any smoke test fails or error rate spikes:

```bash
# 1. Identify last good deploy in Railway dashboard
# 2. Click "Redeploy" on previous successful deployment
# 3. Verify health endpoint returns previous version number
# 4. Notify team in Slack #engineering: "Rolled back to vX.Y.Z — investigating"

# Local investigation:
git log --oneline -10          # find last good commit
git diff HEAD~1 HEAD           # review what changed
git revert HEAD                # revert if single bad commit
git push origin main           # Railway auto-deploys the revert
```

**SLA commitment:** Rollback within 15 minutes of detecting production failure.

---

## Database

### Before deployment (if migrations exist)
- [ ] Review migration SQL: `python manage.py sqlmigrate {app} {number}`
- [ ] Test migration on staging DB first
- [ ] Backup production DB: Railway provides point-in-time recovery (verify it's enabled)
- [ ] For destructive migrations (DROP COLUMN, etc.): deploy in two stages
  - Stage 1: Code that works with both old and new schema
  - Stage 2: Migration that drops old column

### After deployment
- [ ] `python manage.py showmigrations` — all migrations marked [X]
- [ ] Spot-check: run one query against migrated tables via Railway console

---

## SSL / Domain

- [ ] `https://shamsi.ai` returns HTTP 200 (not redirect loop)
- [ ] SSL certificate valid: `openssl s_client -connect shamsi.ai:443 2>/dev/null | grep "Verify return code"` → `Verify return code: 0 (ok)`
- [ ] Certificate expiry > 30 days: `echo | openssl s_client -connect shamsi.ai:443 2>/dev/null | openssl x509 -noout -dates`
- [ ] `http://shamsi.ai` redirects to `https://shamsi.ai` (301)

---

## Sign-off

| Role | Name | Sign-off | Time |
|------|------|----------|------|
| Deploying engineer | | | |
| Second reviewer (if available) | | | |

**Deployment log entry format:**
```
[DATE] v[VERSION] deployed by [NAME]
Changes: [brief description]
Tests: 62/62 | MAPE: X.XX%
Issues: [none / description]
Rollback: [not needed / rolled back at HH:MM]
```

---

*Last updated: May 2026 | Owner: Engineering Lead*
