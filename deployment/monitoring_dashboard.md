# Shamsi Smart — Monitoring Dashboard Specification
## What to Watch, When to Alert, How to Respond

*This document specifies all metrics, alert thresholds, and runbooks for production monitoring.*

---

## Dashboard Sections

### 1. System Health (top-level — always visible)

| Metric | Green | Yellow | Red | Source |
|--------|-------|--------|-----|--------|
| API uptime | 100% | <99.9% | <99.5% | Railway health check |
| `/api/v1/health/` response | 200 OK | — | Non-200 | Uptime Robot (60s interval) |
| P95 API response time | <1s | 1–3s | >3s | Railway metrics |
| P95 optimisation time | <15s | 15–30s | >30s | Celery task timing |
| Celery queue depth | <10 | 10–50 | >50 | Redis `LLEN` |
| Error rate (5xx) | <0.1% | 0.1–1% | >1% | Sentry |

**Smoke test URL:** `GET https://shamsi.ai/api/v1/health/`
Expected response:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "connected",
  "celery": "connected",
  "validation_mape": 3.13
}
```

---

### 2. AI Model Health (daily check)

These metrics detect model drift — the most critical Shamsi-specific risk.

| Metric | Target | Alert Threshold | How to Check |
|--------|--------|-----------------|--------------|
| CNN-LSTM MAPE (live) | <5% | >7% | Run `validate_with_case_studies.py` |
| Cities within 10% MAPE | 5/5 | <4/5 | Validation script output |
| YOLOv8 detection rate | >90% | <80% | Log: `roof_cv_success_rate` |
| NSGA-II convergence rate | >99% | <95% | Log: `optimisation_convergence` |
| Export success rate | >99.5% | <98% | Log: `export_success_rate` |

**Model drift runbook:**
```
IF validation_mape > 7%:
  1. Check if ESED dataset was recently updated (new records may have errors)
  2. Run: python3 -B scripts/validate_with_case_studies.py --verbose
  3. Identify which city(ies) are failing
  4. Check recent user projects for that city — anomalous inputs?
  5. If systematic: re-validate against PVWatts for that city
  6. If data error: roll back dataset update
  7. Alert: engineering@shamsi.ai + founder
```

---

### 3. Business Metrics (daily)

| Metric | Formula | Target (Month 6) |
|--------|---------|------------------|
| New signups | COUNT(users WHERE date=today) | 5/day |
| Free-to-Pro conversions | COUNT(subscriptions WHERE plan='pro' AND created=today) | 1–2/week |
| Designs completed | COUNT(optimisations WHERE status='complete' AND date=today) | 20/day |
| PDF exports | COUNT(exports WHERE type='pdf' AND date=today) | 15/day |
| PVsyst exports | COUNT(exports WHERE type='pvsyst' AND date=today) | 5/day |
| DAU / MAU ratio | DAU / MAU | >0.3 (healthy engagement) |
| Churn this month | Cancelled Pro / Total Pro × 100 | <3% |
| MRR | SUM(active subscriptions × price) | See projections |

**Weekly business report (auto-generated — see `scripts/weekly_report.py`):**
- New users this week
- MRR delta (vs last week)
- Top 3 cities by design volume
- Export type breakdown
- Any churned Pro/Enterprise accounts

---

### 4. User Experience Metrics (weekly)

| Metric | Target | Source |
|--------|--------|--------|
| Time to first optimisation (new user) | <10 minutes | Mixpanel / backend logs |
| Optimisation completion rate | >95% | `optimisation_status` log |
| PDF export success rate | >99% | `export_status` log |
| User-reported errors (support tickets) | <5/week | Email/WhatsApp support |
| NPS (monthly survey) | >8.0 | Survey tool |

---

### 5. Infrastructure Metrics (real-time)

#### Railway / Server
| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| CPU usage | <50% | 50–80% | >80% |
| Memory usage | <70% | 70–85% | >85% |
| Disk usage | <60% | 60–80% | >80% |
| DB connections | <50 | 50–80 | >80 (of max_connections) |
| Redis memory | <50% | 50–80% | >80% |

#### Database
| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| Query time (P95) | <100ms | 100–500ms | >500ms |
| Slow queries (>1s) | 0 | 1–5/hour | >5/hour |
| Replication lag | N/A (single) | — | — |
| Table bloat | <20% | 20–40% | >40% |

**Check slow queries:**
```sql
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
WHERE mean_exec_time > 1000  -- 1 second
ORDER BY mean_exec_time DESC
LIMIT 10;
```

---

## Alert Configuration

### P0 — Immediate Response (SLA: 15 minutes)

Conditions that trigger P0:
- API returns non-200 for >2 consecutive minutes
- Validation MAPE >10% (safety-critical — bank financing uses these numbers)
- Database unreachable
- Error rate >5% for >5 minutes

**Alert channels:** Phone call + SMS (founder) + Email
**Runbook:** Rollback procedure in `production_checklist.md`

---

### P1 — Urgent Response (SLA: 2 hours)

Conditions:
- P95 optimisation time >30 seconds
- Celery queue depth >50
- Memory usage >85% for >10 minutes
- PVsyst export failure rate >5%

**Alert channels:** Email + WhatsApp message
**Runbook:**
```
Queue depth >50:
  → Scale Celery workers: Railway dashboard → workers service → scale up
  → If persistent: check for hung tasks in Celery Flower dashboard

