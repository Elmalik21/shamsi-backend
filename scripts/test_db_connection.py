"""
scripts/test_db_connection.py
==============================
Test Railway PostgreSQL database connection for Shamsi Smart.

Loads DATABASE_URL from the project's .env file, connects to Railway,
and reports record counts for all key tables.

Usage
-----
    python scripts/test_db_connection.py

Expected output (when connected successfully)
----------------------------------------------
    ✅ Connection successful!

    📊 Database Summary:
      - Climate records : 341,991
      - Locations       : 119
      - Solar panels    : 8
      - Inverters       : 7

    ✅ Database has sufficient data for training
       Ready to run: python scripts/train_all_models.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Load .env from project root ───────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()   # fall back to CWD .env or environment variables
except ImportError:
    # python-dotenv not installed — rely on environment variables already set
    pass


def _mask_password(url: str) -> str:
    """Replace the password in a PostgreSQL URL with asterisks."""
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        masked = parsed._replace(
            netloc=f"{parsed.username}:{'*' * 20}@{parsed.hostname}:{parsed.port}"
        )
        return urlunparse(masked)
    except Exception:
        return '<URL hidden>'


def test_connection() -> bool:
    """
    Test database connectivity and print a table summary.

    Returns True on success, False on failure.
    """
    db_url = os.getenv('DATABASE_URL')

    if not db_url:
        print("\n❌  DATABASE_URL not found!\n")
        print("    Please create a .env file in the project root:")
        env_path = Path(__file__).parent.parent / '.env'
        print(f"    {env_path}\n")
        print("    With the following content:")
        print("      DATABASE_URL=postgresql://postgres:PASSWORD@HOST:PORT/railway\n")
        print("    Get your public URL from:")
        print("      Railway Dashboard → PostgreSQL service → Connect tab → Public URL\n")
        return False

    print("\n🔍  Testing Railway PostgreSQL Connection…\n")

    # Show connection details (password masked)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(db_url)
        print(f"    Host     : {parsed.hostname}")
        print(f"    Port     : {parsed.port}")
        print(f"    Database : {parsed.path.lstrip('/')}")
        print(f"    User     : {parsed.username}")
        print(f"    Password : {'*' * 20}  (hidden)\n")

        # Warn if using internal Railway hostname
        if parsed.hostname and 'railway.internal' in parsed.hostname:
            print(
                "    ⚠️  WARNING: You are using the internal Railway hostname.\n"
                "       This only works inside Railway's private network.\n"
                "       Replace DATABASE_URL with the PUBLIC proxy URL:\n"
                "       Railway Dashboard → PostgreSQL → Connect → Public URL\n"
            )
    except Exception:
        pass

    print("    Connecting…")

    # ── Attempt connection (psycopg2 first, SQLAlchemy fallback) ──────────────
    try:
        counts = _connect_psycopg2(db_url)
    except ImportError:
        try:
            counts = _connect_sqlalchemy(db_url)
        except ImportError:
            print(
                "\n❌  Neither psycopg2 nor SQLAlchemy is installed.\n"
                "    Install with:  pip install psycopg2-binary\n"
                "              or:  pip install sqlalchemy\n"
            )
            return False
    except Exception as exc:
        _print_failure(exc)
        return False

    # ── Print results ─────────────────────────────────────────────────────────
    print("\n✅  Connection successful!\n")
    print("    📊 Database Summary:")
    for label, count in counts.items():
        print(f"      - {label:<20}: {count:,}")
    print()

    climate = counts.get('Climate records', 0)
    if climate > 300_000:
        print(f"    ✅  Database has sufficient data for training ({climate:,} records)")
        print("       Ready to run: python scripts/train_all_models.py")
    elif climate > 0:
        print(f"    ⚠️   Only {climate:,} climate records found — expected ~341,991")
        print("       Training will work but metrics may differ from expected")
    else:
        print("    ⚠️   No climate records found — check table migrations")

    print()
    return True


def _connect_psycopg2(db_url: str) -> dict:
    """Connect via psycopg2 and return table row counts."""
    import psycopg2

    conn   = psycopg2.connect(db_url)
    cursor = conn.cursor()

    counts = {}
    table_map = {
        'Climate records': 'solar_data_dailyclimatedata',
        'Locations':       'solar_data_location',
        'Solar panels':    'solar_data_solarpanel',
        'Inverters':       'solar_data_inverter',
    }
    for label, table in table_map.items():
        try:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[label] = cursor.fetchone()[0]
        except Exception:
            counts[label] = 'N/A (table not found)'

    cursor.close()
    conn.close()
    return counts


def _connect_sqlalchemy(db_url: str) -> dict:
    """Connect via SQLAlchemy and return table row counts."""
    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    counts = {}
    table_map = {
        'Climate records': 'solar_data_dailyclimatedata',
        'Locations':       'solar_data_location',
        'Solar panels':    'solar_data_solarpanel',
        'Inverters':       'solar_data_inverter',
    }
    with engine.connect() as conn:
        for label, table in table_map.items():
            try:
                result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                counts[label] = result.fetchone()[0]
            except Exception:
                counts[label] = 'N/A (table not found)'
    return counts


def _print_failure(exc: Exception) -> None:
    """Print a human-friendly connection failure message."""
    msg = str(exc)
    print(f"\n❌  Connection failed!\n")
    print(f"    Error: {msg}\n")
    print("    💡 Troubleshooting:")
    print("       1. Check DATABASE_URL in .env is correct")
    print("       2. Verify Railway database service is running")
    print("          (Railway Dashboard → PostgreSQL → check status)")
    print("       3. Make sure you are using the PUBLIC proxy URL,")
    print("          not postgres.railway.internal")
    print("       4. Check your internet / firewall is not blocking")
    print(f"          the Railway proxy host")
    print()
    print("    📌 Quick fix:")
    print("       python scripts/test_db_connection.py  (run again after fixing .env)")
    print("       python scripts/train_all_models.py --synthetic  (skip DB entirely)")


# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    success = test_connection()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
