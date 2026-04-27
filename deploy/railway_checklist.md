# Railway Deployment Checklist — Shamsi Smart

## Pre-Deployment Environment Variables

Set these in Railway → Project → Variables:

| Variable | Value | Required |
|---|---|---|
| `SECRET_KEY` | Long random string | ✅ |
| `DEBUG` | `False` | ✅ |
| `DJANGO_SETTINGS_MODULE` | `shamsi_smart.settings.production` | ✅ |
| `ALLOWED_HOSTS` | `your-app.railway.app,yourdomain.com` | ✅ |
| `DATABASE_URL` | Auto-provided by Railway PostgreSQL plugin | ✅ |
| `CORS_ALLOWED_ORIGINS` | `https://your-frontend.vercel.app` | ✅ |

## Deployment Checklist

### Infrastructure
- [ ] SECRET_KEY set in Railway variables
- [ ] DEBUG=False confirmed
- [ ] ALLOWED_HOSTS includes Railway URL (e.g. `shamsi-smart.railway.app`)
- [ ] DATABASE_URL auto-provided by Railway PostgreSQL plugin
- [ ] CORS_ALLOWED_ORIGINS set to frontend URL

### Database
- [ ] All migrations applied:
  ```
  railway run python manage.py migrate
  ```
- [ ] Superuser created:
  ```
  railway run python manage.py createsuperuser
  ```

### Static Files
- [ ] Static files collected (runs automatically via nixpacks.toml build phase):
  ```
  railway run python manage.py collectstatic --noinput
  ```

### Data Loading
- [ ] Electricity tariffs loaded:
  ```
  railway run python manage.py loaddata egyptian_electricity_tariffs
  ```
- [ ] Solar equipment loaded:
  ```
  railway run python manage.py loaddata solar_equipment_2026
  ```

### AI Models
- [ ] AI models trained:
  ```
  railway run python manage.py train_ai_models
  ```

### Verification
- [ ] Health check passes:
  ```
  curl https://your-app.railway.app/api/v1/health/
  ```
  Expected: `{"status": "healthy"}`

- [ ] Tariff API works:
  ```
  curl https://your-app.railway.app/api/v1/tariffs/
  ```

- [ ] Equipment API works:
  ```
  curl https://your-app.railway.app/api/v1/equipment/panels/
  ```

- [ ] Django admin accessible:
  ```
  https://your-app.railway.app/admin/
  ```

## Quick Deploy Commands

```bash
# Generate SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Run full post-deploy setup
railway run python manage.py migrate
railway run python manage.py collectstatic --noinput
railway run python manage.py loaddata egyptian_electricity_tariffs solar_equipment_2026
railway run python manage.py train_ai_models
railway run python manage.py createsuperuser
```

## Troubleshooting

### DisallowedHost error
Add your Railway domain to `ALLOWED_HOSTS` env var.

### Static files 404
Ensure `collectstatic` ran and `STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'`.

### Database connection error
Check `DATABASE_URL` is set. Railway auto-injects it when PostgreSQL plugin is added.

### AI model training fails
Ensure climate data is loaded first (`manage.py loaddata` or via the ingestion pipeline).
Models fall back to physics estimates / latitude rules if no data exists.
