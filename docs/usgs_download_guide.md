# Sentinel-2 Auto-Download Guide
## Shamsi Smart — Egyptian Satellite Imagery Pipeline

---

## Why Copernicus, not USGS?

Sentinel-2 is a **European Space Agency (ESA)** mission and is distributed exclusively through the **Copernicus** ecosystem. USGS EarthExplorer carries Landsat (NASA/USGS) imagery only — searching for Sentinel-2 there returns zero results.

| Imagery | Source | Library |
|---------|--------|---------|
| Sentinel-2 (10 m/px, RGB) | Copernicus Data Space | `sentinelsat` |
| Landsat 8/9 (30 m/px, multi-band) | USGS EarthExplorer | `landsatxplore` |

For roof detection at 640×640 tiles we need the 10 m resolution that Sentinel-2 provides, making Copernicus the correct source.

---

## Why These 5 Cities?

The five cities were chosen to give the YOLOv8 model maximum **geographic and climatic diversity** across Egypt's main zones:

### Nile Delta Region (3 cities)
Egypt's most densely populated area, with distinct flat rooftop styles and high urban density.

**Cairo** (lat 30.04°N) — Capital and largest city. Diverse mix of modern high-rises, old urban fabric, and informal housing. The largest single source of varied rooftop types in Egypt. A 0.25° buffer (~25 km) captures Greater Cairo including Giza and Heliopolis.

**Alexandria** (lat 31.20°N) — Mediterranean coastline means higher humidity and occasional cloud cover — the model needs to generalise beyond perfectly dry conditions. Different roof materials (more terracotta, lighter colours) versus Cairo.

**Kafr El Sheikh** (lat 31.11°N) — Chosen specifically because it is your university city. Agricultural Delta region with lower building density, mixed residential and industrial rooftops. Covers the gap between Alexandria and the eastern Delta that would otherwise be missing from training data.

### Upper Egypt (1 city)
**Aswan** (lat 24.09°N) — Extreme solar irradiance (highest in Egypt, ~2,800 kWh/kWp/year). Very low humidity, rare cloud cover (consistently <5%). Distinctive rooftop styles with flat concrete and Nubian architectural elements. Important for the model to learn rooftops under intense sunlight conditions.

### Red Sea Coast (1 city)
**Hurghada** (lat 27.26°N) — Mixed tourist resort and industrial port. Lower building density than Delta cities, with large hotel rooftops and solar installations already common. A smaller buffer (0.15°) captures the built-up coastal strip without including empty desert.

### Coverage summary

```
Egypt bounding box covered:
  Latitude:  24° N (Aswan) → 31.2° N (Alexandria)  — 730 km north-south
  Longitude: 29.9° E (Alexandria) → 33.8° E (Hurghada) — 440 km east-west

Climate zones represented:
  Humid Mediterranean  → Alexandria
  Arid desert-urban    → Cairo, Kafr El Sheikh
  Hyper-arid Upper     → Aswan
  Coastal semi-arid    → Hurghada
```

---

## One-Time Setup: Create a Copernicus Account

This takes about 2 minutes and is completely free.

1. Go to **https://browser.dataspace.copernicus.eu/**
2. Click **"Register"** in the top-right corner
3. Fill in your name, email, and choose a password
4. Check your email and click the activation link
5. Log back in to confirm the account is active

Your USGS credentials (`mohammedhabdullah@outlook.com`) are for Landsat only and will not work here — a separate Copernicus account is needed.

### Add credentials to .env

Open `shamsi-backend-main/.env` and add:

```
COPERNICUS_USERNAME=your_email@example.com
COPERNICUS_PASSWORD=your_password
```

The `.env` file is git-ignored, so these credentials stay on your machine only.

---

## Running the Download Script

### Quick start — all 5 cities

```powershell
python scripts/usgs_auto_download.py
```

### Test authentication first (no download)

```powershell
python scripts/usgs_auto_download.py --dry-run
```

Expected dry-run output:
```
🔐  Connecting to Copernicus Open Access Hub…
    ✅  Connected successfully

🔍  Searching Sentinel-2 L2A for Cairo…
    ✅  Best scene (8 found):
       Title : S2A_MSIL2A_20260512_N0510_R...
       Date  : 2026-05-12
       Cloud : 2.3%
       Size  : 1.1 GB

    [DRY RUN]  Would download: S2A_MSIL2A_20260512_...
    [DRY RUN]  Target dir: E:\...\data\satellite\downloads\Cairo
...
✅  Searched: 5 / 5 cities
```

### Download specific cities only

```powershell
python scripts/usgs_auto_download.py --cities Cairo,Kafr_El_Sheikh
```

### Relax cloud cover filter (useful in summer)

```powershell
python scripts/usgs_auto_download.py --max-cloud 20
```

