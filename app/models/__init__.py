"""Shared Pydantic schemas (the structured contract between agents + renderer)."""
from app.models.scene import Critique, Obj, SceneSpec

__all__ = ["Obj", "SceneSpec", "Critique"]
