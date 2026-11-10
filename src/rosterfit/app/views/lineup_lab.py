"""Lineup Lab: best five-man units for a roster, plus a builder for hypothetical lineups."""
import pandas as pd
import streamlit as st

from rosterfit.app import common as C
from rosterfit.app import ui
from rosterfit.engine.fit import best_lineups
from rosterfit.engine.optimizer import realistic
from rosterfit.features.players import PROFILE_COLS

ctx = C.context()
names = C.team_names()
team = ui.page_header("Lineup Lab", "Every realistic five-man unit from the top-11 rotation, scored by the lineup "
                      "model. Pick one to see its spacing, or build your own.", names, C.team_colors())
roster = ctx.team_roster(team)

with st.spinner("Scoring every five-man combination…"):
    bl = best_lineups(ctx, team, top=None)

# --------------------------------------------------------------------------- ranked units
ui.section("Best five-man units", f"{len(bl):,} realistic combinations, ranked by projected net rating "
           "(points per 100 possessions). Off and Def are relative to league average; positive is better.")
C.show_lineups(bl.head(15), height=420)
choice = st.selectbox("Inspect a lineup", bl.head(15).index, format_func=lambda i: f"#{i}  {C.lineup_names(bl.loc[i, 'player_ids'])}")
C.lineup_panel(bl.loc[choice, "player_ids"], "Projected floor spacing", key="lab_best")

# --------------------------------------------------------------------------- builder
ui.section("Lineup builder", "Put any five players on the floor and compare them with this roster's best unit. "
           "Mix in players from other teams, free agents or draft prospects to test hypotheticals.")
pool_kind = st.radio("Player pool", ["Roster", "Whole league", "League + draft prospects"], horizontal=True,
                     help="Prospects use their projected early-career NBA profile.")
picked = st.multiselect("Pick exactly five", C.builder_pool(pool_kind, roster), default=bl.iloc[0]["player_ids"],
                        max_selections=5, key=f"builder_{pool_kind}", format_func=C.player_label,
                        placeholder="Type a name to search")
if len(picked) < 5:
    need = 5 - len(picked)
    st.info(f"Pick {need} more player{'s' if need != 1 else ''} to score the lineup.")
else:
    mine = C.lineup_metrics(picked)
    best = C.lineup_metrics(bl.iloc[0]["player_ids"])
    rank = int((bl["net_rtg"] > mine["Net"]).sum()) + 1
    outside = [p for p in picked if p not in roster.index]
    where = (f"would rank **below all {len(bl):,}**" if rank > len(bl) else f"would rank **#{rank}** of {len(bl):,}")
    st.markdown(f"Projected net **{mine['Net']:+.1f}**: {where} {names[team]} lineups"
                + (f", using {len(outside)} player{'s' if len(outside) != 1 else ''} from outside the roster."
                   if outside else "."))
    if not realistic(C.five_frame(picked)[PROFILE_COLS].astype(float)):
        st.warning("Unusual construction (for example no ball handler or too many bigs). "
                   "The model has seen few lineups like this, so treat the rating with caution.")
    cmp = pd.DataFrame({"Your lineup": mine, "Current best": best}).drop(index="Players")
    cmp["Difference"] = cmp["Your lineup"].astype(float) - cmp["Current best"].astype(float)
    st.dataframe(cmp.astype(float).round(2), width="stretch",
                 column_config={"Difference": st.column_config.NumberColumn(format="%+.2f")})
    C.lineup_panel(picked, "Your lineup", key="lab_custom")

    saved = st.session_state.setdefault("saved_lineups", [])
    n1, n2 = st.columns([3, 1], vertical_alignment="bottom")
    name = n1.text_input("Lineup name", value=f"Lineup {len(saved) + 1}", key=f"save_name_{len(saved)}",
                         max_chars=40)
    if n2.button("Save lineup", width="stretch"):
        label = name.strip() or f"Lineup {len(saved) + 1}"
        if any(s["ids"] == list(picked) and s["team"] == team for s in saved):
            st.info("This exact lineup is already saved.")
        else:
            saved.append({"name": label, "team": team, "ids": list(picked)})
            st.rerun()

saved = st.session_state.get("saved_lineups", [])
if saved:
    ui.section("Saved lineups", "Kept for this browser session. Ratings are recomputed each time.")
    rows = [{"Name": s["name"], "Team": s["team"], **C.lineup_metrics(s["ids"])} for s in saved]
    st.dataframe(pd.DataFrame(rows).round(2).sort_values("Net", ascending=False), hide_index=True,
                 width="stretch", column_config={"Players": st.column_config.TextColumn(width="large"),
                                                 "Net": st.column_config.NumberColumn(format="%+.1f")})
    r1, r2 = st.columns([3, 1], vertical_alignment="bottom")
    drop = r1.selectbox("Remove a saved lineup", range(len(saved)), format_func=lambda i: saved[i]["name"])
    if r2.button("Remove", width="stretch"):
        saved.pop(drop)
        st.rerun()

# --------------------------------------------------------------------------- roster reference
with st.expander(f"{names[team]} player profiles ({len(roster)} players)"):
    cols = {"player": "Player", "source": "Profile source", "archetype": "Archetype", "mp": "Minutes",
            "bpm": "BPM", "obpm": "OBPM", "dbpm": "DBPM", "ts_pct": "TS%", "usg_pct": "USG%",
            "fg3_pct_eb": "3P% (shrunk)", "fg3a_per_poss": "3PA/100", "ast_pct": "AST%", "blk_pct": "BLK%"}
    prof = roster[[c for c in cols if c in roster]].rename(columns=cols)
    prof[["TS%", "3P% (shrunk)"]] = prof[["TS%", "3P% (shrunk)"]] * 100
    st.dataframe(prof, width="stretch", hide_index=True,
                 column_config={"TS%": st.column_config.NumberColumn(format="%.1f%%"),
                                "3P% (shrunk)": st.column_config.NumberColumn(format="%.1f%%"),
                                "Minutes": st.column_config.NumberColumn(format="%.0f"),
                                **{c: st.column_config.NumberColumn(format="%.1f")
                                   for c in ["BPM", "OBPM", "DBPM", "USG%", "3PA/100", "AST%", "BLK%"]}})
    st.caption("Profile source: nba = regularised NBA stats; nba+college = young player blended with his college "
               "projection; college = rookie with no NBA minutes yet.")
