# Database Setup — Railway PostgreSQL

Complete guide for connecting Shamsi Smart training scripts to the Railway PostgreSQL database (341,991 climate records across 119 Egyptian locations).

---

## Quick Start

### 1. Create the `.env` file

In the project root (`shamsi-backend-main/`), create a file named `.env`:

```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_HOST.proxy.rlwy.net:PORT/railway
```

Get your credentials from: **Railway Dashboard → PostgreSQL service → Connect tab → Public URL**.

A fully populated `.env` looks like this:

```
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://postgres:oKmkfaeaRLjmPmUCstYfDXgbPejUZEeE@switchback.proxy.rlwy.net:36668/railway
CORS_ALLOWED_ORIGINS=http://localhost:5173
DJANGO_SETTINGS_MODULE=shamsi_smart.settings
```

The `.env` file is listed in `.gitignore` and will never be committed.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

This installs `python-dotenv`, which automatically loads `.env` before any training scripts run.

### 3. Test the connection

```bash
python scripts/test_db_connection.py
```

Expected output:

```
✅  Connection successful!

    📊 Database Summary:
      - Climate records     : 341,991
      - Locations           : 119
      - Solar panels        : 8
      - Inverters           : 7

    ✅  Database has sufficient data for training
       Ready to run: python scripts/train_all_models.py
```

### 4. Train all models

```bash
# CPU only:
python scripts/train_all_models.py

# With GPU (CUDA):
python scripts/train_all_models.py --gpu

# Quick test (RF + K-Means only, reduced epochs):
python scripts/train_all_models.py --only rf kmeans --quick
```

---

## Internal vs. Public Hostname

Railway provides **two** different hostnames for the same PostgreSQL instance:

| Hostname | Works from |
|----------|------------|
| `postgres.railway.internal` | Only inside Railway's private network (deployed Railway services) |
| `switchback.proxy.rlwy.net:36668` | Anywhere — your laptop, Colab, Kaggle |

**Always use the public proxy URL on your local machine.**

If you see this warning when running a script:
```
⚠️  Railway Internal Hostname Detected — External Warning
```
open your `.env` and replace the internal hostname with the public one.

---

## Platform-Specific Setup

### Local machine (Windows / Mac / Linux)

Use the `.env` file as shown above. `python-dotenv` loads it automatically at the top of every training script.

### Google Colab

Option A — set the environment variable directly (simplest, credentials visible in notebook):
```python
import os
os.environ['DATABASE_URL'] = "postgresql://postgres:PASSWORD@switchback.proxy.rlwy.net:36668/railway"
```

Option B — use Colab Secrets (recommended for shared notebooks):
1. Click the 🔑 key icon in the left sidebar
2. Add a secret named `DATABASE_URL` with the full connection string as the value
3. In your notebook cell:
```python
from google.colab import userdata
import os
os.environ['DATABASE_URL'] = userdata.get('DATABASE_URL')
```

### Kaggle Notebooks

Option A — set directly:
```python
import os
os.environ['DATABASE_URL'] = "postgresql://postgres:PASSWORD@switchback.proxy.rlwy.net:36668/railway"
```

Option B — use Kaggle Secrets (recommended):
1. Go to Notebook Settings → Add-ons → Secrets
2. Add a secret: name = `DATABASE_URL`, value = the full connection string
3. In your notebook:
```python
from kaggle_secrets import UserSecretsClient
import os
secrets = UserSecretsClient()
os.environ['DATABASE_URL'] = secrets.get_secret("DATABASE_URL")
```

### Railway (deployed service)

When running inside a Railway service, the internal hostname works:
```
DATABASE_URL=postgresql://postgres:PASSWORD@postgres.railway.internal:5432/railway
```
Railway automatically injects this as an environment variable — no `.env` file needed.

---

## Training Without a Database (Synthetic Mode)

If you don't have access to the Railway database, all four models can be trained on high-quality synthetic Egyptian climate data:

```bash
python scripts/train_all_models.py --synthetic --gpu
```

Synthetic data covers 119 locations × 3 years across Egypt's five climate bands (Delta, Cairo, Middle Egypt, Upper Egypt, Deep South). Training metrics will be slightly lower than with real data but the models will be fully functional.

---

## Troubleshooting

### "DATABASE_URL not found"

- Check that `.env` exists in the project root (not in `scripts/`)
- Verify the file is named exactly `.env` (not `.env.txt`)
- Make sure `python-dotenv` is installed: `pip install python-dotenv`

### "Connection timed out" or "could not translate host name"

- You are using the internal Railway hostname (`postgres.railway.internal`)
- Switch to the public proxy URL from the Railway dashboard
- Test connectivity: `ping switchback.proxy.rlwy.net`

### "SSL connection has been closed unexpectedly"

Add `?sslmode=require` to the end of your DATABASE_URL:
```
DATABASE_URL=postgresql://postgres:PASSWORD@HOST:PORT/railway?sslmode=require
```

### "Table does not exist"

The database migrations haven't been run, or you're connected to the wrong database.
```bash
python manage.py showmigrations
python manage.py migrate
```

### "too many connections"

Railway's free tier limits connections. Training scripts use Django ORM which pools connections. If you see this error, wait a minute and retry, or reduce `--batch-size`.

---

## Security Notes

- Never commit `.env` to Git — it's already listed in `.gitignore`
- Use `.env.example` as a template for other developers (no real credentials)
- Rotate credentials immediately if they are accidentally pushed to a public repository (Railway Dashboard → PostgreSQL → Credentials → Reset password)
- When sharing Colab/Kaggle notebooks, use platform secrets rather than hardcoding credentials in cells
