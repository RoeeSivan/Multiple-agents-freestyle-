"""PydanticAI agents. Each module owns one agent + a typed async runner.

The multi-agent cast:
- RouterAgent  (router.py)   triages each SMS: new / edit / chat.
- InfoAgent    (info.py)     asks one clarifying question when a request is too vague.
- PlannerAgent (intent.py)   turns text into a typed BuildSpec.
- ViewPlanner  (photoplan.py) decides per object whether to ask the user for photos.
- BuilderAgent (builder.py)  builds the scene in a live Blender via the Blender MCP
                             toolset + a Hyper3D Rodin text->mesh tool.
- VisionCritic (critic.py)   inspects the render and proposes concrete fixes.
"""
from app.agents.builder import build_scene, builder_agent
from app.agents.critic import critic_agent, critique_render
from app.agents.info import assess as info_assess
from app.agents.info import info_agent
from app.agents.intent import build_spec, intent_agent, planner_agent
from app.agents.photoplan import photoplan_agent, plan_views
from app.agents.reference import get_reference, reference_agent, reference_from_photos
from app.agents.router import route_message, router_agent

__all__ = [
    "router_agent",
    "route_message",
    "info_agent",
    "info_assess",
    "planner_agent",
    "intent_agent",
    "build_spec",
    "photoplan_agent",
    "plan_views",
    "builder_agent",
    "build_scene",
    "critic_agent",
    "critique_render",
    "reference_agent",
    "get_reference",
    "reference_from_photos",
]
