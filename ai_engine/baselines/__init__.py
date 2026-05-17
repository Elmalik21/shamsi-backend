"""
ai_engine/baselines/__init__.py
Shamsi Smart — Physics/industry baseline models.
"""
from .pvwatts_baseline import PVWattsBaseline
from .physics_baseline import SimplifiedPhysicsModel

__all__ = ['PVWattsBaseline', 'SimplifiedPhysicsModel']
