# ICHIBAN UI Theme v20.5.4H

## Purpose

This is a UI-only presentation update for the Streamlit pages. It is intended to make ICHIBAN feel calmer, more professional, and more broadly appealing to agents, sellers, and general users.

## Scope

Changed:
- Adds `.streamlit/config.toml` with a warmer theme.
- Adds `app/ui_theme.py` with shared CSS helpers.
- Applies the shared theme on the main app page and Module pages 1–5.

Not changed:
- No comp math.
- No valuation engine logic.
- No report prompt logic.
- No Tarzan/BBC scope changes.
- No parser behavior.
- No document export behavior.

## Palette

- Deep navy: `#1F3A5F` — trust, stability, professional anchor.
- Soft teal: `#2F6F73` — modern primary action color.
- Warm cream: `#F7F4EF` — approachable page background.
- White cards: `#FFFFFF` — clean reading surfaces.
- Muted slate: `#667085` — secondary text.
- Quiet gold: `#C89B3C` — restrained premium accent.

## Design rule

The app should feel professional and inviting, not technical or intimidating. The visual design should support confidence before the user reaches the valuation/report logic.
