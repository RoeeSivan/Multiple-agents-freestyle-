"""The structured contracts that flow between agents.

The system no longer composes scenes from primitives. The single source of
truth is now a `BuildSpec`: a typed, high-level plan that the PlannerAgent
produces from free text and the BuilderAgent realizes inside a live Blender via
Hyper3D Rodin (text -> real mesh) + PolyHaven (materials/HDRI). Keeping one
typed plan is what lets the agents collaborate reliably.

The actual geometry lives in Blender, not here — `BuildSpec` describes *intent*
(what objects, how big, what mood), and the builder turns that into meshes.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Part(BaseModel):
    """One sub-component of an object: rough size + how it attaches.

    Gives the builder a stable structural contract so it doesn't re-guess an
    object's whole composition on every refine pass.
    """

    name: str = Field(description="short label, e.g. 'seat', 'leg', 'backrest'")
    shape_hint: str = Field(
        default="",
        description="primitive/form to start from, e.g. 'thin tapered cylinder', "
        "'rounded box', 'sphere'",
    )
    approx_dims_m: list[float] = Field(
        default_factory=list,
        description="rough [x, y, z] size in meters; leave [] if unsure",
    )
    anchor: str = Field(
        default="",
        description="how/where this part attaches to the rest, e.g. 'on top of the "
        "seat', '4x mirrored under the seat corners', 'centered, base on ground'",
    )


class ObjectBrief(BaseModel):
    """One object to generate, described richly enough for a text->3D model."""

    name: str = Field(description="snake_case scene identifier, e.g. 'sports_car'")
    description: str = Field(
        description="a vivid, self-contained English prompt for a text-to-3D "
        "generator, e.g. 'a sleek red two-door sports car with black wheels'. "
        "Describe ONE object; no scene layout or other objects here."
    )
    approx_size_m: float = Field(
        default=1.0,
        description="target size of the object's LONGEST dimension in meters. "
        "Generated meshes are normalized, so this drives rescaling.",
    )
    parts: list[Part] = Field(
        default_factory=list,
        description="structural breakdown into sub-components with rough dims and "
        "how they attach; empty means the builder composes it freely",
    )
    proportions: str = Field(
        default="",
        description="key real-world proportions/ratios, e.g. 'seat at 45cm, back "
        "twice the seat height', 'wheels ~1/4 of body length'",
    )
    symmetry: str = Field(
        default="",
        description="symmetry to enforce, e.g. 'bilateral left-right', 'radial x4'; "
        "empty if none",
    )
    material_hint: str = Field(
        default="",
        description="optional surface note, e.g. 'glossy car paint', 'rough oak "
        "wood', 'brushed metal'; guides material/PolyHaven tweaks",
    )
    position_hint: str = Field(
        default="",
        description="optional placement relative to the scene/other objects, "
        "e.g. 'centered on the ground', 'to the left of the car'",
    )


class BuildSpec(BaseModel):
    """A complete, typed build plan — the contract between planner and builder."""

    title: str = Field(description="short human label for the scene, e.g. 'red sports car'")
    objects: list[ObjectBrief] = Field(default_factory=list)
    environment: str = Field(
        default="studio neutral",
        description="lighting/world mood, e.g. 'outdoor sunny', 'studio neutral', "
        "'nighttime city'; guides HDRI/world choice",
    )
    camera_hint: str = Field(
        default="three-quarter front view",
        description="how to frame the shot, e.g. 'three-quarter front view'",
    )


class Clarification(BaseModel):
    """InfoAgent verdict: is the request too ambiguous to build well?"""

    needs_info: bool = Field(description="True only if a key detail is genuinely missing")
    question: str = Field(
        default="",
        description="one short, friendly SMS question gathering the MOST important "
        "missing detail(s); empty when needs_info is False",
    )


class BuildReport(BaseModel):
    """BuilderAgent summary of what it actually built in Blender."""

    objects_built: list[str] = Field(default_factory=list, description="scene object names")
    notes: str = Field(default="", description="brief notes on what was done / any issues")


class Critique(BaseModel):
    """VisionCritic verdict on a rendered image vs. the user's request."""

    matches_request: bool = Field(description="True if the render satisfies the request")
    issues: list[str] = Field(default_factory=list, description="what is wrong, if anything")
    patch_instructions: str = Field(
        default="",
        description="concrete natural-language fixes for the BuilderAgent to apply; "
        "empty if matches",
    )


class ObjectAudit(BaseModel):
    """Deterministic measurements of one built object (no LLM)."""

    name: str
    dims_m: list[float] = Field(default_factory=list, description="world bbox [x,y,z] in meters")
    longest_dim_m: float = 0.0
    lowest_z_m: float = 0.0
    island_count: int = Field(default=0, description="connected mesh components")
    scatter_groups: int = Field(
        default=1,
        description="islands grouped by bbox overlap; >1 means parts float apart",
    )
    has_geometry: bool = True


class GeometryAudit(BaseModel):
    """Programmatic geometry check fed back to the builder alongside the critic.

    Catches mis-sized / scattered / missing / empty geometry with exact numbers,
    without spending a vision pass. `problems` are written as concrete builder
    instructions; `ok` is True when none were found.
    """

    ok: bool = True
    objects: list[ObjectAudit] = Field(default_factory=list)
    problems: list[str] = Field(default_factory=list)
