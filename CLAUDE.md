# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Game

Open `dogstrike.html` directly in a browser — no build step, no server required. Phaser 3 is loaded from CDN (`phaser-arcade-physics.min.js`). For local asset loading to work correctly in some browsers, serve it via a local HTTP server:

```bash
python3 -m http.server 8080
# then open http://localhost:8080/dogstrike.html
```

## Architecture

The entire game lives in a single file: `dogstrike.html`. All game logic is in the `<script>` block. There is no bundler, no npm, no build pipeline.

**Phaser 3 Scene flow:**

```
BootScene → TitleScene → HeroSelectScene → PlayScene
                  ↑              ↑
                  └── StoryScene ┘  (triggered at waves 4 and 7)
```

- **BootScene** — preloads image assets; falls back to generated colored rectangles for any missing file (graceful degradation pattern used everywhere)
- **TitleScene** — static title card, press SPACE to start
- **HeroSelectScene** — pick hero; heroes unlock at wave 4 (Shepherd) and wave 7 (Dachshund); receives `{ wave, score }` so progress persists across waves
- **StoryScene** — graphic novel panels between level arcs; `beatIndex` 0 = Factory arc end, 1 = City Hall arc beginning
- **PlayScene** — main gameplay; receives `{ heroId, wave, score, level }` where `level` is `'factory'` or `'cityhall'`

**Global constants and shared state:**

- `W = 800`, `H = 600`, `GROUND_Y = 520` — canvas dimensions used throughout
- `C` — color palette object; hex values (e.g. `C.gold`) for Phaser graphics calls, string variants (e.g. `C.goldS`) for text fill
- `HEROES` — static config object for the three heroes (`saint`, `shepherd`, `dachshund`); defines speed, strike range, cooldowns, and special power metadata

**Enemy types and logic (PlayScene.spawnNext):**

| Key | Type | HP | Notes |
|-----|------|----|-------|
| `enemy_enforcer` | Standard mech | 1 | Base enemy |
| `enemy_heavy` | Heavy mech | 1 | Slower, larger |
| `enemy_admin` | Admin mech | 2 | Always shielded; appears in cityhall level |
| `boss_chronos` | Boss | 3 | Spawns last on every 3rd wave |

Shielded robots require either the Dachshund's special or multiple hits; they display a blue tint.

**Player animation system:**

Uses a tween-based state machine (`animState`: `idle` / `walk` / `jump`). Critically, tweens operate on `scaleX`/`scaleY` relative to `player._bsx` / `player._bsy` (the base scale set at spawn). Always multiply from these base values, not from current scale, to avoid compound drift.

## Asset Layout

```
assets/
  dogs/       — hero sprites (saint, shepherd, dachshund + alternates)
  bads/       — enemy sprites (enforcer, heavy, admin, boss)
  background/ — level backgrounds (bg_factory_a–d, bg_cityhall_a–c, plus one original)
images/       — Gemini-generated concept art (not used in-game)
```

Background keys are rotated per wave in `PlayScene.init()` to vary visual feel without adding scenes.

## Key Design Patterns

- **Graceful asset fallback**: BootScene generates a solid-color placeholder texture for any image that fails to load. New assets should follow the same pattern in the `assetDefs` array (add `key`, `path`, `w`, `h`, `color`).
- **Procedural Art Deco visuals**: Backgrounds, UI chrome, and special-power effects are drawn with Phaser Graphics calls, not external images. The recurring "all-seeing eye" motif appears in `drawDecoEyeStatic` (static) and `drawDecoEye` (animated, destroys itself after tweening out).
- **Scene data passing**: All persistent state (wave number, score, hero selection) is passed explicitly via `scene.start(key, data)` — there is no global state or registry used between scenes.

