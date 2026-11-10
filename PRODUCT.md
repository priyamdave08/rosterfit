# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Front end: Vite + React + TypeScript single-page app (user's choice), deployed to Vercel. It talks to the existing Python engine through the FastAPI service in `src/rosterfit/api/`, which will run on Hugging Face Spaces from the repository's Dockerfile (user's choice). The user asked for GSAP, Lenis and React Bits in the front end. The Streamlit dashboard (`src/rosterfit/app/`) stays as the current live demo until the React app replaces it.

## Users

Primary: NBA front-office analysts and basketball-operations staff using the tool day to day. They prepare roster decisions: which five-man units to play, which college prospects to draft, and which free agents or trade targets to pursue. They know advanced metrics (net rating, BPM, VORP, usage, true shooting) and want answers fast, without explanations they already know.

Secondary, confirmed: analytics leads the author pitches the project to (for example the Spurs' data science staff), who open it to judge the modelling.

## Product Purpose

RosterFit answers three front-office questions with one engine: what is a team's best lineup, which draft prospect fits this roster, and does a signing or trade help. Success is an analyst reaching a defensible roster answer, with the numbers behind it, in a few interactions.

## Positioning

One engine scores drafts, signings and trades the same way: add or remove players, then re-score every realistic lineup. Prospects are graded on college stats alone (draft slot is never an input) and translated into an NBA profile so they can be dropped into real lineups. Synergy separates fit from talent: how much more a player helps this team than the median NBA team. Validation is out of sample and reported honestly, including where draft slot still wins. No public product combines these (checked November 2026).

## Operating Context

- Workspaces: Lineup Lab (ranked five-man units, spacing map, rating drivers, lineup builder with saved lineups), Draft Room (big board, prospect report with SHAP drivers, comps, college shot profile, scouting memo, team-fit comparison), Signings and Trades (free-agent and trade evaluation), Player Cards (shot zones, league percentiles, season history, search), Model Card (methods and out-of-sample results).
- Every team-specific view is tied to one selected team ("Your team") that persists across workspaces.
- Ratings are per 100 possessions relative to league average; positive offense and defense mean better than average.
- Data: 2026-27 rosters from ESPN; NBA stats from Basketball-Reference; college stats from Bart Torvik; seasons back to 2010-11.

## Capabilities and Constraints

- Lineup model: ridge + gradient-boosting blend predicting offensive and defensive rating from prior-season profiles; trained on team-seasons with Monte Carlo lineup sampling.
- Prospect model: trajectory mixture model (Washout, Flameout, Empty Minutes, Slow Build, Starter, Star), P(bust), P(hit), expected 4-year VORP, letter grade from percentile.
- Scouting memos come from Claude (Bedrock or the Claude API) when a key is configured, otherwise a deterministic template; memos only use numbers from the model packet.
- Absolute lineup ratings run hotter than real five-man samples; rankings and differences are the reliable output.
- Prospect grades are calibrated on drafted players only; international and G League prospects without college stats can't be graded.
- The "shooter" count uses a hard threshold (5.5+ 3PA per 100 at a shrunk 35.5%+); near-misses count as zero.
- Heavy operations (team-fit comparison, roster moves) take seconds on a laptop and longer on free hosting; they need visible progress.

## Brand Commitments

- Front-end only (user, November 2026): the React rebuild and any design work change presentation, never product truth. Every feature, model, metric, number, dataset, label meaning and calculation stays exactly as the engine produces it today. The API may only expose existing engine outputs; it must not alter, round differently, filter or re-rank them.
- Name: RosterFit.
- Binding constraints the user set for every front end: no purple-to-blue gradients, no gradient hero text, no emojis in headings, no Inter font anywhere, no colored-border cards, no glassmorphism, no low-contrast dark mode, no row of three icon boxes, no badge above a headline, no Lucide icons, no untouched shadcn UI, no fade-in on scroll, no cursor-following beam, no buttons that fade on hover, no inconsistent spacing, no em dashes anywhere, no generic buzzwords, no serif italic accents, no Space Grotesk + Instrument Serif pairing, no grain over a gradient.
- The user's design and engineering brief (November 2026) also applies: purposeful color roles, restrained radius and shadow use, motion only for state feedback and respecting reduced motion, concrete copy, every control functional, responsive from the start.

## Evidence on Hand

- Out-of-sample results (README, Model Card): lineup net R² 0.628 vs 0.603 for an average-BPM baseline; offense R² 0.590 vs 0.524; defense R² 0.390 vs 0.271. Prospect EV Spearman 0.365 vs 0.230 for draft slot; first-round P(hit) AUC 0.666 vs 0.628; draft slot is better at P(bust) (0.802 vs 0.720) and all-pick P(hit) (0.777 vs 0.733).
- Real data for all 30 teams and about 2,800 college prospects, available through the API and the demo bundle (`src/rosterfit/demo_data.py`).
- No customers, testimonials, press, or team endorsements exist. None may be implied.

## Product Principles

1. The roster is the context: every number is about the selected team's real lineups, not players in a vacuum.
2. Show the evidence behind each answer (drivers, comps, probabilities) and state limits plainly.
3. Same engine, same scale: a draft pick, a signing and a trade are compared on identical terms.
4. Fast to the answer: an analyst should reach a ranked, defensible result in a few interactions.

## Accessibility & Inclusion

WCAG 2.2 AA (user's brief): text contrast, visible focus, full keyboard access, labelled controls, no information carried by color alone, and respect for reduced-motion preferences.
