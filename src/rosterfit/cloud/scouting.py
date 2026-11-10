"""AI scouting reports: Claude turns the model outputs into a front-office memo.

The numbers come from RosterFit's models (grade, bust/hit probabilities, SHAP
drivers, historical comps, team-fit metrics). Claude only *writes*; it is told to
use the supplied numbers and nothing else, so the report stays auditable.

Providers (env ROSTERFIT_LLM_PROVIDER):
  bedrock    Amazon Bedrock via AnthropicBedrockMantle (AWS credentials + region)
  anthropic  Claude API directly (ANTHROPIC_API_KEY or an `ant auth login` profile)
  none       deterministic template report, no network (default when unconfigured)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import pandas as pd

log = logging.getLogger("rosterfit.scouting")

MODEL = os.environ.get("ROSTERFIT_CLAUDE_MODEL", "claude-opus-5-5")
BEDROCK_MODEL = os.environ.get("ROSTERFIT_BEDROCK_MODEL", f"anthropic.{MODEL}")

SYSTEM = """You are a senior analyst in an NBA front office writing an internal scouting memo for the general \
manager and the draft room. You receive a JSON packet produced by the team's statistical models.

Rules:
- Use only the facts and numbers in the packet. Do not add measurements, injuries, quotes or outside knowledge.
- Treat model outputs as probabilities, not certainties, and say what the uncertainty means for the decision.
- Write in plain, direct language. No hype, no buzzwords, no em dashes.
- Structure: a one-sentence bottom line; Strengths; Concerns; NBA role and team fit; Historical comparisons; \
Recommendation. Use short paragraphs or tight bullet lists. Keep it under 450 words."""


@dataclass
class Report:
    text: str
    provider: str
    model: str | None = None


def _num(x, nd=3):
    try:
        return None if pd.isna(x) else round(float(x), nd)
    except (TypeError, ValueError):
        return x


def build_packet(prospect: pd.Series, drivers: pd.DataFrame | None = None, comps: pd.DataFrame | None = None,
                 fit: dict | None = None, team_name: str | None = None) -> dict:
    """Structured, JSON-safe summary of everything the models know about a prospect."""
    keys = ["player", "team", "conf", "class_yr", "age_at_draft", "height_in", "gp", "total_min", "bpm", "obpm",
            "dbpm", "usg", "ts", "ast_pct", "tov_pct", "orb_pct", "drb_pct", "stl_pct", "blk_pct", "fg3_eb", "ft_eb",
            "rim_eb", "fg3a_per40", "recruit_rank", "grade", "grade_score", "expected_vorp_4yr", "hit_prob",
            "bust_prob", "draft_prob", "likeliest_path", "archetype"]
    packet = {"prospect": {k: _num(prospect.get(k)) if not isinstance(prospect.get(k), str) else prospect.get(k)
                           for k in keys if k in prospect.index},
              "definitions": {
                  "grade_score": "percentile of expected 4-year NBA VORP among every college draftee since 2010",
                  "hit_prob": "P(averages >= 1.5 VORP over first four NBA seasons)",
                  "bust_prob": "P(out of the league by year 4)",
                  "shooting": "fg3_eb, ft_eb, rim_eb are Bayes-shrunk percentages",
                  "fit": "net rating per 100 possessions; synergy = gain for this team minus gain for the median team",
              }}
    if drivers is not None and len(drivers):
        from rosterfit.features.college import FEATURE_LABELS

        packet["model_drivers"] = [{"feature": r.feature, "label": FEATURE_LABELS.get(r.feature, r.feature), "value": _num(r.value), "impact_on_expected_vorp":
                                    _num(r.impact_vorp)} for r in drivers.itertuples()]
    if comps is not None and len(comps):
        packet["historical_comps"] = [{"name": r.nba_name, "college": r.team, "draft_year": int(r.draft_year),
                                       "pick": int(r.pick), "outcome": r.outcome, "vorp_first_4": _num(r.vorp_4yr)}
                                      for r in comps.itertuples()]
    if fit:
        packet["team_fit"] = {"team": team_name, **{k: _num(v) if not isinstance(v, str) else v for k, v in fit.items()}}
    return packet


def _client(provider: str):
    if provider == "bedrock":
        from anthropic import AnthropicBedrockMantle

        return AnthropicBedrockMantle(aws_region=os.environ.get("AWS_REGION", "us-east-1")), BEDROCK_MODEL
    from anthropic import Anthropic

    return Anthropic(), MODEL


def resolve_provider() -> str:
    p = os.environ.get("ROSTERFIT_LLM_PROVIDER")
    if p:
        return p
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "none"


def generate(packet: dict, provider: str | None = None, client=None, model: str | None = None) -> Report:
    provider = provider or resolve_provider()
    if provider == "none" and client is None:
        return Report(template_report(packet), "template")
    try:
        import anthropic

        if client is None:
            client, model = _client(provider)
        response = client.messages.create(
            model=model or MODEL,
            max_tokens=16000,
            output_config={"effort": "medium"},
            system=SYSTEM,
            messages=[{"role": "user", "content": "Scouting packet:\n```json\n"
                       + json.dumps(packet, indent=1, default=str) + "\n```\nWrite the memo."}],
        )
        if response.stop_reason == "refusal":
            log.warning("model declined; using template report")
            return Report(template_report(packet), "template (model declined)")
        text = "\n".join(b.text for b in response.content if b.type == "text").strip()
        return Report(text, provider, response.model)
    except ImportError:
        return Report(template_report(packet), "template (anthropic SDK not installed)")
    except anthropic.APIStatusError as exc:
        log.warning("Claude API error %s; using template report", exc.status_code)
        return Report(template_report(packet), f"template (API error {exc.status_code})")
    except anthropic.APIConnectionError:
        log.warning("Claude unreachable; using template report")
        return Report(template_report(packet), "template (no network)")
    except Exception as exc:  # noqa: BLE001 - e.g. missing AWS credentials when building the Bedrock client
        log.warning("Claude unavailable (%s: %s); using template report", type(exc).__name__, exc)
        return Report(template_report(packet), "template (provider not configured)")


def template_report(packet: dict) -> str:
    """Deterministic fallback memo built from the same packet (no LLM)."""
    p = packet["prospect"]
    lines = [f"**{p.get('player')}** ({p.get('team')}, {p.get('class_yr')}): grade **{p.get('grade')}** "
             f"({p.get('grade_score'):.0f}th percentile), expected 4-year VORP {p.get('expected_vorp_4yr'):.2f}.",
             f"P(hit) {p.get('hit_prob', 0):.0%}, P(bust) {p.get('bust_prob', 0):.0%}; most likely path: "
             f"{p.get('likeliest_path')}. Projected NBA archetype: {p.get('archetype')}."]
    drivers = packet.get("model_drivers", [])
    ups = [d["feature"] for d in drivers if (d["impact_on_expected_vorp"] or 0) > 0][:3]
    downs = [d["feature"] for d in drivers if (d["impact_on_expected_vorp"] or 0) < 0][:3]
    from rosterfit.features.college import FEATURE_LABELS

    if ups:
        lines.append("Strengths per the model: " + ", ".join(FEATURE_LABELS.get(u, u) for u in ups) + ".")
    if downs:
        lines.append("Concerns per the model: " + ", ".join(FEATURE_LABELS.get(d, d) for d in downs) + ".")
    comps = packet.get("historical_comps", [])
    if comps:
        lines.append("Closest college comps: " + "; ".join(f"{c['name']} ({c['outcome']})" for c in comps[:4]) + ".")
    fit = packet.get("team_fit")
    if fit:
        lines.append(f"Team fit for {fit.get('team')}: fit score {fit.get('fit_score', 0):.0f}/100, "
                     f"synergy {fit.get('synergy', 0):+.2f}, would displace {fit.get('displaces', '-')}.")
    return "\n\n".join(lines)
