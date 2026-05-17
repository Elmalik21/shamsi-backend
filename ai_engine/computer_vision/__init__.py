"""
ai_engine/computer_vision/__init__.py
======================================
Shamsi Smart — Computer Vision module.

Provides automated roof analysis for Egyptian buildings using
YOLOv8 instance segmentation. Detects roof boundaries, obstacles
(AC units, water tanks, chimneys, trees) and calculates usable
area for solar panel installation.

Quick start
-----------
    from ai_engine.computer_vision import EgyptianRoofDetector

    detector = EgyptianRoofDetector()          # uses pretrained YOLOv8n-seg
    result   = detector.detect_roof('roof.jpg')
    print(result['usable_area_m2'])

Author: Shamsi Smart AI Team
"""
from .roof_detector import EgyptianRoofDetector
from .image_utils import ImageProcessor

__all__ = ['EgyptianRoofDetector', 'ImageProcessor']
