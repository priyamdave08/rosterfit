"""Draft Room: standalone prospect grades, a deep dive per prospect, and team-fit comparison."""
import pandas as pd
import streamlit as st

from rosterfit.app import common as C
from rosterfit.app import ui
from rosterfit.cloud import scouting
from rosterfit.engine.context import rank_search
from rosterfit.engine.fit import compare_candidates, evaluate_move
from rosterfit.viz import palette as P
from rosterfit.viz import shots

ctx = C.context()
names = C.team_names()
team = ui.page_header("Draft Room", "Grade every college prospect on his own numbers, then test how each one "
                      "fits this roster's lineups.", names, C.team_colors())
p = ctx.prospects
_, league_college = C.league_shooting()

# --------------------------------------------------------------------------- filters + board
f1, f2, f3, f4 = st.columns(4)
min_min = f1.slider("Min. college minutes", 0, 1500, 250, 50)
min_draft = f2.slider("Min. draftability", 0.0, 1.0, 0.5, 0.05,
                      help="Probability of being drafted, from a model of every final college season since 2010")
classes = f3.multiselect("Class", ["Fr", "So", "Jr", "Sr"], default=["Fr", "So", "Jr", "Sr"])
q = f4.text_input("Search name", placeholder="e.g. Bidunga")
board = p[(p["total_min"] >= min_min) & (p["draft_prob"] >= min_draft) & p["class_yr"].isin(classes)]
board = board.sort_values("grade_score", ascending=False)
if q.strip():
    board = board.loc[rank_search(board["player"], q, limit=None)]

ui.section("Big board", "Grade = percentile of expected 4-year VORP among every college draftee since 2010. "
           "College stats only: draft slot is not an input.")
if board.empty:
    reason = f'No prospect matches "{q}" with these filters.' if q.strip() else "No prospects pass these filters."
    st.info(f"{reason} Lower the minimum minutes or draftability, or add class years.")
    st.stop()

show = board[["player", "team", "class_yr", "age_at_draft", "height_in", "bpm", "grade", "grade_score",
              "expected_vorp_4yr", "hit_prob", "bust_prob", "likeliest_path", "archetype"]].head(60).copy()
show["height_in"] = show["height_in"].map(lambda h: f"{int(h // 12)}'{int(h % 12)}\"" if pd.notna(h) else "n/a")
show = show.rename(columns={"player": "Player", "team": "School", "class_yr": "Class", "age_at_draft": "Age",
                            "height_in": "Height", "bpm": "BPM", "grade": "Grade", "grade_score": "Score",
                            "expected_vorp_4yr": "Exp. VORP (4 yr)", "hit_prob": "P(hit)", "bust_prob": "P(bust)",
                            "likeliest_path": "Likeliest path", "archetype": "NBA archetype"})
st.dataframe(show, width="stretch", height=380, hide_index=True,
             column_config={"P(hit)": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
                            "P(bust)": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
                            "Score": st.column_config.NumberColumn(format="%.0f",
                                                                   help="Percentile among college draftees since 2010"),
                            "Age": st.column_config.NumberColumn(format="%.1f"),
                            "BPM": st.column_config.NumberColumn(format="%.1f"),
                            "Exp. VORP (4 yr)": st.column_config.NumberColumn(format="%.2f")})
st.caption(f"Showing {min(len(board), 60)} of {len(board):,} prospects that pass the filters.")

# --------------------------------------------------------------------------- deep dive
ui.section("Prospect report", "Probabilities, the college stats behind the grade, his college shot profile and "
           "the most similar past draftees.")
sel = st.selectbox("Prospect", board.index[:200], format_func=lambda i: f"{p.loc[i, 'player']} ({p.loc[i, 'team']})")
r = p.loc[sel]
a, b, c, d, e = st.columns(5)
a.metric("Grade", f"{r['grade']} ({r['grade_score']:.0f})", help="Letter grade and percentile")
b.metric("P(hit)", C.pct(r["hit_prob"]), help="Probability of averaging 1.5+ VORP over his first four seasons")
c.metric("P(bust)", C.pct(r["bust_prob"]), help="Probability of being out of the league by year 4")
d.metric("Exp. VORP (4 yrs)", f"{r['expected_vorp_4yr']:.2f}")
ui.text_stat("NBA archetype", str(r.get("archetype", "n/a")), where=e)

left, mid = st.columns(2)
with left:
    tiers = pd.DataFrame({"path": ctx.prospect_model.tier_names,
                          "prob": [r[f"p_{n.lower().replace(' ', '_')}"] for n in ctx.prospect_model.tier_names]})
    st.plotly_chart(C.share_bars(tiers, "prob", "path", "Career-path probabilities", colors=P.ORDINAL,
                                 height=300), width="stretch")
    st.caption("Paths run from worst (cool) to best (warm), named from the first four NBA seasons of past draftees.")
    with st.spinner("Computing SHAP attributions…"):
        expl = ctx.prospect_model.explain(p.loc[[sel]])
    st.plotly_chart(C.drivers_chart(expl, "impact_vorp", C.COLLEGE_LABELS, "What drives his grade"),
                    width="stretch")
with mid:
    zc = shots.college_zones(r, league_college)
    st.plotly_chart(shots.zone_chart(zc, "College shot profile", scheme="college", height=430), width="stretch")
    st.caption("Bubble size and top number: share of shots. Bottom number and colour: FG% "
               "(colour is relative to the Division I average, shrunk for small samples).")

