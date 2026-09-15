# Design System: LexGentium Hearing

Version **0.8.0**. Adapted from Linear’s dark-first workbench density and Stripe’s institutional restraint on marketing pages. Not a pixel clone. Do not use Linear’s brand indigo (`#5e6ad2`) or proprietary fonts (CursorGothic, Berkeley Mono).

## 1. Visual Theme & Atmosphere

LexGentium is an international commercial arbitration hearing workbench. Product surfaces are dark-native: information emerges from near-black through luminance, not color. Marketing pages (home, about, docs) stay quiet—wide whitespace, one accent, no grid wallpaper, no glow logos.

Ink dark is the default medium for 开庭 / 复盘 / 系统 / 观庭（`/hearing-3d`）. Light mode is a first-class alternate. Switch palettes with `html[data-scheme="ink"|"parchment"|"seal"]`; `.dark` still flips each scheme. Do not add a fourth hue family.

**Key characteristics**

- Default canvas `#08090a` (ink dark), panel `#0f1011`, elevated `#191a1b`
- Structure via hairline borders (`rgba(255,255,255,0.06-0.10)` dark; `#e4e5e7` / paper edges light)
- Geist Sans (npm `geist`, bundled files) + PingFang SC / Microsoft YaHei. Do not fetch Google Fonts at build time.
- Product radius `6px`; cards have no drop shadow by default
- Two shells: Marketing (generous) and Workbench (dense, no large footer on live sessions)

## 2. Color Palette & Roles

Tokens live in `app/globals.css`. Shared status colors do not change with scheme: Success `#27a644`, Warning `#c9a227`, Danger `#d4534c`. Overlay `rgba(0,0,0,0.72)`.

### Ink `data-scheme="ink"` (default, navy)

| Token | Hex | Role |
|-------|-----|------|
| Canvas | `#08090a` | Dark page (`--background`) |
| Brand | `#4e5bb8` | Dark primary / light ring |
| Interactive | `#6b78e0` | Dark ring, focus, hover |
| Light canvas | `#f7f8f8` | Light page |
| Brand light | `#3d4a9c` | Light primary |

### Parchment `data-scheme="parchment"` (paper + navy)

| Token | Hex | Role |
|-------|-----|------|
| Paper | `#f4efe6` | Light page (`--background`) |
| Brand | `#3d4a9c` | Light primary |
| Interactive | `#4e5bb8` | Light ring; dark primary |
| Dusk canvas | `#1c1914` | Dark page |
| Ink text | `#1a1612` | Light foreground |

### Seal `data-scheme="seal"` (warm ink + vermillion)

| Token | Hex | Role |
|-------|-----|------|
| Warm ink | `#161210` | Dark page (`--background`) |
| Ivory | `#f6f1ea` | Light page |
| Vermillion | `#9b2d2a` | Light primary |
| Interactive | `#c45c4a` | Dark primary / both rings |
| Dark panel | `#241e1b` | Dark cards, popovers |

### Role accents (transcript rail only — 2px, never full-bubble fills)

| Role ID | Token | Use |
|---------|-------|-----|
| Client | `--chart-2` | Party input |
| Lawyer | `--chart-1` | Counsel |
| Judge | `--chart-5` | Tribunal |
| Plaintiff | `--chart-4` | Applicant |
| Defendant | `--chart-3` | Respondent |
| Final | `--chart-2` | Award / filing |

Do not paint message bodies with Tailwind palette colors (`bg-blue-50`, `from-purple-500`, etc.).

## 3. Typography Rules

### Families

- **UI / display**: Geist Sans, fallbacks `PingFang SC, Microsoft YaHei, system-ui, sans-serif`
- **Mono**: `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`

### Hierarchy

| Role | Size | Weight | Tracking | Line height |
|------|------|--------|----------|-------------|
| Display (marketing hero) | 48–64px | 500 | -0.045em | 1.05 |
| Page title (workbench) | 22–24px | 500 | -0.02em | 1.2 |
| Section | 16–18px | 500 | -0.01em | 1.3 |
| Body | 14px | 400 | 0 | 1.55 |
| UI / nav | 13px | 500 | 0 | 1.3 |
| Meta / caption | 12px | 450–500 | 0.01em | 1.4 |
| Mono | 12px | 400 | 0 | 1.5 |

