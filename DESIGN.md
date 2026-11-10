---
name: RosterFit
description: Lineup, draft and roster-move analysis for NBA front offices, drawn in the selected team's own uniform.
colors:
  ink: "#121212"
  ink-2: "#45433f"
  muted: "#5f5c56"
  ground: "#f5f4ef"
  surface: "#ffffff"
  surface-sunk: "#eceae4"
  rule: "#cfcbc1"
  rule-soft: "#e3e0d8"
  hot: "#b03a28"
  hot-tint: "#f3dcd6"
  cold: "#285f9a"
  cold-tint: "#d9e4f0"
  slate: "#3e5770"
  paint: "#8c6d1f"
  ok: "#2a7a5e"
  warn: "#8a5f00"
  warn-tint: "#f4ead2"
  err: "#b23a2e"
  focus: "#1d4e89"
typography:
  numeral:
    fontFamily: "Graduate, Archivo, serif"
    fontSize: "30px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  figure:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: 1.15
    fontFeature: "tnum"
  body:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  body-sm:
    fontFamily: "Archivo, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Archivo Narrow, Archivo, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.05em"
rounded:
  sm: "2px"
  md: "3px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-5: "24px"
  s-6: "32px"
  s-7: "48px"
  s-8: "64px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "#2b2b2b"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.surface-sunk}"
  input-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 12px"
    height: "40px"
  segment-on:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    padding: "8px 12px"
  table-header:
    backgroundColor: "{colors.surface-sunk}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    padding: "8px 10px"
  tooltip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-tab-active:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: RosterFit

## Overview

**Creative North Star: "Tackle Twill"**

RosterFit is drawn in the loaded team's uniform. Every player on screen wears his real jersey number as layered tackle twill in that team's colorway, so a five-man unit reads the way a coach reads his floor: numbers at their spots, not anonymous name rows. The page itself is the home-white jersey: a warm off-white ground with a faint dot mesh, a shell bar in the team's primary with a two-row running stitch in its secondary along its hem.

Everything else stays quiet so the numbers can talk. The analysis surfaces are flat white panels with hairline rules, tabular figures and a box-score stat line. Data has its own palette that never borrows team color, so a Lakers gold and a Warriors gold never get confused with "above average". Density is that of a daily tool: tables that fit their column, a sticky half court beside them, no hero, no marketing rhythm. Motion only marks a state change: a swapped player glides to his spot and has his numeral re-stitched.

