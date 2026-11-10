---
version: 1
slug: "web-src-app-tsx"
primary_target: "web/src/App.tsx"
related_targets: ["web"]
---

# RosterFit web app (React)

Scope: the whole React front end (Lineup Lab, Draft Room, Signings and Trades, Player Cards, Model Card). Visitor mode: Operate. Front-end only: every feature, number and label meaning comes from the existing engine unchanged (PRODUCT.md, Brand Commitments).

Audience and task: front-office analysts in daily use. Pick a team, find its best five-man units, grade prospects, and test how prospects, signings and trades change the team's best lineups.

Memorable moment: the selected unit's five players standing on the half court as their own jersey numbers, re-stitching when a player is swapped.

Open decisions: none on the world. React Bits pieces must stay inside this grammar.

## Direction contract

THESIS: Every player on screen wears his real number in the selected team's colorway, so a lineup reads the way a coach reads his floor. Refuses the category default of anonymous name rows on a grey dashboard with one accent.

OWN-WORLD: Home-white mesh ground; the shell bar in the team's primary with a stitched double rule in its secondary; tackle-twill numerals (fill plus outline in team colors, auto-swapped for contrast); data never borrows team color: warm and cool for above and below average, slate for neutral series; tabular figures; restrained 3px radius.

STORY: The analyst knows which team is loaded, sees the best units ranked, reads why each rates as it does, swaps players and watches the number change, then carries the same view into draft, signing and trade decisions.

FIRST VIEWPORT: Team-colored top bar (wordmark, five workspace tabs, Your team select right). Lineup Lab: heading and one-line scope, a four-figure stat line, a sortable ranked units table whose rows show five twill numerals over surnames, and a right column half court with the selected unit as numerals at their spots inside gravity rings.

FORM: Tackle Twill, position 6 of 7 on the ordered list, seed:8cce5b437d0104d8. Raises: one fixed scale per comparison (botanical folio); every headline number one click from its evidence (monochrome product); one size ramp for player value (star atlas); nothing labelled twice (catalog sleeve). Signature interaction: swapping a player re-stitches his numeral and moves it to its spot; motion is state feedback only and off under reduced motion.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