Headlines use size and tracking, not weight 700. Do not bold entire paragraphs.

## 4. Component Stylings

### Buttons

- Primary: brand fill, white text, height 32px workbench / 40px marketing, radius 6px, no gradient, no shine sweep
- Outline: transparent + hairline border, hover `elevated`
- Ghost: no border, hover `rgba(255,255,255,0.05)` / light `#f3f4f5`
- Destructive: danger text or fill; never rainbow

### Cards

- Background `elevated` (dark) or white (light)
- `1px` hairline, radius 6px, **no** `shadow-2xl` / `border-2`
- Marketing feature cards may use a single soft shadow: `0 12px 40px rgba(0,0,0,0.08)`

### Inputs

- Height 32–36px, hairline border, transparent or panel fill
- Focus: 1px brand ring, no 3px glow stack

### Navigation

Two bars share the same tokens. Do not introduce Linear indigo (`#5e6ad2`), CursorGothic, Berkeley Mono, or Inter-from-Google.

**Marketing** (`MarketingShell`: `/` `/about` `/docs`)

- Height 56px, content max ~1120px, hairline bottom, `backdrop-blur` at low opacity
- Stripe-style few links: logo → `/`; 文档; 关于
- Right: primary CTA「开庭」→ `/conversation` (height 40px marketing button) + theme
- No workbench groups, no session chip, no health dot

**Workbench** (`WorkbenchShell`)

- Height 48px, full width (`max-w-none`), hairline `border-subtle`, `backdrop-blur`
- Four group triggers: 开庭 / 观庭 / 复盘 / 系统. UI/nav type: 13px, weight 500. Active group = `secondary` pill
- Each group opens a dropdown (max 5 items). Item = title + one-line secondary description
- Do not flatten 博弈 / 评测 / 全案 / 调解 as fifth top-level links. 策略推演 and 对照本场 live under 复盘. `game_id` / `report_id` show on the session chip
- Right cluster: session chip, health dot, theme
- Optional command bar: `Cmd+K` / `Ctrl+K` lists the same `NAV_ACTIONS` as the four dropdowns. Display entry only; not a second feature set
- Logo: 28px square, solid brand fill, Scale icon - **no blur glow**

**Dropdown**

- Surface: `elevated` + 1px hairline + radius 6px
- No Linear stacked shadows (`shadow-2xl` / multi-layer glow)
- Item hover: hover surface. Disabled items stay in place, no pointer

**Session chip**

- Pill: `9999px` or product radius 6px. Mono tabular short `session_id` (8 chars)
- With session: stage copy from `STAGE_LABELS` + `策略已开` (has `links.game_id`) and/or `未对照` (no `links.report_id`)
- No last session:「未开场」
- Backend unreachable (`GET /api/health` fail):「未连接」. Do not treat a list 500 as「暂无会话」
- Persist last `session_id` in `sessionStorage` (`lib/session/last-session.ts`). Hydrate chip via `GET /api/conversation/{id}` for `links` / stage. Write after 开庭 / 观庭 succeed
- Chip menu: 本场听证 / 观庭 / 对照 / 策略推演

**Health dot**

- 8px circle. `success` when `GET /api/health` is ok; `danger` when it is not

### Transcript

- Shared surface; 2px left rail in role token
- Meta line: role label + tertiary text
- Streaming line uses muted italic, same rail

### HUD (3D chrome only)

- Panel token + hairline + light blur
- Same type scale as workbench captions
- Do not restyle the WebGL scene

## 5. Layout Principles

- Base unit 4px; workbench padding 12–16px; marketing sections 64–96px vertical
- Workbench content is full-bleed inside the shell (no `max-w-4xl` card stacks on hearing)
- Marketing max width ~1120px, centered
- Session and 3D live pages: no marketing footer
- Spacing between workbench rows: 0; separators are hairlines

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| 0 | Flat canvas | Page |
| 1 | Hairline only | Cards, tables, composer |
| 2 | Hairline + slight lift (marketing only) | Home product preview |
| Overlay | Dark 72% | Dialogs |

No inset neon bars, no colored top stripes on cards.

## 7. Do's and Don'ts

**Do**

