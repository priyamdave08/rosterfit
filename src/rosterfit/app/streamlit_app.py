"""RosterFit front-office dashboard.

    streamlit run src/rosterfit/app/streamlit_app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from rosterfit import config
from rosterfit.cloud import scouting
from rosterfit.db.warehouse import query
from rosterfit.engine.context import get_context
from rosterfit.engine.fit import best_lineups, compare_candidates, evaluate_move
from rosterfit.features.college import FEATURE_LABELS
from rosterfit.features.league import college_zone_averages, nba_zone_averages
from rosterfit.features.players import PROFILE_COLS
from rosterfit.viz import shots

st.set_page_config(page_title="RosterFit", layout="wide")

STAT_LABELS = {
    "avg_bpm": "Talent (BPM)", "avg_obpm": "Offensive BPM", "avg_dbpm": "Defensive BPM",
    "avg_ts_pct": "True shooting", "spacing_index": "Spacing", "n_shooters": "# shooters",
    "n_creators": "# creators", "n_rim_protectors": "# rim protectors", "usage_overload": "Usage overload",
    "usage_vacuum": "Usage vacuum", "usage_sd": "Usage spread (star vs committee)", "usage_weighted_ts": "Shot-taker TS%",
    "paint_clog": "Paint congestion", "avg_trb_pct": "Rebounding", "creator_x_spacing": "Creation × spacing",
    "def_anchor_x_perimeter": "Rim protection × ball pressure", "avg_off_rtg": "Offensive rating",
    "avg_def_rtg": "Defensive rating", "avg_tov_pct": "Turnovers", "avg_stl_pct": "Steals",
    "avg_blk_pct": "Blocks", "no_creator": "No creator", "no_rim_protector": "No rim protector",
    "avg_pos": "Size", "pos_spread": "Positional spread", "avg_ast_pct": "Assist rate",
    "avg_drb_pct": "Defensive rebounding", "avg_orb_pct": "Offensive rebounding", "avg_usg_pct": "Usage",
    "avg_fta_rate": "Free-throw rate", "avg_fg3a_rate": "3PA rate", "avg_corner3_share": "Corner-3 share",
    "avg_rim_freq": "Rim frequency", "avg_rim_fg": "Rim FG%", "avg_mid_freq": "Mid-range frequency",
    "usage_total": "Usage total", "too_small": "Too small", "too_big": "Too big",
    "n_non_shooters": "# non-shooters", "n_bigs": "# bigs",
}
COLLEGE_LABELS = FEATURE_LABELS


@st.cache_resource(show_spinner="Loading models and rosters (first load ~30 s)…")
def load():
    return get_context()


ctx = load()
team_names = ctx.teams.set_index("team_abbr")["team_name"].to_dict()
league_nba = nba_zone_averages()
league_college = college_zone_averages()


def pct(x: float) -> str:
    return f"{x:.0%}" if pd.notna(x) else "n/a"


def five_frame(ids: list[str]) -> pd.DataFrame:
    rows = []
    for pid in ids:
        if str(pid).startswith("prospect:"):
            rows.append(ctx.prospect_as_player(int(str(pid).split(":")[1])))
        else:
            r = ctx.players.loc[pid].copy()
            r["player_id"] = pid
            rows.append(r)
    return pd.DataFrame(rows)


def drivers_chart(df: pd.DataFrame, value_col: str, labels: dict, title: str) -> go.Figure:
    d = df.copy()
    d["label"] = d["feature"].map(labels).fillna(d["feature"])
    d = d.iloc[::-1]
    fig = go.Figure(go.Bar(x=d[value_col], y=d["label"], orientation="h",
                           marker_color=np.where(d[value_col] >= 0, "#2A7F62", "#B8461B"),
                           hovertext=[f"value = {v:.3g}" for v in d["value"]], hoverinfo="text+x"))
    fig.update_layout(title=title, height=330, margin={"l": 10, "r": 10, "t": 40, "b": 10})
    return fig


def plural(n: int, word: str) -> str:
    return f"**{n}** {word}{'' if n == 1 else 's'}"


def lineup_panel(ids: list[str], title: str, key: str, highlight: str | None = None) -> None:
    five = five_frame(ids)
    prof = five[PROFILE_COLS].astype(float)
    pred = ctx.lineup_model.predict_lineup(prof)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net rating", f"{pred['net_rtg']:+.1f}")
    c2.metric("Offense vs avg", f"{pred['off_rtg_rel']:+.1f}")
    c3.metric("Defense vs avg", f"{-pred['def_rtg_rel']:+.1f}", help="Positive = better than league-average defense")
    c4.metric("Shooters on floor", f"{pred['features']['n_shooters']:.0f}",
              help="3PA per 100 >= 5.5 and Bayes-shrunk 3P% >= 35.5%")
    left, right = st.columns([1.15, 1])
    with left:
        fig, summary = shots.spacing_map(five.assign(player=five["player"].astype(str)), title=title,
                                         highlight=highlight)
        st.plotly_chart(fig, width="stretch", key=f"{key}_spacing")
        msg = (f"{plural(summary['perimeter_threats'], 'perimeter threat')} the defense must respect. "
               f"{plural(summary['paint_bodies'], 'player')} living in the paint.")
        if summary["congested"]:
            st.warning(msg + " The paint is congested.")
        else:
            st.caption(msg)
    with right:
        st.plotly_chart(drivers_chart(ctx.lineup_model.explain(prof), "net_impact", STAT_LABELS,
                                      "What drives this lineup's net rating"), width="stretch", key=f"{key}_drivers")
        diet = shots.lineup_shot_diet(prof)
        st.plotly_chart(px.bar(diet, x="share", y="zone", orientation="h", title="Lineup shot diet (usage-weighted)",
                               text=diet["share"].map(lambda v: f"{v:.0%}")).update_layout(
            height=250, margin={"l": 10, "r": 10, "t": 40, "b": 10}, xaxis_tickformat=".0%", xaxis_title="",
            yaxis_title=""), width="stretch", key=f"{key}_diet")


def lineup_table(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["players", "net_rtg", "off_rtg_rel", "def_rtg_rel", "n_shooters", "spacing_index", "usage_total"]].copy()
    out.columns = ["Lineup", "Net", "Off vs avg", "Def vs avg (lower=better)", "Shooters", "Spacing", "Usage Σ"]
    return out.round(2)


# --------------------------------------------------------------------------- sidebar
st.sidebar.title("RosterFit")
st.sidebar.caption("Lineup optimisation · draft grading · roster-move fit")
teams_sorted = sorted(team_names)
team = st.sidebar.selectbox("Front office", teams_sorted, index=teams_sorted.index("SAS") if "SAS" in teams_sorted else 0,
                            format_func=lambda t: f"{t}  {team_names[t]}")
page = st.sidebar.radio("Workspace", ["Lineup Lab", "Draft Room", "Free Agency and Trades", "Player Cards", "Model Card"])
st.sidebar.divider()
st.sidebar.caption(f"Data: {config.CURRENT_SEASON - 1}-{str(config.CURRENT_SEASON)[-2:]} rosters (ESPN), "
                   "Basketball-Reference, Bart Torvik. Ratings are per 100 possessions vs league average.")

roster = ctx.team_roster(team)

# --------------------------------------------------------------------------- Lineup Lab
if page == "Lineup Lab":
    st.title(f"Lineup Lab: {team_names[team]}")
    with st.spinner("Scoring every 5-man combination…"):
        bl = best_lineups(ctx, team, top=None)
    st.subheader("Optimal lineups")
    st.caption(f"{len(bl):,} realistic 5-man combinations from the top-11 rotation, ranked by projected net rating.")
    st.dataframe(lineup_table(bl.head(15)), width="stretch", height=420)

    choice = st.selectbox("Inspect lineup", bl.head(15).index, format_func=lambda i: f"#{i}: {bl.loc[i, 'players']}")
    lineup_panel(bl.loc[choice, "player_ids"], "Projected floor spacing", key="lab_best")

    st.subheader("Build your own lineup")
    opts = list(roster.index)
    default = bl.iloc[0]["player_ids"]
    picked = st.multiselect("Pick exactly five", opts, default=default, max_selections=5,
                            format_func=lambda p: ctx.players.loc[p, "player"])
    if len(picked) == 5:
        lineup_panel(picked, "Custom lineup", key="lab_custom")

    with st.expander("Roster profiles"):
        cols = ["player", "source", "archetype", "mp", "bpm", "obpm", "dbpm", "ts_pct", "usg_pct", "fg3_pct_eb",
                "fg3a_per_poss", "ast_pct", "blk_pct"]
        st.dataframe(roster[[c for c in cols if c in roster]].round(3), width="stretch")

# --------------------------------------------------------------------------- Draft Room
elif page == "Draft Room":
    st.title(f"Draft Room: {team_names[team]}")
    p = ctx.prospects
    f1, f2, f3, f4 = st.columns(4)
    min_min = f1.slider("Min. college minutes", 0, 1500, 250, 50)
    min_draft = f2.slider("Min. draftability", 0.0, 1.0, 0.5, 0.05,
                          help="P(drafted) from a model of every final college season since 2010")
    classes = f3.multiselect("Class", ["Fr", "So", "Jr", "Sr"], default=["Fr", "So", "Jr", "Sr"])
    q = f4.text_input("Search name")
    board = p[(p["total_min"] >= min_min) & (p["draft_prob"] >= min_draft) & p["class_yr"].isin(classes)]
    if q:
        board = board[board["player"].str.contains(q, case=False)]

    st.subheader("Big board: standalone prospect grades")
    st.caption("Grade = percentile of expected 4-year VORP among every college draftee since 2010 "
               "(college stats only; draft slot is NOT an input).")
    show = board[["player", "team", "class_yr", "age_at_draft", "height_in", "bpm", "grade", "grade_score",
                  "expected_vorp_4yr", "hit_prob", "bust_prob", "likeliest_path", "archetype"]].head(60).copy()
    show["height_in"] = show["height_in"].map(lambda h: f"{int(h // 12)}'{int(h % 12)}\"" if pd.notna(h) else "n/a")
    st.dataframe(show.rename(columns={"age_at_draft": "age", "height_in": "ht", "expected_vorp_4yr": "exp VORP (4y)"})
                 .round(2), width="stretch", height=380,
                 column_config={"hit_prob": st.column_config.ProgressColumn("P(hit)", min_value=0, max_value=1, format="percent"),
                                "bust_prob": st.column_config.ProgressColumn("P(bust)", min_value=0, max_value=1, format="percent"),
                                "grade_score": st.column_config.NumberColumn("score", format="%.0f")})

    st.subheader("Prospect deep dive")
    sel = st.selectbox("Prospect", board.index[:200], format_func=lambda i: f"{p.loc[i, 'player']} ({p.loc[i, 'team']})")
    if sel is not None:
        r = p.loc[sel]
        a, b, c, d, e = st.columns(5)
        a.metric("Grade (percentile)", f"{r['grade']} ({r['grade_score']:.0f})")
        b.metric("P(hit)", pct(r["hit_prob"]))
        c.metric("P(bust)", pct(r["bust_prob"]))
        d.metric("Exp. VORP (4 yrs)", f"{r['expected_vorp_4yr']:.2f}")
        e.markdown(f"<div style='font-size:0.875rem'>NBA archetype</div>"
                   f"<div style='font-size:1.25rem;font-weight:600;line-height:1.4'>{r.get('archetype', 'n/a')}</div>",
                   unsafe_allow_html=True)
        left, mid = st.columns(2)
        with left:
            tiers = pd.DataFrame({"path": ctx.prospect_model.tier_names,
                                  "prob": [r[f"p_{n.lower().replace(' ', '_')}"] for n in ctx.prospect_model.tier_names]})
            st.plotly_chart(px.bar(tiers, x="prob", y="path", orientation="h", title="Career-path probabilities",
                                   text=tiers["prob"].map(lambda v: f"{v:.0%}")).update_layout(
                height=300, xaxis_tickformat=".0%", margin={"l": 10, "r": 10, "t": 40, "b": 10}), width="stretch")
            with st.spinner("Computing SHAP attributions…"):
                expl = ctx.prospect_model.explain(p.loc[[sel]])
            st.plotly_chart(drivers_chart(expl, "impact_vorp", COLLEGE_LABELS, "Why: SHAP drivers of expected VORP"),
                            width="stretch")
        with mid:
            zc = shots.college_zones(r, league_college)
            st.plotly_chart(shots.zone_chart(zc, f"College shot profile, {r['player']}", scheme="college", height=430),
                            width="stretch")
            st.caption("Bubble size = share of shots; colour = FG% vs D-I average (Bayes-shrunk for small samples).")
        st.markdown("**Historical comps** (nearest college profiles, with how their first four NBA seasons went)")
        comps = ctx.prospect_model.comps(p.loc[[sel]], k=6)
        st.dataframe(comps[["nba_name", "team", "draft_year", "pick", "outcome", "vorp_4yr", "mp_4yr", "similarity"]]
                     .round(2), width="stretch", hide_index=True)

        provider = scouting.resolve_provider()
        label = {"bedrock": "Claude on Amazon Bedrock", "anthropic": "Claude API"}.get(provider, "template (no LLM configured)")
        if st.button(f"Write scouting memo for {team_names[team]}", help=f"Writer: {label}"):
            with st.spinner("Evaluating team fit and drafting the memo…"):
                cand = ctx.prospect_as_player(sel)
                res = evaluate_move(ctx, team, [cand])
                pid = cand["player_id"]
                fit = {"fit_score": res.fit_score(pid), "synergy": res.synergy.get(pid),
                       "best_lineup_net_with_him": res.best_with.get(pid), "current_best_net": res.before_best,
                       "displaces": res.displaces.get(pid)}
                packet = scouting.build_packet(r, expl, comps, fit, team_names[team])
                st.session_state["memo"] = (sel, scouting.generate(packet))
        if st.session_state.get("memo", (None,))[0] == sel:
            memo = st.session_state["memo"][1]
            with st.container(border=True):
                st.markdown(memo.text)
                st.caption(f"Written by: {memo.provider}{' / ' + memo.model if memo.model else ''}. "
                           "All figures come from RosterFit's models.")

    st.subheader(f"Team fit: who fits the {team_names[team]} best?")
    default = list(board.index[:6])
    chosen = st.multiselect("Prospects to compare", list(board.index[:200]), default=default,
                            format_func=lambda i: p.loc[i, "player"])
    talent_w = st.slider("Weight on standalone talent vs. team fit", 0.0, 1.0, 0.65, 0.05)
    if chosen and st.button("Run fit analysis", type="primary"):
        with st.spinner("Re-optimising lineups with each prospect…"):
            cmp = compare_candidates(ctx, team, [ctx.prospect_as_player(i) for i in chosen], talent_weight=talent_w)
        st.session_state["draft_cmp"] = cmp
    if "draft_cmp" in st.session_state:
        cmp = st.session_state["draft_cmp"]
        st.dataframe(cmp[["player", "grade", "grade_score", "fit_score", "board_score", "gain_vs_current_best",
                          "synergy", "displaces", "bust_prob", "hit_prob"]].round(2), width="stretch",
                     hide_index=True,
                     column_config={"board_score": st.column_config.ProgressColumn("Board score", min_value=0, max_value=100, format="%.0f"),
                                    "fit_score": st.column_config.ProgressColumn("Fit", min_value=0, max_value=100, format="%.0f")})
        st.caption("fit_score: 50 = neutral. gain_vs_current_best: change in best-lineup net rating with the prospect "
                   "as a rookie. synergy: how much more he helps this team than the median NBA team.")
        top = cmp.iloc[0]
        res = evaluate_move(ctx, team, [ctx.prospect_as_player(int(top["player_id"].split(":")[1]))], with_synergy=False)
        with_him = res.lineups_after[res.lineups_after["player_ids"].map(lambda ids: top["player_id"] in ids)]
        if len(with_him):
            st.markdown(f"**Best lineup featuring {top['player']}:** {with_him.iloc[0]['players']}")
            lineup_panel(with_him.iloc[0]["player_ids"], f"Spacing with {top['player']}", key="draft_fit",
                         highlight=top["player"])

# --------------------------------------------------------------------------- FA & trades
elif page == "Free Agency and Trades":
    st.title(f"Free Agency and Trades: {team_names[team]}")
    st.caption("Same engine as the draft room: add players, remove players, re-optimise every lineup.")
    mode = st.radio("Move type", ["Free-agent signing", "Trade"], horizontal=True)
    others = ctx.players[(ctx.players["source"] != "replacement") & (ctx.players["current_team"] != team)]
    if mode == "Free-agent signing":
        fa = ctx.free_agents()
        st.markdown(f"**{len(fa)} unsigned players** with recent NBA minutes (not on any current roster).")
        pool_ids = list(fa.index) + [i for i in others.index if i not in fa.index]
    else:
        pool_ids = list(others.sort_values("minutes_proxy", ascending=False).index)
    incoming = st.multiselect("Incoming", pool_ids, max_selections=3,
                              format_func=lambda i: f"{ctx.players.loc[i, 'player']} "
                                                    f"({ctx.players.loc[i].get('current_team') or ctx.players.loc[i, 'team_id']})")
    outgoing = []
    if mode == "Trade":
        outgoing = st.multiselect("Outgoing", list(roster.index), max_selections=4,
                                  format_func=lambda i: ctx.players.loc[i, "player"])
    if incoming and st.button("Evaluate move", type="primary"):
        cands = []
        for i in incoming:
            row = ctx.players.loc[i].copy()
            row["player_id"] = i
            cands.append(row)
        with st.spinner("Re-optimising lineups…"):
            res = evaluate_move(ctx, team, cands, outgoing)
        a, b, c = st.columns(3)
        a.metric("Best lineup net", f"{res.after_best:+.1f}", f"{res.ceiling_delta:+.2f}")
        b.metric("Top-10 lineup depth", f"{res.after_depth:+.1f}", f"{res.depth_delta:+.2f}")
        c.metric("Fit score", " / ".join(f"{res.fit_score(p):.0f}" for p in res.incoming))
        st.dataframe(pd.DataFrame({"player": [ctx.players.loc[p, "player"] for p in res.incoming],
                                   "best lineup with him": [res.best_with.get(p) for p in res.incoming],
                                   "replaces": [res.displaces.get(p) for p in res.incoming],
                                   "synergy": [res.synergy.get(p) for p in res.incoming]}).round(2),
                     hide_index=True, width="stretch")
        left, right = st.columns(2)
        left.markdown("**Before**")
        left.dataframe(lineup_table(res.lineups_before.head(5)), width="stretch")
        right.markdown("**After**")
        right.dataframe(lineup_table(res.lineups_after.head(5)), width="stretch")
        lineup_panel(res.lineups_after.iloc[0]["player_ids"], "New best lineup", key="move",
                     highlight=ctx.players.loc[res.incoming[0], "player"])

# --------------------------------------------------------------------------- Player cards
elif page == "Player Cards":
    st.title("Player Cards")
    pid = st.selectbox("Player", list(ctx.players[ctx.players["source"] != "replacement"]
                                      .sort_values("minutes_proxy", ascending=False).index),
                       format_func=lambda i: f"{ctx.players.loc[i, 'player']} ({ctx.players.loc[i].get('current_team') or ''})")
    r = ctx.players.loc[pid]
    a, b, c, d = st.columns(4)
    a.markdown(f"<div style='font-size:0.875rem'>Archetype</div>"
               f"<div style='font-size:1.25rem;font-weight:600;line-height:1.4'>{r.get('archetype', 'n/a')}</div>",
               unsafe_allow_html=True)
    b.metric("BPM (regularised)", f"{r['bpm']:+.1f}")
    c.metric("TS%", pct(r["ts_pct"]))
    d.metric("Profile source", r["source"])
    seasons = query("SELECT * FROM mart_player_season WHERE player_id = ? ORDER BY season DESC", [pid])
    left, mid = st.columns([1.1, 1])
    with left:
        if len(seasons):
            sea = st.selectbox("Season", seasons["season"].tolist(),
                               format_func=lambda s: f"{s - 1}-{str(s)[-2:]}")
            row = seasons[seasons["season"] == sea].iloc[0]
            zc = shots.nba_zones(row, nba_zone_averages(int(sea)) if sea < config.CURRENT_SEASON else league_nba)
            st.plotly_chart(shots.zone_chart(zc, f"{r['player']}, shot zones {sea - 1}-{str(sea)[-2:]}"),
                            width="stretch")
            if st.toggle("Try exact shot locations (stats.nba.com, optional)"):
                from rosterfit.ingest.nba_shots import hexbin_chart, shot_locations

                locs = shot_locations(r["player"], int(sea))
                if locs is None or locs.empty:
                    st.info("stats.nba.com was unreachable or `nba_api` isn't installed - showing zone chart only.")
                else:
                    st.plotly_chart(hexbin_chart(locs, "Shot locations"), width="stretch")
        else:
            st.info("No NBA shooting data yet (rookie projection).")
    with mid:
        pool = ctx.players[ctx.players["mp"] >= 500]
        stats_show = ["bpm", "obpm", "dbpm", "ts_pct", "usg_pct", "ast_pct", "tov_pct", "trb_pct", "stl_pct",
                      "blk_pct", "fg3_pct_eb", "fg3a_per_poss", "rim_freq"]
        pctl = [stats.percentileofscore(pool[s].dropna(), r[s]) for s in stats_show]
        pctl = [100 - x if s == "tov_pct" else x for s, x in zip(stats_show, pctl, strict=False)]
        radar_labels = {"bpm": "BPM", "obpm": "Off. BPM", "dbpm": "Def. BPM", "ts_pct": "True shooting",
                        "usg_pct": "Usage", "ast_pct": "Assists", "tov_pct": "Ball security", "trb_pct": "Rebounding",
                        "stl_pct": "Steals", "blk_pct": "Blocks", "fg3_pct_eb": "3P% (shrunk)",
                        "fg3a_per_poss": "3PA volume", "rim_freq": "Rim pressure"}
        theta = [radar_labels[x] for x in stats_show]
        fig = go.Figure(go.Scatterpolar(r=pctl + [pctl[0]], theta=theta + [theta[0]], fill="toself",
                                        line_color="#1F4E79", fillcolor="rgba(31,78,121,0.25)"))
        fig.update_layout(polar={"radialaxis": {"range": [0, 100]}}, title="League percentiles (500+ min)",
                          height=460, margin={"l": 40, "r": 40, "t": 60, "b": 30})
        st.plotly_chart(fig, width="stretch")
    if len(seasons):
        cols = ["season", "team_id", "age", "g", "mp", "per", "ts_pct", "usg_pct", "bpm", "vorp", "ws_per_48",
                "off_rtg", "def_rtg"]
        st.dataframe(seasons[cols].round(3), hide_index=True, width="stretch")

# --------------------------------------------------------------------------- Model card
else:
    st.title("Model Card")
    lm, pm = ctx.lineup_model.metrics, ctx.prospect_model.metrics
    st.header("1 · Lineup efficiency model")
    st.markdown("""
