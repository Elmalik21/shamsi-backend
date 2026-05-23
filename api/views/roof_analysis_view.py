"""
api/views/roof_analysis_view.py
==================================
Django REST Framework endpoint for automated roof analysis.

Endpoint
--------
    POST /api/v1/ai/analyze-roof/

Request (multipart/form-data)
-----------------------------
    image       : File     Satellite or aerial roof image (JPEG/PNG)
    latitude    : float    Site latitude  (default: 30.0)
    longitude   : float    Site longitude (default: 31.0)
    zoom_level  : int      Map zoom level (default: 19 → ~0.3 m/px)
    panel_power_w: int     Panel wattage  (default: 580 W)

Response 200 OK (JSON)
----------------------
    {
        "roof_area_m2":       156.3,
        "usable_area_m2":     142.1,
        "usable_percentage":  90.9,
        "obstacles": [
            {
                "class":      "ac_unit",
                "area_m2":    3.2,
                "location":   [320, 215],
                "confidence": 0.92,
                "bbox":       [300, 200, 340, 230]
            },
            ...
        ],
        "panel_layout": {
            "max_panels":        42,
            "rows":               6,
            "columns":            7,
            "total_capacity_kw": 24.36,
            "total_coverage_m2": 108.4,
            "efficiency_pct":    76.3,
            "spacing_requirements": {
                "row_spacing_m":    0.68,
                "edge_clearance_m": 0.5
            }
        },
        "shading_analysis": {
            "annual_shading_loss_pct": 5.2,
            "monthly_shading": [3.1, 2.8, 4.0, ...],
            "critical_obstacles": [...]
        },
        "metadata": {
            "meters_per_pixel": 0.298,
            "orientation":      "flat",
            "roof_type":        "concrete",
            "detector_mode":    "yolov8"
        },
        "annotated_image_url": "/media/roof_analysis/abc123_annotated.jpg",
        "layout_image_url":    "/media/roof_analysis/abc123_layout.jpg",
        "analysis_id":         "abc123",
        "processing_time_sec": 1.24
    }

Error responses
---------------
    400  Missing image file
    400  Invalid latitude/longitude
    413  Image too large (> 10 MB)
    500  Internal analysis error
"""
from __future__ import annotations

import logging
import os
import time
import uuid

import numpy as np
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_IMAGE_BYTES    = 10 * 1024 * 1024    # 10 MB
MEDIA_SUBDIR       = 'roof_analysis'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}

