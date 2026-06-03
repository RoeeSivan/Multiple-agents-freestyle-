"""PydanticAI agents. Each module owns one agent + a typed async runner.

Three agents collaborate: RouterAgent triages the message, IntentAgent turns
text into a typed SceneSpec, VisionCritic inspects the render and proposes fixes.
"""
from app.agents.critic import critique_render, critic_agent
from app.agents.intent import build_spec, intent_agent
from app.agents.router import route_message, router_agent

__all__ = [
    "router_agent",
    "route_message",
    "intent_agent",
    "build_spec",
    "critic_agent",
    "critique_render",
]
