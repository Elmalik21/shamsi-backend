"""
ai_engine/computer_vision/image_utils.py
==========================================
Satellite imagery utilities for Shamsi Smart roof analysis.

Responsibilities
----------------
- Fetch satellite images (Google Static Maps, Mapbox, or offline)
- Compute ground resolution (meters/pixel) at given lat/zoom
- Convert pixel areas to square metres
- Enhance image contrast for roof detection
- Draw panel layout overlays on annotated images
- Generate synthetic test images (no API key required)

Author: Shamsi Smart AI Team
"""
from __future__ import annotations

import io
import logging
import math
import os
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── Optional heavy imports ────────────────────────────────────────────────────
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logger.debug("opencv-python not installed — some image functions will be limited.")

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Panel colours for layout overlay
PANEL_COLOUR       = (65, 105, 225)   # Royal Blue (BGR for OpenCV)
PANEL_COLOUR_PIL   = (65, 105, 225)   # RGB for PIL
ROOF_COLOUR        = (0, 255, 0)      # Green — roof boundary
OBSTACLE_COLOUR    = (0, 0, 255)      # Red — obstacles

# Google Static Maps tile formula constants
# meters/pixel = 156543.03392 * cos(lat_rad) / 2^zoom
_TILE_CONSTANT = 156543.03392


# ─────────────────────────────────────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────────────────────────────────────

