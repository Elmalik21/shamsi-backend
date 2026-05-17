# Shamsi Smart — Scaling Plan
## Infrastructure Growth: 10 → 10,000 Users

*This document defines scaling thresholds, architecture changes, and cost projections for each growth stage.*

---

## Current State (Beta, <50 Users)

### Architecture
```
Internet → Railway (single container)
              ├── Django (Gunicorn, 2 workers)
              ├── PostgreSQL (Railway managed)
              └── Static files (Railway CDN)
```

### Specs
- **Compute:** Railway Starter ($5/month) — 512MB RAM, 0.5 vCPU
- **Database:** Railway PostgreSQL ($5/month) — 1GB storage
- **Total cost:** ~$27/month (including domain, Sentry free tier)
- **Capacity:** ~200 optimisation requests/day before degradation

### Known Bottlenecks
- NSGA-II optimisation: CPU-bound, blocks Django thread for 5–15 seconds
- Large PDF exports: memory spike to ~300MB per request
- No queue — concurrent optimisations queue in Gunicorn

---

## Stage 1: Soft Launch (50–250 Users, Month 3–6)

**Trigger:** >50 daily active users, or P95 response time >5s for optimisation

### Changes
1. **Add Celery + Redis** for async task queue
   - Optimisation runs in background; user polls for result
   - Removes 15-second blocking from web workers
   - Cost: +$10/month (Redis on Railway)

2. **Scale Railway container**
   - Upgrade to Pro plan: 1GB RAM, 1 vCPU → $20/month
   - Increase Gunicorn workers: 2 → 4

3. **Add CDN for static assets**
   - Cloudflare free tier — cache JS/CSS/images
   - Reduces Railway egress cost

### Architecture
```
Internet → Cloudflare CDN → Railway Web (4 Gunicorn workers)
                                  ├── PostgreSQL
                                  ├── Redis
                                  └── Celery Worker (1 container)
```

### Estimated Cost: ~$65/month
### Capacity: ~1,000 optimisation requests/day

---

## Stage 2: Public Launch (250–1,000 Users, Month 6–12)

**Trigger:** >500 DAU, or optimisation queue depth >50 pending tasks

### Changes
1. **Horizontal scaling — web workers**
   - Add second Railway web container behind load balancer
   - Session storage moves to Redis (stateless web)

2. **Celery worker pool**
   - Scale from 1 to 3 Celery workers (3 concurrent optimisations)
   - Separate Railway service for workers — scales independently

3. **Database optimisation**
   - Add read replica for analytics queries
   - Index audit: add composite indexes on `user_id + created_at`
   - Connection pooling via PgBouncer (Railway add-on)

4. **File storage — S3**
   - Move user uploads (roof photos) to AWS S3
   - Move PDF/PVsyst exports to S3 with 7-day expiry links
   - Reduces Railway disk usage

5. **YOLOv8 service isolation**
   - Move roof CV analysis to dedicated container (GPU optional)
   - Railway does not offer GPU — consider Render or Modal for CV worker
   - Alternative: optimise YOLOv8 inference to CPU (acceptable at this scale)

### Architecture
```
Internet → Cloudflare → Railway Load Balancer
                              ├── Web Container A (4 workers)
                              ├── Web Container B (4 workers)
                              ├── Celery Worker × 3
                              ├── PostgreSQL + Read Replica
                              ├── Redis
                              └── S3 (uploads + exports)
```

### Estimated Cost: ~$250/month
### Capacity: ~5,000 optimisation requests/day
### Revenue at this stage: $3,500–$10,000 MRR (infrastructure is <5% of revenue)

---

## Stage 3: Scale (1,000–5,000 Users, Month 12–24)

**Trigger:** >2,000 DAU, or infrastructure cost >10% of MRR

### Changes
1. **Migrate from Railway to AWS/GCP**
   - Railway is excellent for early stage but lacks fine-grained control at scale
   - Target: AWS ECS (Fargate) or GCP Cloud Run for web + Celery
   - Managed PostgreSQL → AWS RDS (Multi-AZ for 99.99% uptime)
   - This migration requires 1 week of engineering time

2. **API gateway**
   - Add AWS API Gateway or Kong in front of Django
   - Rate limiting per API key (Enterprise tier: 1,000 req/day; Pro: 100/day; Free: 10/day)
   - Authentication moves to JWT with refresh tokens

3. **Dedicated CV inference service**
   - YOLOv8 deployed on AWS Lambda (CPU) or Replicate.com (GPU on-demand)
   - Cost per CV analysis: ~$0.01–0.05 (acceptable at $5 per-use API price)