### Extend search window (more scenes to choose from)

```powershell
python scripts/usgs_auto_download.py --start-date 2024-01-01
```

### Pass credentials directly (no .env needed)

```powershell
python scripts/usgs_auto_download.py --user me@email.com --password MyPass
```

---

## Expected File Sizes and Times

| City | Approx. size | Download time (50 Mbps) |
|------|-------------|-------------------------|
| Cairo | 1.1–1.5 GB | 3–5 min |
| Alexandria | 1.0–1.4 GB | 3–5 min |
| Kafr El Sheikh | 1.0–1.3 GB | 3–4 min |
| Aswan | 0.9–1.2 GB | 3–4 min |
| Hurghada | 0.8–1.1 GB | 2–3 min |
| **Total** | **~7–10 GB** | **~20–30 min active** |

Copernicus allows 2 concurrent downloads on the free tier, so downloading all 5 sequentially takes 20–30 minutes on a good connection.

### Output structure

```
data/satellite/downloads/
├── Cairo/
│   └── S2A_MSIL2A_20260512_N0510_R035_T36RTT_20260512T090123.zip
├── Alexandria/
│   └── S2B_MSIL2A_20260511_N0510_R092_T35SPB_20260511T085612.zip
├── Kafr_El_Sheikh/
│   └── S2A_MSIL2A_20260510_N0510_R035_T36RUT_20260510T091045.zip
├── Aswan/
│   └── S2A_MSIL2A_20260508_N0510_R035_T36PWS_20260508T083412.zip
└── Hurghada/
    └── S2B_MSIL2A_20260509_N0510_R092_T37QFG_20260509T084523.zip
```

Each `.zip` contains all Sentinel-2 bands. For roof detection, the TCI (True Colour Image) band at 10 m is what we use.

---

## Troubleshooting

### "Credentials not set"

Your `.env` file is missing or doesn't have the Copernicus credentials. See the setup section above.

### "401 Unauthorized"

Your username or password is wrong, or the account is not activated. Check:
1. Log in manually at https://browser.dataspace.copernicus.eu/ to confirm credentials
2. Check your registration email for an activation link
3. Make sure there are no trailing spaces in the `.env` values

### "No scenes found with cloud ≤ 10%"

Very common in summer for Delta cities (June–August). Solutions:
```powershell
# Relax to 20%
python scripts/usgs_auto_download.py --max-cloud 20

# Or search a wider date range (winter is clearer)
python scripts/usgs_auto_download.py --start-date 2023-10-01 --end-date 2024-03-31
```

### "Scene is in Long-Term Archive (offline storage)"

Scenes older than 12 months are moved to offline storage. Copernicus will bring them back online within 24 hours of a request. The script will inform you when this happens — simply re-run the next day, or search for a more recent scene.

### "Download quota reached / 429 error"

The free tier allows 2 concurrent downloads. If you're running multiple scripts or another download is active, wait a few minutes and retry. The script will show: `💡 Copernicus allows 2 concurrent downloads on the free tier.`

### "Network timeout"

Large files (1+ GB) over slow connections may time out. The script retries 3 times with increasing delays (30s, 60s). If it keeps failing:
- Check your internet connection stability
- Try downloading during off-peak hours
- Consider using the Copernicus Browser web interface to download manually

### "shapely not found" or "sentinelsat not found"

```powershell
pip install sentinelsat shapely
```

---

## After Download: Next Steps

### Step 1 — Validate the downloads

```powershell
python scripts/download_sentinel2.py --validate data/satellite/downloads/ --verbose
```

A healthy file shows `✅` with 10 m resolution and bounds overlapping Egypt.

### Step 2 — Extract 640×640 roof tiles

```powershell
python scripts/extract_roofs_from_geotiff.py ^
    --input  data/satellite/downloads/ ^
    --output datasets/egyptian_roofs/ ^
    --tile-size 640 ^
    --stride 320 ^
    --split 0.8
```

Expect 200–800 tiles per city (1,000–4,000 total).

### Step 3 — Auto-annotate with SAM

```powershell
python scripts/semi_auto_annotate.py --download-sam
python scripts/semi_auto_annotate.py ^
    --images datasets/egyptian_roofs/images/train/ ^
    --output datasets/egyptian_roofs/labels/train/ ^
    --device cuda
```

### Step 4 — Train YOLOv8

```powershell
python scripts/train_yolov8_roof.py --device 0 --epochs 100 --copy-best
```

---

## Security Notes

- Your Copernicus credentials live only in `.env`, which is git-ignored
- Never paste passwords or tokens directly into script source files
- If credentials are accidentally committed to Git, change the password immediately at https://browser.dataspace.copernicus.eu/profile
- The `.env.example` file uses placeholder values safe to commit
