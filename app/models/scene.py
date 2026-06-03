"""The structured 3D-scene contract.

`SceneSpec` is the single source of truth that flows through the whole system:
IntentAgent produces/edits it, the renderer turns it into a Three.js scene, and
the VisionCritic reasons about the rendered result. Keeping one typed schema is
what lets the agents collaborate reliably.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Shape = Literal["box", "sphere", "cylinder", "cone", "torus", "plane"]
Material = Literal["standard", "metal", "glass", "emissive"]

Vec3 = tuple[float, float, float]


class Obj(BaseModel):
    """One primitive mesh in the scene. Units are meters (1 unit = 1 m)."""

    name: str = Field(description="snake_case identifier, e.g. 'car_body'")
    shape: Shape = "box"
    position: Vec3 = (0.0, 0.0, 0.0)
    rotation: Vec3 = (0.0, 0.0, 0.0)  # radians, XYZ
    scale: Vec3 = (1.0, 1.0, 1.0)
    color: str = Field(default="#cccccc", description="hex color like '#e23b3b'")
    material: Material = "standard"


class SceneSpec(BaseModel):
    """A complete renderable scene."""

    objects: list[Obj] = Field(default_factory=list)
    background: str = Field(default="#202b38", description="hex background color")
    ground: bool = Field(default=True, description="add a shadow-catching ground plane")
    sun_dir: Vec3 = Field(default=(-1.0, -1.0, -0.5), description="directional light direction")


class Critique(BaseModel):
    """VisionCritic verdict on a rendered image vs. the user's request."""

    matches_request: bool = Field(description="True if the render satisfies the request")
    issues: list[str] = Field(default_factory=list, description="what is wrong, if anything")
    patch_instructions: str = Field(
        default="",
        description="concrete natural-language edits for IntentAgent to apply; empty if matches",
    )