st.subheader("Historical comps", anchor=False)
st.caption("Nearest college profiles among past draftees, and how their first four NBA seasons went.")
comps = ctx.prospect_model.comps(p.loc[[sel]], k=6)
st.dataframe(comps[["nba_name", "team", "draft_year", "pick", "outcome", "vorp_4yr", "mp_4yr", "similarity"]]
             .rename(columns={"nba_name": "Player", "team": "School", "draft_year": "Draft", "pick": "Pick",
                              "outcome": "Outcome", "vorp_4yr": "VORP (4 yr)", "mp_4yr": "Minutes (4 yr)",
                              "similarity": "Similarity"}),
             width="stretch", hide_index=True,
             column_config={"Draft": st.column_config.NumberColumn(format="%d"),
                            "Pick": st.column_config.NumberColumn(format="%d"),
                            "VORP (4 yr)": st.column_config.NumberColumn(format="%.1f"),
                            "Minutes (4 yr)": st.column_config.NumberColumn(format="%.0f"),
                            "Similarity": st.column_config.NumberColumn(format="%.2f")})

provider = scouting.resolve_provider()
writer = {"bedrock": "Claude on Amazon Bedrock", "anthropic": "Claude API"}.get(
    provider, "the built-in template (no Claude API key configured)")
memo_key = (sel, team)
if st.button(f"Write scouting memo for the {names[team]}", help=f"Written by {writer}"):
    with st.spinner("Evaluating team fit and writing the memo…"):
        cand = ctx.prospect_as_player(sel)
        res = evaluate_move(ctx, team, [cand])
        pid = cand["player_id"]
        fit = {"fit_score": res.fit_score(pid), "synergy": res.synergy.get(pid),
               "best_lineup_net_with_him": res.best_with.get(pid), "current_best_net": res.before_best,
               "displaces": res.displaces.get(pid)}
        packet = scouting.build_packet(r, expl, comps, fit, names[team])
        st.session_state["memo"] = (memo_key, scouting.generate(packet))
if st.session_state.get("memo", (None,))[0] == memo_key:
    memo = st.session_state["memo"][1]
    with st.container(border=True):
        st.markdown(memo.text)
        st.caption(f"Written by: {memo.provider}{' / ' + memo.model if memo.model else ''}. "
                   "Every figure comes from RosterFit's models.")

# --------------------------------------------------------------------------- team fit
ui.section(f"Fit with the {names[team]}", "Each prospect is dropped into the roster as a rookie and every lineup "
           "is re-scored. The board score blends his standalone grade with that fit.")
chosen = st.multiselect("Prospects to compare", list(board.index[:200]), default=list(board.index[:6]),
                        format_func=lambda i: p.loc[i, "player"], max_selections=12)
talent_w = st.slider("Weight on standalone talent vs. team fit", 0.0, 1.0, 0.65, 0.05,
                     help="1.0 ranks by grade only; 0.0 ranks by fit with this roster only.")
run_key = (team, tuple(chosen), talent_w)
if st.button("Run fit analysis", type="primary", disabled=not chosen):
    with st.spinner(f"Re-scoring {names[team]} lineups with each of {len(chosen)} prospects…"):
        cmp = compare_candidates(ctx, team, [ctx.prospect_as_player(i) for i in chosen], talent_weight=talent_w)
    st.session_state["draft_cmp"] = (run_key, cmp)
if not chosen:
    st.info("Choose at least one prospect to compare.")

stored = st.session_state.get("draft_cmp")
if stored and stored[0][0] == team:
    if stored[0] != run_key:
        st.warning("The prospects or the talent weight changed since this run. Run the analysis again to update.")
    cmp = stored[1]
    st.dataframe(cmp[["player", "grade", "grade_score", "fit_score", "board_score", "gain_vs_current_best",
                      "synergy", "displaces", "bust_prob", "hit_prob"]]
                 .rename(columns={"player": "Player", "grade": "Grade", "grade_score": "Score", "fit_score": "Fit",
                                  "board_score": "Board score", "gain_vs_current_best": "Net gain",
                                  "synergy": "Synergy", "displaces": "Displaces", "bust_prob": "P(bust)",
                                  "hit_prob": "P(hit)"}),
                 width="stretch", hide_index=True,
                 column_config={"Board score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                                "Fit": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                                "Score": st.column_config.NumberColumn(format="%.0f"),
                                "Net gain": st.column_config.NumberColumn(format="%+.2f"),
                                "Synergy": st.column_config.NumberColumn(format="%+.2f"),
                                "P(bust)": st.column_config.NumberColumn(format="percent"),
                                "P(hit)": st.column_config.NumberColumn(format="percent")})
    st.caption("Fit: 50 = neutral. Net gain: change in best-lineup net rating with the prospect as a rookie. "
               "Synergy: how much more he helps this team than the median NBA team.")
    top = cmp.iloc[0]
    res = evaluate_move(ctx, team, [ctx.prospect_as_player(int(top["player_id"].split(":")[1]))], with_synergy=False)
    with_him = res.lineups_after[res.lineups_after["player_ids"].map(lambda ids: top["player_id"] in ids)]
    if len(with_him):
        st.subheader(f"Best lineup with {top['player']}", anchor=False)
        st.caption(C.lineup_names(with_him.iloc[0]["player_ids"]))
        C.lineup_panel(with_him.iloc[0]["player_ids"], f"Spacing with {top['player']}", key="draft_fit",
                       highlight=top["player"])
