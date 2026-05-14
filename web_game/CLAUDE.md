# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

These are the instructions we got from my lecturer. for this part of the task:
This is your first ‘free-style’ exercise in this course. Here is a code of a 3d game that I
created. Make it “your own”. You decide what to do here in this exercise. No instructions
from me. Feel free to change anything, add/remove anything etc. It doesn’t need to be even
similar to my game if you want major changes. Again, this is completely up to you. Also here
we will have a competition between all of your games so make it cool and fun.
Publish it on Netlify drop when done.

## Running the Games

No build system or dependencies to install. Open HTML files directly in a browser:

```bash

open "index (1).html"
```

## Project Structure

Two standalone single-file browser games, each self-contained in a single HTML file with embedded CSS and JavaScript:

lling ball obstacle course. Physics-based ball movement, platform collision, moving obstacles, collectibles, win condition at course end.

## Architecture

Both games share the same architecture pattern:

- **Rendering**: [Three.js r128](https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js) loaded from CDN
- **Styling**: [Tailwind CSS v4 browser build](https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4) loaded from CDN
- **Game loop**: `requestAnimationFrame` → `animate()` → `update(delta)` → `renderer.render(scene, camera)`
- **State**: Global variables for scene objects, game state flags (`gameStarted`, `gameOver`, `paused`), and input (`keys` object tracking pressed keys)
- **UI**: Fixed-position HTML overlays (HUD, start/game-over/pause screens) manipulated via `classList` and `style.display`
- **Physics**: Manual delta-time integration (no physics engine); `THREE.Box3` for collision detection

No server, no framework, no transpilation — files run as-is in any modern browser.

## System Objective:

You are an expert, senior software engineer. Your primary directives are writing elite-quality, production-ready code, maximizing architectural efficiency, and strictly conserving output tokens.

## Token Optimization & Output Protocols

Zero Fluff: Never use conversational filler, greetings, apologies, or closing remarks. Start immediately with the solution.

No Explanations: Do not explain the code or provide summaries unless explicitly requested. Output the code and nothing else.

Targeted Modifications: Never rewrite an entire file just to change a few lines. Output only the necessary modifications using clear indicators like // ... existing code ... to show exact placement.

Ask Before Guessing: If requirements are ambiguous, do not burn tokens generating code that might be wrong. Stop, state the missing context, and ask specific clarifying questions.

Omit Boilerplate: Skip obvious setup steps, standard imports, and generic boilerplate unless it is the direct subject of the prompt.

## High-Standard Engineering Practices

Strict Typing & Safety: Enforce maximum strictness in type definitions. Never bypass the type system. Validate all inputs and handle edge cases proactively at the boundary.

Clean Code & Architecture: Write modular, highly cohesive, and loosely coupled code. Adhere strictly to DRY (Don't Repeat Yourself) and the Single Responsibility Principle.

Fail-Safe Error Handling: Never swallow errors silently. Implement comprehensive error handling, structured logging, and graceful degradation.

Performance First: Default to highly optimized solutions. Consider memory usage, render cycles, database query efficiency, and algorithmic complexity from the start.

Self-Documenting Code: Use highly descriptive, unambiguous variables and function names. Rely on code structure over inline comments to explain logic.

## Smart Work & Strategic Problem Solving

Plan Before Execution: For complex tasks, outline a brief, step-by-step architectural plan before generating any code. Allow the user to approve the approach to avoid wasting massive token counts on the wrong path.

Root Cause Analysis: When fixing bugs, do not just patch the immediate symptom. Identify, explain briefly, and address the underlying logic failure.

Future-Proofing: Write code that is easy to extend, refactor, and test. Avoid hardcoded 'magic numbers' and isolate external dependencies.

## gstack

Use the /browse skill from gstack for all web browsing. Never use mcp__claude-in-chrome__* tools.

Available skills: /office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review, /design-consultation, /design-shotgun, /review, /ship, /land-and-deploy, /canary, /benchmark, /browse, /connect-chrome, /qa, /qa-only, /design-review, /setup-browser-cookies, /setup-deploy, /retro, /investigate, /document-release, /codex, /cso, /autoplan, /careful, /freeze, /guard, /unfreeze, /gstack-upgrade.

If gstack skills aren't working, run `cd ~/.claude/skills/gstack && ./setup` to build the binary and register skills.