- Change color by editing CSS variables first
- Use `SCENARIO_LABELS` / `STAGE_LABELS` / `ROLE_LABELS` for product copy
- Keep engine IDs (`Judge`, `Plaintiff`, `CD`) in code, Chinese labels in UI
- Default new hearings to `CI` + `foreign_commercial_001`

**Don't**

- Logo gradients, glow blurs, grid background wallpaper
- Rainbow scenario cards or `Sparkles` decoration
- Button shine sweeps (`via-white/20 translate-x`)
- Full-color chat bubbles per role
- One-off Tailwind hues (`from-blue-500 to-cyan-500`)
- Copy that says 模拟法庭 / 起诉状 / 法庭判决 / 多智能体 as the product name
- Imply a full J1Bench suite on 复盘
- Flatten 博弈 / 评测 / 全案 / 调解 across the workbench top bar
- Put 验收清单, 性转皮肤, or「绑定博弈」on the live 观庭 footer
- Surface LexEval / J1 / 极化 / 责任链 in nav, command bar, or 复盘 home
- Use Linear brand indigo, CursorGothic, Berkeley Mono, or Inter-from-Google

## 8. Responsive Behavior

| Breakpoint | Behavior |
|------------|----------|
| <640px | Workbench: four groups collapse into one「菜单」dropdown; session chip keeps short ID; composer full width |
| 640–1024 | Group trigger labels visible; tables scroll horizontally |
| >1024 | Hearing: top bar + filling transcript + pinned composer; four groups + chip + health + theme |

Touch targets stay ≥32px on workbench, ≥40px on marketing CTAs.

## 9. Agent Prompt Guide

When editing UI:

1. Read this file and `app/globals.css` before adding a color.
2. Official product language: **国际商事仲裁听证仿真**. Flows: 开庭 → 观庭 → 复盘.
3. Scenarios: CD 申请准备, DD 答辩准备, CI 仲裁听证.
4. Roles on screen: 首席仲裁员 / 申请人 / 被申请人 — never paint them as 法官/原告/被告 in new copy.
5. Shells: `MarketingShell` for `/` `/about` `/docs`; `WorkbenchShell` for product pages; `footer={false}` on live hearing and 3D session.
6. 3D: restyle HUD and lobby chrome only. Do not edit `CourtScene`, avatars, or cast JSON for visual polish.

Example: "Hearing transcript row: elevated surface, 2px left rail from `--chart-*`, 13px meta, 14px body. No colored bubble fill."

Example: "Workbench top bar: height 48px, full width, hairline `border-subtle`, backdrop-blur. Triggers 开庭 / 观庭 / 复盘 / 系统 at 13px/500. Active group is a `secondary` pill. Each dropdown is elevated + hairline + radius 6px, max 5 rows of title + one-line description. Same `NAV_ACTIONS` feed Cmd+K. Right: session chip, 8px health dot (`success`/`danger` from `/api/health`), theme. No fifth top-level 博弈 or 评测 link."

Example: "Session chip: pill (`rounded-full` or 6px), mono 8-char session id, stage from `STAGE_LABELS`, then `策略已开` if `links.game_id` else omit, `未对照` if no `links.report_id`. Empty: 未开场. Health down: 未连接 (do not invent a session list). Menu: 本场听证, 观庭, 对照本场, 策略推演 - all the same `session_id`."

## 10. Taste-Skill (redesign-preserve)

Anti-slop rules from taste-skill. Marketing uses v2 landing guidance. Workbench is a dense product UI: do not apply landing-page variance, GSAP, or three-column feature towers.

### Dials

| Surface | VARIANCE | MOTION | DENSITY |
|---------|----------|--------|---------|
| Marketing (`/`, `/about`, `/docs`) | 4 | 3 | 3 |
| Workbench (开庭 / 复盘 / 系统 / 观庭) | 2 | 2 | 8 |

Motion is feedback only: hover, `:active` scale 0.98, focus. Honor `prefers-reduced-motion`. No scroll hijack, no unmotivated animation.

### Banned

- Three equal marketing cards or 3xN identical feature tiles
- Em-dash (`—`) in UI copy; use `-`
- Inter-from-Google at build time
- Picsum / stock courtroom photos
- Rewriting product tokens or hearing layout for "taste"