4. **ESED dataset versioning**
   - Dataset grows with every user project (~5 new climate data points/day)
   - Automated weekly re-training of CNN-LSTM model on expanded dataset
   - A/B test new model vs current before deploying

5. **Multi-region (MENA)**
   - Deploy read-only API replica in Frankfurt (EU) for Saudi/UAE users
   - Saudi Arabia users: 60ms latency from Frankfurt vs 200ms from EU railway
   - Full MENA region deployment in Year 2 with Saudi data

### Architecture
```
Internet → Cloudflare (global CDN)
              → AWS API Gateway
                    → ECS Web Cluster (auto-scaling, 2–8 containers)
                    → ECS Celery Cluster (auto-scaling, 2–6 workers)
                    → RDS PostgreSQL (Multi-AZ)
                    → ElastiCache Redis
                    → S3 (uploads, exports, model artifacts)
                    → Lambda (YOLOv8 inference)
```

### Estimated Cost: ~$1,200/month
### Capacity: ~50,000 optimisation requests/day
### Revenue at this stage: $24,000+ MRR (infrastructure is ~5% of revenue)

---

## Stage 4: MENA Expansion (5,000–10,000 Users, Year 2–3)

**Trigger:** Saudi/UAE launch, or >5,000 total registered users

### Changes
1. **Multi-tenant architecture**
   - Separate MENA country datasets (Saudi, UAE, Jordan) per tenant
   - Country-specific tariff tables, dust zones, equipment pricing
   - White-label Enterprise: custom subdomain per company

2. **Dedicated ML pipeline**
   - AWS SageMaker for CNN-LSTM retraining
   - Automated model validation (MAPE check before promoting to production)
   - Model versioning with rollback capability

3. **Real-time monitoring**
   - Datadog (or Grafana Cloud) for infrastructure metrics
   - Custom Shamsi dashboard: designs/day, MAPE drift, export success rate
   - PagerDuty alerts for P0 incidents (validation MAPE > 10%)

4. **Enterprise features**
   - SSO (SAML/OAuth2) for Enterprise tier
   - Role-based access control (project manager, engineer, viewer)
   - Audit log for all designs and exports (regulatory compliance for large EPCs)

### Estimated Cost: ~$3,500/month
### Capacity: 200,000+ optimisation requests/day
### Revenue at this stage: $50,000+ MRR (infrastructure is ~7% of revenue)

---

## Cost Summary by Stage

| Stage | Users | Infra Cost/Month | MRR | Infra as % MRR |
|-------|-------|-----------------|-----|----------------|
| Beta | <50 | $27 | $0–500 | — |
| Soft Launch | 50–250 | $65 | $500–3,500 | 2–13% |
| Public Launch | 250–1,000 | $250 | $3,500–10,000 | 2–7% |
| Scale | 1,000–5,000 | $1,200 | $10,000–50,000 | 2–12% |
| MENA | 5,000–10,000 | $3,500 | $50,000–120,000 | 3–7% |

**Key insight:** Infrastructure costs scale sub-linearly relative to revenue — gross margin improves with scale.

---

## Reliability Targets

| Stage | Uptime SLA | RTO | RPO |
|-------|-----------|-----|-----|
| Beta | Best-effort | 4 hours | 24 hours |
| Soft Launch | 99.5% | 2 hours | 4 hours |
| Public Launch | 99.9% | 30 min | 1 hour |
| Scale+ | 99.99% | 5 min | 5 min |

**RTO** = Recovery Time Objective (time to restore service after failure)
**RPO** = Recovery Point Objective (maximum data loss acceptable)

---

## Key Engineering Decisions by Stage

| Decision | Beta | Public Launch | Scale |
|----------|------|---------------|-------|
| Task queue | Synchronous | Celery+Redis | Celery+Redis |
| File storage | Local disk | S3 | S3 (multi-region) |
| CV inference | In-process | In-process | Lambda/GPU |
| ML retraining | Manual | Manual | Automated (SageMaker) |
| Monitoring | Sentry free | Sentry + Railway | Datadog + PagerDuty |
| DB backups | Railway daily | Railway daily | RDS PITR + S3 |
| Auth | Django sessions | Django sessions | JWT + SSO |
| CDN | None | Cloudflare free | Cloudflare Pro |

---

*Owner: Engineering Lead | Review: Quarterly or at each stage trigger | Last updated: May 2026*