DEFAULT_PANEL = {
    'width_m':  1.134,
    'height_m': 2.278,
    'power_w':  580,
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _media_dir() -> str:
    """Return (and create) the media directory for roof analysis outputs."""
    base = getattr(settings, 'MEDIA_ROOT', 'media')
    d    = os.path.join(base, MEDIA_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def _media_url(filename: str) -> str:
    """Build the public URL for a saved media file."""
    base = getattr(settings, 'MEDIA_URL', '/media/')
    return f"{base.rstrip('/')}/{MEDIA_SUBDIR}/{filename}"


def _save_image_array(image: np.ndarray, filename: str) -> str:
    """Save a numpy BGR image and return its public URL."""
    from ai_engine.computer_vision.image_utils import ImageProcessor
    path = os.path.join(_media_dir(), filename)
    ImageProcessor.save_image(image, path)
    return _media_url(filename)


def _validate_request(request: Request) -> tuple[dict | None, Response | None]:
    """
    Validate and extract request parameters.

    Returns (params_dict, None) on success or (None, error_Response) on failure.
    """
    if 'image' not in request.FILES:
        return None, Response(
            {'error': 'No image file provided. Send as multipart/form-data with key "image".'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    image_file = request.FILES['image']

    # Size check
    if image_file.size > MAX_IMAGE_BYTES:
        return None, Response(
            {'error': f'Image too large ({image_file.size/1e6:.1f} MB). Maximum: 10 MB.'},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    # Extension check
    ext = os.path.splitext(image_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None, Response(
            {'error': f'Unsupported file type "{ext}". Allowed: {ALLOWED_EXTENSIONS}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Parse numeric params
    try:
        latitude  = float(request.data.get('latitude',   30.0))
        longitude = float(request.data.get('longitude',  31.0))
        zoom      = int(request.data.get('zoom_level',   19))
        panel_w   = int(request.data.get('panel_power_w', 580))
    except (TypeError, ValueError) as exc:
        return None, Response(
            {'error': f'Invalid parameter: {exc}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not (-90 <= latitude <= 90):
        return None, Response(
            {'error': f'Invalid latitude: {latitude}. Must be -90 to 90.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not (-180 <= longitude <= 180):
        return None, Response(
            {'error': f'Invalid longitude: {longitude}. Must be -180 to 180.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not (15 <= zoom <= 21):
        return None, Response(
            {'error': f'Invalid zoom_level: {zoom}. Must be 15-21.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    panel_spec = {**DEFAULT_PANEL, 'power_w': panel_w}

    return {
        'image_file': image_file,
        'latitude':   latitude,
        'longitude':  longitude,
        'zoom':       zoom,
        'panel_spec': panel_spec,
    }, None


def _save_upload_temp(image_file) -> str:
    """Save uploaded file to a temp path. Returns path."""
    import tempfile
    ext     = os.path.splitext(image_file.name)[1].lower() or '.jpg'
    tmp     = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    for chunk in image_file.chunks():
        tmp.write(chunk)
    tmp.close()
    return tmp.name


# ─────────────────────────────────────────────────────────────────────────────
# Main endpoint
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def analyze_roof_image(request: Request) -> Response:
    """
    POST /api/v1/ai/analyze-roof/

    Analyse a satellite or aerial roof image and return:
    - Roof boundary and area
    - Detected obstacles (AC units, water tanks, chimneys, …)
    - Usable roof area after obstacle exclusion
    - Optimal solar panel layout
    - Shading loss estimate
    - Annotated and layout images

    See module docstring for full request/response schema.
    """
    t_start      = time.time()
    analysis_id  = uuid.uuid4().hex[:12]
    tmp_path     = None

    # ── Validate request ──────────────────────────────────────────────────────
    params, err = _validate_request(request)
    if err:
        return err

    latitude   = params['latitude']
    longitude  = params['longitude']
    zoom       = params['zoom']
    panel_spec = params['panel_spec']

    try:
        # ── Save uploaded file temporarily ────────────────────────────────────
        tmp_path = _save_upload_temp(params['image_file'])

        # ── Load detector ─────────────────────────────────────────────────────
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        model_path = os.path.join(
            getattr(settings, 'BASE_DIR', '.'),
            'ai_engine', 'models', 'roof_detector_best.pt'
        )
        detector = EgyptianRoofDetector(
            model_path=model_path if os.path.exists(model_path) else None
        )

        # ── Run analysis ──────────────────────────────────────────────────────
        result = detector.detect_roof(
            image_path           = tmp_path,
            confidence_threshold = 0.5,
            latitude             = latitude,
            zoom                 = zoom,
        )

        # ── Override panel layout with user-specified panel power ─────────────
        panel_layout = detector.calculate_panel_layout(
            usable_area_m2 = result['usable_area_m2'],
            panel_specs    = panel_spec,
            orientation    = 'portrait',
        )

        # ── Generate layout image ─────────────────────────────────────────────
        from ai_engine.computer_vision.image_utils import ImageProcessor
        mpp           = result['metadata']['meters_per_pixel']
        panel_pos_px  = detector.get_panel_positions_px(
            roof_polygon = result['roof_polygon'],
            panel_layout = panel_layout,
            meters_per_pixel = mpp,
        )
        annotated_img = result['annotated_image']
        layout_img    = ImageProcessor.draw_panel_layout(
            image            = annotated_img.copy(),
            roof_polygon     = result['roof_polygon'],
            panel_positions  = panel_pos_px,
            panel_size_px    = (
                max(1, int(panel_spec['width_m']  / mpp)),
                max(1, int(panel_spec['height_m'] / mpp)),
            ),
            meters_per_pixel = mpp,
            panel_power_w    = panel_spec['power_w'],
        )

        # ── Save output images ────────────────────────────────────────────────
        ann_filename    = f'{analysis_id}_annotated.jpg'
        layout_filename = f'{analysis_id}_layout.jpg'
        ann_url         = _save_image_array(annotated_img, ann_filename)
        layout_url      = _save_image_array(layout_img,    layout_filename)

        # ── Serialise obstacles (remove numpy arrays for JSON) ────────────────
        serialised_obstacles = []
        for obs in result['obstacles']:
            serialised_obstacles.append({
                'class':      obs.get('class'),
                'area_m2':    obs.get('area_m2'),
                'location':   obs.get('location'),
                'confidence': obs.get('confidence'),
                'bbox':       [round(v, 1) for v in obs.get('bbox', [])],
            })

        processing_time = round(time.time() - t_start, 2)

        response_data = {
            'analysis_id':          analysis_id,
            'roof_area_m2':         result['roof_area_m2'],
            'usable_area_m2':       result['usable_area_m2'],
            'usable_percentage':    result['usable_percentage'],
            'obstacles':            serialised_obstacles,
            'panel_layout':         panel_layout,
            'shading_analysis':     result['shading_analysis'],
            'metadata':             result['metadata'],
            'annotated_image_url':  ann_url,
            'layout_image_url':     layout_url,
            'processing_time_sec':  processing_time,
        }

        logger.info(
            "Roof analysis %s: %.0f m² roof, %.0f m² usable, %d panels — %.2fs",
            analysis_id,
            result['roof_area_m2'],
            result['usable_area_m2'],
            panel_layout['max_panels'],
            processing_time,
        )

        return Response(response_data, status=status.HTTP_200_OK)

    except FileNotFoundError as exc:
        logger.error("Image file error in analysis %s: %s", analysis_id, exc)
        return Response(
            {'error': 'Could not process uploaded image file.', 'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as exc:
        logger.exception("Unexpected error in roof analysis %s", analysis_id)
        return Response(
            {'error': 'Internal analysis error.', 'detail': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        # Always clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Quick satellite-fetch endpoint (convenience)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def analyze_roof_by_coordinates(request: Request) -> Response:
    """
    POST /api/v1/ai/analyze-roof-by-coords/

    Fetch a satellite image from coordinates and run roof analysis.
    Requires GOOGLE_MAPS_API_KEY or MAPBOX_TOKEN environment variable.

    Request (JSON):
        {
            "latitude":    30.0444,
            "longitude":   31.2357,
            "zoom_level":  19,
            "source":      "google",
            "panel_power_w": 580
        }
    """
    latitude   = float(request.data.get('latitude',   30.0))
    longitude  = float(request.data.get('longitude',  31.0))
    zoom       = int(request.data.get('zoom_level',   19))
    # Default: 'esri' (ESRI World Imagery — free, no API key, real satellite).
    # Falls back to synthetic automatically if the network request fails.
    source     = request.data.get('source', 'esri')
    panel_w    = int(request.data.get('panel_power_w', 580))

    t_start     = time.time()
    analysis_id = uuid.uuid4().hex[:12]
    tmp_path    = None

    try:
        from ai_engine.computer_vision.image_utils import ImageProcessor
        import tempfile

        img = ImageProcessor.fetch_satellite_image(
            latitude=latitude, longitude=longitude,
            zoom=zoom, size=640, source=source,
        )

        # Save to temp file and reuse the main analysis pipeline
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            ImageProcessor.save_image(img, tmp.name)
            tmp_path = tmp.name

        # Delegate to detect_roof
        from ai_engine.computer_vision.roof_detector import EgyptianRoofDetector
        detector = EgyptianRoofDetector()
        result   = detector.detect_roof(
            image_path=tmp_path, latitude=latitude, zoom=zoom
        )

        mpp = result['metadata']['meters_per_pixel']
        panel_spec   = {**DEFAULT_PANEL, 'power_w': panel_w}
        panel_layout = detector.calculate_panel_layout(
            result['usable_area_m2'], panel_spec
        )

        ann_filename = f'{analysis_id}_annotated.jpg'
        ann_url      = _save_image_array(result['annotated_image'], ann_filename)

        return Response({
            'analysis_id':         analysis_id,
            'roof_area_m2':        result['roof_area_m2'],
            'usable_area_m2':      result['usable_area_m2'],
            'usable_percentage':   result['usable_percentage'],
            'obstacles':           result['obstacles'],
            'panel_layout':        panel_layout,
            'shading_analysis':    result['shading_analysis'],
            'metadata':            result['metadata'],
            'annotated_image_url': ann_url,
            'processing_time_sec': round(time.time() - t_start, 2),
        }, status=status.HTTP_200_OK)

    except Exception as exc:
        logger.exception("Coords-based analysis %s failed", analysis_id)
        return Response(
            {'error': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
