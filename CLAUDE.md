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
- **HeroSelectScene** — pick hero; heroes unlock at wave 4 (Shepherd) and wave 7 (Dachshund); receives `{ wave, score, upgrades }` so progress persists across waves
- **StoryScene** — graphic novel panels between level arcs; `beatIndex` 0 = Factory arc end, 1 = City Hall arc beginning, 2 = Chronos Prime victory, 3+ = HQ arc beats. Each beat picks its own background and renders panel art via `drawPanelArt(beatIndex)`; pre-rendered images can override procedural art via the `PANEL_IMGS[beatIndex + '_' + panelIndex]` lookup
- **PlayScene** — main gameplay; receives `{ heroId, wave, score, level, upgrades }` where `level` is `'factory'` or `'cityhall'`

**Persistence (localStorage):**

- `dogstrike_mute` — audio mute flag
- `HS_KEY` — high score (`getHS` / `saveHS`)
- `PROGRESS_KEY` — JSON blob of `{ wave, score, upgrades, ... }` written between scene transitions so the player resumes mid-run on reload
- `applyUpgradeMods(hero, upgrades)` mutates a clone of the `HEROES` config (e.g., `longer_strike` adds 20 to `strikeRange`, `quick_special` shaves 15% off `powerCD`). Always pass the cloned hero object into PlayScene — never mutate `HEROES` directly.

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
  story/      — pre-rendered story panel images (story_factory, story_cityhall, story_hq, story_march, story_solidarity, story_fight, story_boss, story_victory)
images/       — Gemini-generated concept art (not used in-game)
tools/        — Python utilities to generate/assemble sprite frames; outputs land in tools/generated/ and assets/dogs/
```

Background keys are rotated per wave in `PlayScene.init()` to vary visual feel without adding scenes.

Touch input: TitleScene detects mobile (`this.sys.game.device.input.touch`) and requests fullscreen on tap. PlayScene exposes a touch-strike control; if you add new input paths, wire them through the same handlers as keyboard so both stay in sync.

## Key Design Patterns

- **Graceful asset fallback**: BootScene generates a solid-color placeholder texture for any image that fails to load. New assets should follow the same pattern in the `assetDefs` array (add `key`, `path`, `w`, `h`, `color`).
- **Procedural Art Deco visuals**: Backgrounds, UI chrome, and special-power effects are drawn with Phaser Graphics calls, not external images. The recurring "all-seeing eye" motif appears in `drawDecoEyeStatic` (static) and `drawDecoEye` (animated, destroys itself after tweening out).
- **Scene data passing**: All persistent state (wave number, score, hero selection) is passed explicitly via `scene.start(key, data)` — there is no global state or registry used between scenes.

## Debugging

After implementing any fix, verify it works by reading the relevant code path end-to-end before declaring it done. If a fix involves patching or monkey-patching a library (e.g. Phaser internals), confirm the patch runs before the affected code and is not bypassed by cached internal references.

Always check initialization order when adding new game systems — ensure dependencies (player, robots, physics groups, etc.) are created before any system that references them.

## Deployment

`deploy.sh` deploys the CloudFormation stack defined in `infra.yaml` (S3 + CloudFront + ACM + Route53 in `us-east-1`), syncs `assets/` with a 1-year immutable cache, uploads `dogstrike.html` with a 5-minute cache, and invalidates CloudFront. Stack name: `dogsonstrike-game`. The site is `https://dogsonstrike.com`.

Before running, verify AWS credentials are active:

```bash
aws sts get-caller-identity
```

If expired, re-authenticate first. The deploy script will fail silently-ish otherwise.

`us-east-1` is required because CloudFront only accepts ACM certs from that region — do not change it.
