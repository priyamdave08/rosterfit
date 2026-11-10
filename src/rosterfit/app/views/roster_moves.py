"""Signings and Trades: add or remove players and re-score every lineup."""
import pandas as pd
import streamlit as st

from rosterfit.app import common as C
from rosterfit.app import ui
from rosterfit.engine.fit import evaluate_move

ctx = C.context()
names = C.team_names()
team = ui.page_header("Signings and Trades", "Add or remove players and re-score every lineup with the same model "
                      "the Draft Room uses. Fit is measured against this roster, not in a vacuum.",
                      names, C.team_colors())
roster = ctx.team_roster(team)

mode = st.radio("Move type", ["Free-agent signing", "Trade"], horizontal=True)
if mode == "Free-agent signing":
    fa = ctx.free_agents()
    st.markdown(f"{len(fa)} unsigned players with 300+ recent NBA minutes are available.")
    pool_ids = list(fa.index)
else:
    rostered = ctx.players[(ctx.players["source"] != "replacement") & ctx.players["current_team"].notna()
                           & (ctx.players["current_team"] != team)]
    pool_ids = list(rostered.sort_values("minutes_proxy", ascending=False).index)

left, right = st.columns(2) if mode == "Trade" else (st.container(), None)
incoming = left.multiselect("Incoming", pool_ids, max_selections=3, key=f"incoming_{mode}",
                            format_func=lambda i: f"{ctx.players.loc[i, 'player']} ({C.team_tag(i)})",
                            placeholder="Type a name to search")
outgoing = []
if right is not None:
    outgoing = right.multiselect("Outgoing", list(roster.index), max_selections=4,
                                 format_func=lambda i: ctx.players.loc[i, "player"],
                                 placeholder=f"Players leaving the {names[team]}")

run_key = (team, mode, tuple(incoming), tuple(outgoing))
if st.button("Evaluate move", type="primary", disabled=not incoming):
    cands = []
    for i in incoming:
        row = ctx.players.loc[i].copy()
        row["player_id"] = i
        cands.append(row)
    with st.spinner(f"Re-scoring every {names[team]} lineup…"):
        try:
            st.session_state["move_result"] = (run_key, evaluate_move(ctx, team, cands, outgoing))
        except ValueError as err:
            st.session_state.pop("move_result", None)
            st.error(f"This move isn't possible: {err}.")
if not incoming:
    st.info("Choose at least one incoming player to evaluate the move.")

stored = st.session_state.get("move_result")
if stored and stored[0][0] == team:
    if stored[0] != run_key:
        st.warning("The move changed since this evaluation. Click Evaluate move to update.")
    res = stored[1]
    ui.section("Result")
    a, b, c = st.columns(3)
    a.metric("Best lineup net", f"{res.after_best:+.1f}", f"{res.ceiling_delta:+.2f} vs now",
             help="Projected net rating of the best five-man unit after the move")
    b.metric("Top-10 lineup depth", f"{res.after_depth:+.1f}", f"{res.depth_delta:+.2f} vs now",
             help="Average net rating of the ten best units after the move")
    c.metric("Fit score", " / ".join(f"{res.fit_score(pid):.0f}" for pid in res.incoming),
             help="0-100, 50 = neutral. One score per incoming player.")
    st.dataframe(pd.DataFrame({"Player": [ctx.players.loc[pid, "player"] for pid in res.incoming],
                               "Best lineup with him": [res.best_with.get(pid) for pid in res.incoming],
                               "Replaces": [res.displaces.get(pid) for pid in res.incoming],
                               "Synergy": [res.synergy.get(pid) for pid in res.incoming]}),
                 hide_index=True, width="stretch",
                 column_config={"Best lineup with him": st.column_config.NumberColumn(format="%+.1f"),
                                "Synergy": st.column_config.NumberColumn(
                                    format="%+.2f", help="How much more he helps this team than the median NBA team")})
    before, after = st.columns(2)
    before.subheader("Before", anchor=False)
    C.show_lineups(res.lineups_before.head(5), where=before)
    after.subheader("After", anchor=False)
    C.show_lineups(res.lineups_after.head(5), where=after)
    C.lineup_panel(res.lineups_after.iloc[0]["player_ids"], "New best lineup", key="move",
                   highlight=ctx.players.loc[res.incoming[0], "player"])