**Key Characteristics:**
- Real jersey numbers as three-layer SVG twill (fill, inner outline in the primary, outer outline in the secondary, a dashed sewing line between them at court and card sizes).
- Team colorway is runtime and scoped to identity: shell bar, wordmark, numerals. Never data.
- Home-white mesh ground (#f5f4ef plus a 3.5% dot weave), white surfaces, 3px corners.
- Box-score typography: Archivo for UI, Archivo Narrow uppercase for labels, Graduate block for numerals and the wordmark, tabular figures everywhere.
- Every headline number has an explanation one click away (a help button or an evidence link).

## Colors

A neutral jersey-white base, an ink scale, and a small warm/cool data palette; team colors are injected at runtime and confined to identity.

### Primary
- **Box-Score Ink** (ink): text, primary buttons, the selected segment, the heavy rule over each stat figure, the selected table row's top and bottom rules.

### Team colorway (runtime, not tokens)
Set on `:root` from the selected team by `lib/color.ts` and never hard-coded: `--team` (shell bar, inner twill outline), `--team-2` (stitching, wordmark outline, outer twill layer), `--on-team` / `--on-team-muted` (bar text), `--twill-fill`, `--twill-inner`, `--twill-outer`. The colorway function enforces legibility: a primary too light for white type is deepened; the inner outline falls back to ink when the primary is under 3:1 on the ground; the fill is whichever of white or the secondary reads best inside it; a pale secondary (under 1.8:1 on white, such as silver) is deepened 35% toward ink so the outer layer still shows.

### Data
- **Above-Average Brick** (hot): positive impact, hot shooting zones, the warm end of the diverging scale.
- **Below-Average Harbor Blue** (cold): negative impact, cold zones, the cool end.
- **Neutral Series Slate** (slate): single-series bars and lines with no good or bad direction.
- **Paint Ochre** (paint): paint-spot rings on the half court.
- **Hot Tint / Cold Tint** (hot-tint, cold-tint): backgrounds behind warm and cool values.

### Semantic
- **Fit Green** (ok): the incoming player's ring and outline on a roster move.
- **Caution Amber** (warn, warn-tint): stale-result and assumption notices.
- **Error Red** (err): failed requests and validation.
- **Focus Blue** (focus): focus rings, links, the text caret.

### Neutral
- **Home-White Mesh** (ground): page ground under the dot weave.
- **Panel White** (surface): tables, cards, inputs, the court panel.
- **Sunk Panel** (surface-sunk): table headers, hover fills, scrollbar tracks.
- **Hairline / Soft Hairline** (rule, rule-soft): borders, section dividers, row separators.
- **Second Ink / Muted** (ink-2, muted): descriptions, labels, help text. Both pass AA on ground and surface.

### Named Rules
**The Uniform Is Identity Rule.** Team color dresses the shell bar, the wordmark and the numerals. It never encodes a value, a status or a selection tint stronger than 9%.

**The Two-Direction Data Rule.** Warm means above average or helps, cool means below average or hurts, slate means neither. One fixed scale per comparison, centered on league average.

## Typography

**Display Font:** Graduate (with Archivo), numerals and the wordmark only
**Body Font:** Archivo (with system-ui)
**Label Font:** Archivo Narrow (with Archivo)

**Character:** A collegiate block numeral set against a plain, slightly wide grotesk, like the number on a jersey above the small print of a box score. All three are self-hosted through @fontsource.

### Hierarchy
- **Numeral** (Graduate 400, 0.84 of the twill height: 22px in tables, 30px on the court, 44px on cards): jersey numbers only. Initials in Archivo Narrow 700 when a player has no number.
- **Headline** (600, 2rem, 1.15): page h1, visually hidden on workspace pages so the first section title leads.
- **Title** (600, 1.5rem, 1.15): section titles such as "Best five-man units".
- **Figure** (600, 1.875rem, 1.15, tabular): the four-figure stat line; 1.5rem under 720px.
- **Body** (400, 0.9375rem, 1.5, tabular): running text, capped at 70 to 75ch for descriptions.
- **Body small** (400, 0.8125rem): tables, controls, help text, tooltips.
- **Label** (Archivo Narrow 600, 0.75rem, 0.05em to 0.08em, uppercase): table headers and stat labels.

### Named Rules
**The Tabular Rule.** Every number is set in tabular figures (`font-feature-settings: "tnum"` on body), so columns and rolling counters never shift.

**The Numerals Only Rule.** Graduate is reserved for jersey numbers and the wordmark. Headings and figures stay in Archivo.

## Layout

A single centered column up to 1320px with 32px side gutters (16px under 900px), on a 4px spacing scale. The shell bar is 64px and sticky on wide screens; at 900px and below its tabs wrap onto their own rows and the bar scrolls away with the page, so `--bar-stick` drops to 0 and scroll padding, sticky columns and in-page anchors stop reserving space for it. Sections are separated by 48px and a hairline; the first section of each page has no rule and owns the first viewport.

Lineup Lab pairs a ranked table (about 1.45fr) with a sticky right column (stat line plus half court). Under 1180px the court and stats move above the table, and selecting a unit scrolls the court into view. Tables scroll horizontally inside their own frame on narrow screens; the page itself never scrolls sideways. On touch screens every control outside running text is at least 44px tall, and help buttons get a 44px hit area that overhangs instead of adding line height.

## Elevation & Depth

Flat by default. Depth comes from tonal layering (mesh ground, white surface, sunk header) and hairline borders. The only shadow is the tooltip's raise, because it floats over content.

### Shadow Vocabulary
- **Raise** (`box-shadow: 0 1px 2px rgba(18,18,18,0.08), 0 4px 12px rgba(18,18,18,0.06)`): floating help tooltips only.

### Named Rules
**The Flat Panel Rule.** Panels, cards and tables never carry a shadow; they are separated by a 1px rule-soft border on white.

## Shapes

Restrained, nearly square corners: 3px on buttons, inputs, panels, tooltips and tabs, 2px on inline text buttons. Circles appear only where they mean something: the defensive-gravity rings on the court and the help glyph. The court is drawn to regulation geometry. The only patterned edge is the stitched hem under the shell bar.

## Components

### Buttons
Plain and firm; they confirm the press.
- **Shape:** gently squared (3px), 40px tall, 16px side padding, 600 weight, small type.
- **Primary:** ink fill with ground text; hover deepens to #2b2b2b on fine pointers only.
- **Secondary:** white with a hairline border; hover sinks the fill and darkens the border.
- **Press:** `scale(0.97)` over 160ms with the strong ease-out. Busy buttons show a 14px spinner and `aria-busy`.
- **Labels:** a verb and an object ("Evaluate move", "Save lineup").

### Segmented control
A row of radio segments in one hairline frame; the chosen segment is ink with ground text. Focus draws an inset 2px focus ring.

### Inputs / Fields
- **Style:** white, hairline border, 3px corners, 40px tall, 12px side padding.
- **Focus:** border and a 1px ring in focus blue.
- **Labels:** always visible above the field, 600 weight; help text in muted below.

### Data table
- **Header:** sunk panel, Archivo Narrow uppercase labels, sticky. Sortable headers are real buttons (24px minimum, 44px on touch) with a two-triangle glyph; a help button sits 6px to the right of the label.
- **Rows:** hairline separators, 8px cells, sunk hover tint on fine pointers. On desktop the ranked units table never scrolls sideways: its column takes at least its min-content width and the court gives way.
- **Selected row:** a 9% team tint plus a 2px ink rule above and below, and a bold rank, so the state never rests on tint alone.

### Help tooltip
A 14px question-mark glyph button (5px padding) that opens an ink tooltip with ground text, positioned against the viewport and clamped 16px inside it, scaling in from 0.97 over 140ms from the trigger's position. Closes on Escape, blur, scroll and resize.

### Navigation
Team-colored shell bar: wordmark in two-layer twill on the left, five workspace tabs, the "Your team" select on the right. Tabs are muted on-team text; hover adds a 12% on-team wash; the active tab is a ground-colored chip with ink text. The tabs keep the team in the URL as they navigate.

### Twill numeral (signature)
An SVG of the player's real jersey number in three heights (26, 36, 52px): an outer layer stroked in `--twill-outer`, a dashed sewing line in `--twill-fill` at 36px and up, and the fill with an inner outline in `--twill-inner`. Players without a number show initials. An incoming player on a roster move adds a 2px ok outline and a "(new)" text tag.

### Stat line
A box-score row of up to four figures, each under a 3px ink rule with an uppercase label and optional help. Cells share label, figure and evidence rows through subgrid, so every figure starts on the same line even when a label wraps. Figures roll to their new value over 0.3s (React Bits Counter) with the plain value available to screen readers.

### Spacing map (signature)
The selected unit's five numerals stand at their spots on a regulation half court, each inside a ring sized by how far the defense must stretch to guard him: slate-blue for perimeter spots, ochre for paint spots, green for an incoming player. When the unit changes, players who stay glide to their new spots (0.28s, ease-in-out); new players settle in from 0.95 scale and have their outer twill layer stitched on over 0.6s. All of it is skipped under reduced motion.

## Do's and Don'ts

### Do:
- **Do** show players as their real jersey numbers in the selected team's colorway wherever a lineup appears.
- **Do** keep data colors fixed (hot, cold, slate) and independent of the team.
- **Do** put an explanation one click from every headline number: a help button or an evidence link.
- **Do** keep motion to state feedback under 300ms on the strong ease-out or ease-in-out curves, transforms and opacity only, and drop it under reduced motion.
- **Do** gate hover styles to `(hover: hover) and (pointer: fine)` and keep touch targets at 44px.
- **Do** keep every pointer target at least 24px (WCAG 2.5.8), letting small hit areas overhang instead of widening the layout.
- **Do** keep page state in the URL (`?team`, `?unit`, `?prospect`, `?player`, `?q`) so a reload or a shared link opens the same view; workspace tabs carry only the team.
- **Do** make removals reversible with an Undo next to the result rather than a confirmation dialog.
- **Do** bring a result that renders out of view (a prospect report, a move evaluation) into view when it is requested.
- **Do** end loading and in-progress labels with an ellipsis and use curly quotes in interface copy.

### Don't:
- **Don't** use team color to encode a value, a direction or a status.
- **Don't** add shadows to panels, cards or tables.
- **Don't** use Graduate for headings or figures.
- **Don't** use purple-to-blue gradients, gradient text, glassmorphism, colored-border cards, grain over gradients, emojis in headings, Inter, or Lucide icons.
- **Don't** put a badge or eyebrow above a headline, or set three icon boxes in a row.
- **Don't** fade sections in on scroll, add a cursor beam, or make buttons fade on hover.
- **Don't** use em dashes or buzzwords in interface copy.