class ImageProcessor:
    """
    Static utility class for satellite image processing.

    All methods are @staticmethod so they can be called without
    instantiation:  ImageProcessor.estimate_meters_per_pixel(30.0, 19)
    """

    # ── Ground resolution ─────────────────────────────────────────────────────

    @staticmethod
    def estimate_meters_per_pixel(latitude: float, zoom: int) -> float:
        """
        Ground resolution at the given latitude and Web Mercator zoom level.

        Formula (Web Mercator / Slippy Map tiles):
            meters/pixel = 156543.03392 × cos(lat_rad) / 2^zoom

        Parameters
        ----------
        latitude : float   Site latitude in decimal degrees
        zoom     : int     Tile zoom level (17=1.2m, 18=0.6m, 19=0.3m, 20=0.15m)

        Returns
        -------
        float  Metres per pixel at the given location and zoom.

        Examples
        --------
        >>> ImageProcessor.estimate_meters_per_pixel(30.0, 19)
        0.298   # ~0.3 m/pixel — good for roof detection
        """
        return _TILE_CONSTANT * math.cos(math.radians(latitude)) / (2 ** zoom)

    @staticmethod
    def pixel_area_to_meters(pixel_area: float, meters_per_pixel: float) -> float:
        """
        Convert a pixel-count area to square metres.

        Parameters
        ----------
        pixel_area       : float  Area in pixels²
        meters_per_pixel : float  Ground resolution [m/px]

        Returns
        -------
        float  Area in m²
        """
        return pixel_area * (meters_per_pixel ** 2)

    @staticmethod
    def pixels_to_meters(pixels: float, meters_per_pixel: float) -> float:
        """Convert a linear pixel measurement to metres."""
        return pixels * meters_per_pixel

    # ── Image fetching ────────────────────────────────────────────────────────

    @staticmethod
    def fetch_satellite_image(
        latitude: float,
        longitude: float,
        zoom: int = 19,
        size: int = 640,
        source: str = 'google',
        api_key: Optional[str] = None,
    ) -> np.ndarray:
        """
        Fetch a satellite image centred on (latitude, longitude).

        Supported sources
        -----------------
        'google'  : Google Static Maps API  (requires GOOGLE_MAPS_API_KEY env var)
        'mapbox'  : Mapbox Satellite API    (requires MAPBOX_TOKEN env var)
        'osm'     : OpenStreetMap tile      (free, lower quality)
        'synthetic': Generate a synthetic test image (no API key needed)

        Parameters
        ----------
        latitude, longitude : float  Centre of the image
        zoom                : int    Zoom level (19 recommended for roofs)
        size                : int    Output image size in pixels (square)
        source              : str    Imagery provider
        api_key             : str    Override env-var API key

        Returns
        -------
        np.ndarray  Shape (size, size, 3) RGB uint8

        Raises
        ------
        ValueError  If source is unknown or API key is missing
        RuntimeError If network request fails
        """
        source = source.lower()

        if source == 'synthetic':
            return ImageProcessor._synthetic_roof_image(size)

        if source == 'google':
            return ImageProcessor._fetch_google(
                latitude, longitude, zoom, size,
                api_key or os.environ.get('GOOGLE_MAPS_API_KEY', '')
            )

        if source == 'mapbox':
            return ImageProcessor._fetch_mapbox(
                latitude, longitude, zoom, size,
                api_key or os.environ.get('MAPBOX_TOKEN', '')
            )

        if source == 'osm':
            return ImageProcessor._fetch_osm_tile(latitude, longitude, zoom, size)

        if source == 'esri':
            return ImageProcessor._fetch_esri_tile(latitude, longitude, zoom, size)

        if source == 'auto':
            # Smart auto-selection: try best-quality free source first
            return ImageProcessor._auto_fetch(latitude, longitude, zoom, size, api_key)

        raise ValueError(f"Unknown source '{source}'. Use: google, mapbox, osm, esri, auto, synthetic.")

    @staticmethod
    def _fetch_google(lat, lon, zoom, size, api_key) -> np.ndarray:
        """Fetch from Google Static Maps API."""
        if not api_key:
            raise ValueError(
                "Google Maps API key required. "
                "Set GOOGLE_MAPS_API_KEY environment variable or pass api_key=."
            )
        try:
            import requests
        except ImportError:
            raise ImportError("pip install requests")

        url = (
            f"https://maps.googleapis.com/maps/api/staticmap"
            f"?center={lat},{lon}"
            f"&zoom={zoom}"
            f"&size={size}x{size}"
            f"&maptype=satellite"
            f"&key={api_key}"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img = np.frombuffer(resp.content, dtype=np.uint8)
        if CV2_AVAILABLE:
            return cv2.imdecode(img, cv2.IMREAD_COLOR)
        return np.array(PILImage.open(io.BytesIO(resp.content)).convert('RGB'))

    @staticmethod
    def _fetch_mapbox(lat, lon, zoom, size, token) -> np.ndarray:
        """Fetch from Mapbox Satellite API."""
        if not token:
            raise ValueError(
                "Mapbox token required. "
                "Set MAPBOX_TOKEN environment variable."
            )
        try:
            import requests
        except ImportError:
            raise ImportError("pip install requests")

        url = (
            f"https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static"
            f"/{lon},{lat},{zoom},0"
            f"/{size}x{size}"
            f"?access_token={token}"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        img_array = np.frombuffer(resp.content, dtype=np.uint8)
        if CV2_AVAILABLE:
            return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return np.array(PILImage.open(io.BytesIO(resp.content)).convert('RGB'))

    @staticmethod
    def _auto_fetch(lat, lon, zoom, size, api_key=None) -> np.ndarray:
        """
        Auto-select best available satellite source.
        Priority: Mapbox (if token set) → ESRI World Imagery (free) → synthetic.
        """
        import os
        mapbox_token = api_key or os.environ.get('MAPBOX_TOKEN', '')
        if mapbox_token:
            try:
                return ImageProcessor._fetch_mapbox(lat, lon, zoom, size, mapbox_token)
            except Exception:
                pass  # fall through to ESRI

        try:
            return ImageProcessor._fetch_esri_tile(lat, lon, zoom, size)
        except Exception:
            pass  # fall through to synthetic

        logger.warning("All satellite sources failed — using synthetic image.")
        return ImageProcessor._synthetic_roof_image(size)

    @staticmethod
    def _fetch_esri_tile(lat, lon, zoom, size) -> np.ndarray:
        """
        Fetch ESRI World Imagery satellite tile — free, no API key required.

        ESRI World Imagery provides cloud-free, high-resolution imagery for most of Egypt.
        Tile URL format: /MapServer/tile/{z}/{y}/{x}
        At zoom 19 this gives ~0.3 m/px — ideal for roof detection.
        """
        try:
            import requests
        except ImportError:
            raise ImportError("pip install requests")

        # Convert lat/lon to Slippy Map tile coordinates
        import math
        lat_r = math.radians(lat)
        n = 2 ** zoom
        xtile = int((lon + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)

        url = (
            f"https://server.arcgisonline.com/ArcGIS/rest/services/"
            f"World_Imagery/MapServer/tile/{zoom}/{ytile}/{xtile}"
        )
        headers = {'User-Agent': 'ShamsiSmart/2.0 (solar-energy-research; Egypt)'}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        if PIL_AVAILABLE:
            from PIL import Image as PILImage
            import io
            img = PILImage.open(io.BytesIO(resp.content)).convert('RGB')
            img = img.resize((size, size), PILImage.LANCZOS)
            arr = np.array(img)
            # Convert RGB → BGR for OpenCV compatibility
            if CV2_AVAILABLE:
                return arr[:, :, ::-1].copy()
            return arr

        if CV2_AVAILABLE:
            img_arr = np.frombuffer(resp.content, dtype=np.uint8)
            return cv2.imdecode(img_arr, cv2.IMREAD_COLOR)

        raise ImportError("Install opencv-python or Pillow to decode ESRI tiles.")

    @staticmethod
    def _fetch_osm_tile(lat, lon, zoom, size) -> np.ndarray:
        """
        Fetch and stitch OSM tiles (free, no API key).
        Returns a single tile resized to `size`.
        """
        try:
            import requests
        except ImportError:
            raise ImportError("pip install requests")

        # Convert lat/lon to tile coordinates
        lat_r = math.radians(lat)
        n = 2 ** zoom
        xtile = int((lon + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_r)) / math.pi) / 2.0 * n)

        url = f"https://tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png"
        headers = {'User-Agent': 'ShamsiSmart/2.0 (solar-energy-research)'}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        img = PILImage.open(io.BytesIO(resp.content)).convert('RGB')
        img = img.resize((size, size), PILImage.LANCZOS)
        return np.array(img)

    @staticmethod
    def _synthetic_roof_image(size: int = 640) -> np.ndarray:
        """
        Generate a realistic synthetic Egyptian flat-roof image.
        Used for testing without any API key.

        Creates a grey concrete roof with:
        - Rectangular roof boundary
        - 1-2 AC unit rectangles
        - 1 water tank circle
        - Optional satellite dish
        """
        rng = np.random.default_rng(42)
        img = np.full((size, size, 3), 180, dtype=np.uint8)  # grey sky/background

        # Roof surface (lighter grey concrete)
        pad = size // 8
        roof_colour = int(rng.integers(140, 170))
        img[pad:size - pad, pad:size - pad] = roof_colour

        # Add texture noise
        noise = rng.integers(-15, 15, (size - 2 * pad, size - 2 * pad, 3))
        img[pad:size - pad, pad:size - pad] = np.clip(
            img[pad:size - pad, pad:size - pad].astype(int) + noise, 0, 255
        ).astype(np.uint8)

        if CV2_AVAILABLE:
            # Draw obstacles
            # AC unit 1
            ac1_x, ac1_y = size // 3, size // 3
            cv2.rectangle(img, (ac1_x, ac1_y), (ac1_x + 40, ac1_y + 25),
                          (100, 100, 120), -1)
            cv2.rectangle(img, (ac1_x, ac1_y), (ac1_x + 40, ac1_y + 25),
                          (60, 60, 80), 2)

            # Water tank
            cx, cy = size * 2 // 3, size // 3
            cv2.circle(img, (cx, cy), 28, (90, 90, 95), -1)
            cv2.circle(img, (cx, cy), 28, (50, 50, 55), 2)

            # AC unit 2
            ac2_x, ac2_y = size // 2, size * 2 // 3
            cv2.rectangle(img, (ac2_x, ac2_y), (ac2_x + 35, ac2_y + 22),
                          (95, 95, 115), -1)

            # Roof edge shadow
            cv2.rectangle(img, (pad, pad), (size - pad, size - pad),
                          (100, 100, 100), 3)

        return img

    # ── Image enhancement ─────────────────────────────────────────────────────

    @staticmethod
    def enhance_roof_contrast(image: np.ndarray) -> np.ndarray:
        """
        Enhance satellite image for better roof detection in Egyptian conditions.

        Steps
        -----
        1. Convert to LAB colour space
        2. Apply CLAHE to the L channel (contrast-limited adaptive histogram equalisation)
        3. Sharpen edges (Unsharp Masking)
        4. Normalize brightness (Egypt's intense sunlight causes overexposure)

        Parameters
        ----------
        image : np.ndarray  Input image (H, W, 3) BGR (OpenCV) or RGB

        Returns
        -------
        np.ndarray  Enhanced image, same shape and dtype
        """
        if not CV2_AVAILABLE:
            logger.warning("opencv not installed — skipping enhancement.")
            return image

        # CLAHE on L channel
        lab  = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_eq  = clahe.apply(l)
        lab_eq = cv2.merge([l_eq, a, b])
        enhanced = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)

        # Unsharp mask for edge sharpening
        blurred   = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=3)
        sharpened = cv2.addWeighted(enhanced, 1.5, blurred, -0.5, 0)

        return sharpened

    @staticmethod
    def normalize_shadow(image: np.ndarray) -> np.ndarray:
        """
        Reduce shadow effects caused by bright Egyptian sunlight.
        Uses gamma correction and local contrast normalisation.
        """
        if not CV2_AVAILABLE:
            return image

        # Gamma correction (gamma < 1 brightens shadows)
        gamma = 0.8
        lut   = np.array([((i / 255.0) ** gamma) * 255 for i in range(256)],
                         dtype=np.uint8)
        corrected = cv2.LUT(image, lut)
        return corrected

    # ── Drawing utilities ─────────────────────────────────────────────────────

    @staticmethod
    def draw_panel_layout(
        image: np.ndarray,
        roof_polygon: np.ndarray,
        panel_positions: List[Tuple[int, int]],
        panel_size_px: Tuple[int, int],
        meters_per_pixel: float,
        panel_power_w: int = 580,
    ) -> np.ndarray:
        """
        Draw roof boundary + solar panel layout on the image.

        Parameters
        ----------
        image            : np.ndarray    Background satellite image (BGR)
        roof_polygon     : np.ndarray    (N, 2) polygon points in pixel coords
        panel_positions  : list of (x, y) top-left corners for each panel [pixels]
        panel_size_px    : (width_px, height_px) of each panel
        meters_per_pixel : float         Ground resolution for caption
        panel_power_w    : int           Panel rated power for total kW caption

        Returns
        -------
        np.ndarray  Annotated image (copy, does not modify input)
        """
        if not CV2_AVAILABLE:
            logger.warning("opencv not installed — cannot draw layout.")
            return image

        out = image.copy()
        pw, ph = panel_size_px

        # Draw roof boundary
        if len(roof_polygon) > 2:
            pts = roof_polygon.reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(out, [pts], isClosed=True,
                          color=ROOF_COLOUR, thickness=3)
            overlay = out.copy()
            cv2.fillPoly(overlay, [pts], color=(0, 255, 0))
            cv2.addWeighted(overlay, 0.08, out, 0.92, 0, out)

        # Draw panels
        for (px, py) in panel_positions:
            cv2.rectangle(out, (px, py), (px + pw, py + ph),
                          PANEL_COLOUR, -1)
            cv2.rectangle(out, (px, py), (px + pw, py + ph),
                          (255, 255, 255), 1)

        # Caption
        n_panels   = len(panel_positions)
        total_kw   = round(n_panels * panel_power_w / 1000, 2)
        caption    = f"{n_panels} panels | {total_kw} kW | {meters_per_pixel:.2f} m/px"
        cv2.putText(out, caption, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(out, caption, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)

        return out

    @staticmethod
    def draw_detection_results(
        image: np.ndarray,
        roof_polygon: Optional[np.ndarray],
        obstacles: List[dict],
        usable_area_m2: float,
        roof_area_m2: float,
    ) -> np.ndarray:
        """
        Draw detection results: roof boundary + obstacle bounding boxes.

        Parameters
        ----------
        image          : BGR satellite image
        roof_polygon   : (N, 2) boundary polygon or None
        obstacles      : list of dicts from EgyptianRoofDetector.detect_roof()
        usable_area_m2 : calculated usable area
        roof_area_m2   : total detected roof area

        Returns
        -------
        np.ndarray  Annotated image
        """
        if not CV2_AVAILABLE:
            return image

        out = image.copy()

        # Roof polygon
        if roof_polygon is not None and len(roof_polygon) > 2:
            pts = roof_polygon.reshape((-1, 1, 2)).astype(np.int32)
            cv2.polylines(out, [pts], True, ROOF_COLOUR, 3)

        # Obstacle boxes
        colours = {
            'chimney':       (0, 0, 255),
            'ac_unit':       (255, 0, 0),
            'water_tank':    (0, 165, 255),
            'satellite_dish':(128, 0, 128),
            'tree_shadow':   (0, 128, 0),
            'vent':          (255, 165, 0),
            'shade_structure':(0, 128, 128),
        }
        for obs in obstacles:
            cls   = obs.get('class', 'unknown')
            bbox  = obs.get('bbox', [])
            conf  = obs.get('confidence', 0.0)
            colour = colours.get(cls, (200, 200, 200))
            if len(bbox) == 4:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
                label = f"{cls} {conf:.2f}"
                cv2.rectangle(out, (x1, y1 - 18), (x1 + len(label) * 9, y1), colour, -1)
                cv2.putText(out, label, (x1 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Summary banner
        pct  = round(usable_area_m2 / max(roof_area_m2, 0.01) * 100, 1)
        text = f"Roof: {roof_area_m2:.0f}m2  Usable: {usable_area_m2:.0f}m2 ({pct}%)"
        h    = out.shape[0]
        cv2.rectangle(out, (0, h - 35), (out.shape[1], h), (0, 0, 0), -1)
        cv2.putText(out, text, (8, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 150), 2)

        return out

    # ── Format helpers ────────────────────────────────────────────────────────

    @staticmethod
    def load_image(path: str) -> np.ndarray:
        """Load an image file → BGR numpy array (OpenCV convention)."""
        if CV2_AVAILABLE:
            img = cv2.imread(path)
            if img is None:
                raise FileNotFoundError(f"Could not load image: {path}")
            return img
        if PIL_AVAILABLE:
            pil = PILImage.open(path).convert('RGB')
            return np.array(pil)[:, :, ::-1]   # RGB→BGR
        raise ImportError("Install opencv-python or Pillow to load images.")

    @staticmethod
    def save_image(image: np.ndarray, path: str) -> None:
        """Save a BGR numpy array to file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        if CV2_AVAILABLE:
            cv2.imwrite(path, image)
        elif PIL_AVAILABLE:
            PILImage.fromarray(image[:, :, ::-1]).save(path)
        else:
            raise ImportError("Install opencv-python or Pillow to save images.")

    @staticmethod
    def image_to_bytes(image: np.ndarray, format: str = '.jpg') -> bytes:
        """Encode a BGR image to bytes (for HTTP responses)."""
        if CV2_AVAILABLE:
            _, buf = cv2.imencode(format, image)
            return buf.tobytes()
        raise ImportError("opencv-python required for image_to_bytes.")

    @staticmethod
    def crop_to_polygon(image: np.ndarray, polygon: np.ndarray) -> np.ndarray:
        """Return the bounding-box crop of `image` around `polygon`."""
        if not CV2_AVAILABLE:
            return image
        x, y, w, h = cv2.boundingRect(polygon.astype(np.int32))
        return image[y:y + h, x:x + w]
        }
        for obs in obstacles:
            cls   = obs.get('class', 'unknown')
            bbox  = obs.get('bbox', [])
            conf  = obs.get('confidence', 0.0)
            colour = colours.get(cls, (200, 200, 200))
            if len(bbox) == 4:
                x1, y1, x2, y2 = [int(v) for v in bbox]
                cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
                label = f"{cls} {conf:.2f}"
                cv2.rectangle(out, (x1, y1 - 18), (x1 + len(label) * 9, y1), colour, -1)
                cv2.putText(out, label, (x1 + 2, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Summary banner
        pct  = round(usable_area_m2 / max(roof_area_m2, 0.01) * 100, 1)
        text = f"Roof: {roof_area_m2:.0f}m2  Usable: {usable_area_m2:.0f}m2 ({pct}%)"
        h    = out.shape[0]
        cv2.rectangle(out, (0, h - 35), (out.shape[1], h), (0, 0, 0), -1)
        cv2.putText(out, text, (8, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 150), 2)

        return out

    # ── Format helpers ────────────────────────────────────────────────────────

    @staticmethod
    def load_image(path: str) -> np.ndarray:
        """Load an image file → BGR numpy array (OpenCV convention)."""
        if CV2_AVAILABLE:
            img = cv2.imread(path)
            if img is None:
                raise FileNotFoundError(f"Could not load image: {path}")
            return img
        if PIL_AVAILABLE:
            pil = PILImage.open(path).convert('RGB')
            return np.array(pil)[:, :, ::-1]   # RGB→BGR
        raise ImportError("Install opencv-python or Pillow to load images.")

    @staticmethod
    def save_image(image: np.ndarray, path: str) -> None:
        """Save a BGR numpy array to file."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        if CV2_AVAILABLE:
            cv2.imwrite(path, image)
        elif PIL_AVAILABLE:
            PILImage.fromarray(image[:, :, ::-1]).save(path)
        else:
            raise ImportError("Install opencv-python or Pillow to save images.")

    @staticmethod
    def image_to_bytes(image: np.ndarray, format: str = '.jpg') -> bytes:
        """Encode a BGR image to bytes (for HTTP responses)."""
        if CV2_AVAILABLE:
            _, buf = cv2.imencode(format, image)
            return buf.tobytes()
        raise ImportError("opencv-python required for image_to_bytes.")

    @staticmethod
    def crop_to_polygon(image: np.ndarray, polygon: np.ndarray) -> np.ndarray:
        """Return the bounding-box crop of `image` around `polygon`."""
        if not CV2_AVAILABLE:
            return image
        x, y, w, h = cv2.boundingRect(polygon.astype(np.int32))
        return image[y:y + h, x:x + w]