Memory >85%:
  → Check for memory leak: Railway logs → grep "MemoryError"
  → Scale container: Railway dashboard → web service → increase RAM
  → Immediate: restart web container (brief downtime ~30s)
```

---

### P2 — Business Hours Response (SLA: 24 hours)

Conditions:
- DAU drops >30% vs 7-day average
- Churn spike: >2 Pro cancellations in 24 hours
- YOLOv8 detection rate <80% for >1 hour
- New user signup rate drops >50% vs weekly average

**Alert channels:** Email
**Runbook:** Investigate logs, check for UX issues or marketing channel problems

---

## Logging Standards

All Shamsi application logs follow this structured format:

```json
{
  "timestamp": "2026-05-16T14:32:00Z",
  "level": "INFO",
  "event": "optimisation_complete",
  "user_id": "usr_xxxxx",
  "session_id": "ses_xxxxx",
  "city": "cairo",
  "system_size_kwp": 11.6,
  "duration_ms": 8432,
  "pareto_solutions": 5,
  "mape_estimate": 3.1,
  "export_types_requested": ["pdf", "pvsyst"],
  "tier": "pro"
}
```

**Key log events to track:**
- `user_signup` — new registration
- `optimisation_start` / `optimisation_complete` / `optimisation_failed`
- `export_start` / `export_complete` / `export_failed`
- `subscription_created` / `subscription_cancelled`
- `validation_run` — daily MAPE validation
- `model_drift_detected` — if MAPE exceeds threshold

---

## Dashboards to Build (Priority Order)

### Immediate (pre-launch)
1. **Uptime monitor** — Uptime Robot free tier (https://uptimerobot.com)
   - Check `/api/v1/health/` every 60 seconds
   - Alert via email if down >2 minutes
   - Public status page: `status.shamsi.ai`

2. **Error tracking** — Sentry free tier
   - Django + Celery integration: `pip install sentry-sdk`
   - Alert threshold: >5 new errors/hour
   - Group by error type + user impact

3. **Business metrics** — Google Sheets (automated)
   - Daily cron job (`scripts/daily_metrics.py`) writes to Google Sheets
   - Tracks: signups, designs, exports, MRR, churn

### Month 3 (public launch)
4. **Infrastructure dashboard** — Railway metrics (built-in)
   - CPU, memory, request count visible in Railway dashboard
   - Set Railway usage alerts at 80% of plan limits

5. **Celery monitoring** — Flower (open source)
   - `pip install flower` → `celery flower --port=5555`
   - Protected behind Railway private network
   - Monitor: active tasks, queue depth, worker health

### Month 6 (scale)
6. **Full observability stack** — Grafana Cloud free tier
   - Prometheus metrics from Django (`django-prometheus`)
   - Grafana dashboards: business + infrastructure in one view
   - 14-day data retention on free tier

---

## Validation Automation

Run `validate_with_case_studies.py` automatically:

### Daily cron (Railway Cron Job service)
```
# Schedule: 06:00 UTC daily
python3 -B scripts/validate_with_case_studies.py --output json > /tmp/validation_result.json

# Parse result and alert if needed:
python3 scripts/check_validation_alert.py /tmp/validation_result.json
```

`check_validation_alert.py` logic:
```python
import json, sys
result = json.load(open(sys.argv[1]))
mape = result['stats']['mean_mape']
passed = result['stats']['passed']

if not passed or mape > 7.0:
    # Send alert email via SendGrid
    send_alert(f"VALIDATION ALERT: MAPE={mape:.2f}% — {result['stats']['verdict']}")
    sys.exit(1)

print(f"Validation OK: MAPE={mape:.2f}%")
```

---

## Monthly Review Checklist

On the first Monday of each month, review:

- [ ] Mean MAPE for the month (from daily validation logs) — still <5%?
- [ ] MRR vs projection (from business_model.md month targets)
- [ ] Churn rate — within acceptable bounds?
- [ ] Support tickets — any recurring issues?
- [ ] Infrastructure cost vs revenue — still <10% of MRR?
- [ ] Any Celery tasks failed silently? (`celery inspect failed`)
- [ ] Certificate expiry date check
- [ ] Database growth rate — on track for storage plan?
- [ ] Update `deployment/production_checklist.md` if procedures changed

---

*Owner: Founder / Engineering Lead | Review: Monthly | Last updated: May 2026*