Predicts a lineup's offensive and defensive rating (per 100 possessions, vs league average) from the five
players' **prior-season** profiles. Trained on every team-season since 2011-12 (a team-season is the
minutes-weighted average of the lineups it played). Ridge + gradient boosting blend, validated
**leave-one-season-out**.""")
    a, b, c = st.columns(3)
    a.metric("Net rating R² (out of sample)", f"{lm['net_r2']:.2f}", f"{lm['net_r2'] - lm['net_r2_bpm_baseline']:+.2f} vs BPM-only")
    b.metric("Offense R²", f"{lm['off_rtg_rel_r2_blend']:.2f}", f"{lm['off_rtg_rel_r2_blend'] - lm['off_rtg_rel_r2_bpm_baseline']:+.2f}")
    c.metric("Defense R²", f"{lm['def_rtg_rel_r2_blend']:.2f}", f"{lm['def_rtg_rel_r2_blend'] - lm['def_rtg_rel_r2_bpm_baseline']:+.2f}")

    st.header("2 · Prospect outcome model")
    st.markdown("""
**Outcome definition (latent trajectories).** A group-based finite mixture model is fit to every draftee's
four-season path of VORP and minutes. BIC picks the number of groups; each group is named from its mean path.
*Bust* = groups out of the league by year 4. *Hit* = groups averaging ≥ 1.5 VORP over four seasons.""")
    groups = pd.DataFrame([{"group": g["name"], "year": y + 1, "minutes": g["mean_mp_path"][y],
                            "vorp": g["mean_vorp_path"][y], "n": g["n"]}
                           for g in ctx.prospect_model.groups for y in range(4)])
    left, right = st.columns(2)
    left.plotly_chart(px.line(groups, x="year", y="minutes", color="group", markers=True,
                           title="Mean minutes by season, per trajectory group"), width="stretch")
    right.plotly_chart(px.line(groups, x="year", y="vorp", color="group", markers=True,
                           title="Mean VORP by season, per trajectory group"), width="stretch")
    comp = pd.DataFrame({
        "metric": ["P(hit) AUC", "P(hit) AUC, 1st round only", "P(bust) AUC", "Expected-value Spearman ρ"],
        "college stats only": [pm["hit_auc_stats"], pm["hit_auc_stats_round1"], pm["bust_auc_stats"], pm["ev_spearman_stats"]],
        "draft slot only": [pm["hit_auc_pick"], pm["hit_auc_pick_round1"], pm["bust_auc_pick"], pm["ev_spearman_pick"]],
    }).round(3)
    st.dataframe(comp, hide_index=True, width="stretch")
    st.markdown("""
**How to read this.** Draft slot is a strong signal because it encodes scouting, medicals and interviews,
and because teams give high picks more minutes. College stats alone **rank first-round outcomes better than the
actual draft order did** and predict 4-year value better than slot, but slot is still better at predicting who
washes out of the league (second-round contracts are non-guaranteed).""")
    tr = {k.replace("translate_r_", ""): v for k, v in pm.items() if k.startswith("translate_r_")}
    st.plotly_chart(px.bar(x=list(tr.values()), y=list(tr.keys()), orientation="h",
                           title="College → NBA translation: out-of-sample correlation per stat").update_layout(
        height=520, xaxis_title="r", yaxis_title=""), width="stretch")
    with st.expander("All metrics"):
        st.json({"lineup": lm, "prospect": pm})
