"""Player Cards: shot profile, league percentiles and season history for any NBA player."""
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

from rosterfit import config
from rosterfit.app import common as C
from rosterfit.app import ui
from rosterfit.db.warehouse import query
from rosterfit.engine.context import rank_search
from rosterfit.features.league import nba_zone_averages
from rosterfit.viz import palette as P
from rosterfit.viz import shots

ctx = C.context()
names = C.team_names()
league_nba, _ = C.league_shooting()
ui.page_header("Player Cards", "Where a player shoots from, how efficiently, and where he ranks in the league.")

card_pool = ctx.players[ctx.players["source"] != "replacement"].sort_values("minutes_proxy", ascending=False)
s1, s2 = st.columns(2)
q = s1.text_input("Search players", placeholder="Name or team code, e.g. wemb, Doncic, SAS",
                  help="Matches any part of a name, ignores accents and tolerates typos. A team code lists that roster.")
code = q.strip().upper()
matches = (list(card_pool.index[card_pool["current_team"] == code]) if code in names
           else rank_search(card_pool["player"], q, limit=None))
if not matches:
    s2.selectbox("Player", ["No matches"], disabled=True)
    st.info(f'No players match "{q}". Try part of a first or last name, or a team code such as BOS.')
    st.stop()
label = f"Player ({len(matches)} match{'es' if len(matches) != 1 else ''})" if q else "Player"
pid = s2.selectbox(label, matches, format_func=lambda i: f"{ctx.players.loc[i, 'player']} ({C.team_tag(i)})")
r = ctx.players.loc[pid]

st.subheader(f"{r['player']}", anchor=False)
a, b, c, d = st.columns(4)
ui.text_stat("Archetype", str(r.get("archetype", "n/a")), where=a)
b.metric("BPM (regularised)", f"{r['bpm']:+.1f}", help="Box plus/minus, shrunk toward his position's average "
         "when minutes are limited")
c.metric("True shooting", C.pct(r["ts_pct"]))
source_help = {"nba": "Regularised NBA stats", "nba+college": "Young player: NBA stats blended with his college "
               "projection", "college": "Rookie with no NBA minutes: college projection"}
d.metric("Profile source", str(r["source"]), help=source_help.get(str(r["source"])))

seasons = query("SELECT * FROM mart_player_season WHERE player_id = ? ORDER BY season DESC", [pid])
left, mid = st.columns([1.1, 1])
with left:
    if len(seasons):
        sea = st.selectbox("Season", seasons["season"].tolist(), format_func=ui.season_label)
        row = seasons[seasons["season"] == sea].iloc[0]
        zc = shots.nba_zones(row, nba_zone_averages(int(sea)) if sea < config.CURRENT_SEASON else league_nba)
        st.plotly_chart(shots.zone_chart(zc, f"Shot zones, {ui.season_label(int(sea))}"), width="stretch")
        st.caption("Bubble size and top number: share of shots. Bottom number and colour: FG% "
                   "(colour is relative to league average).")
        if st.toggle("Show exact shot locations (stats.nba.com)",
                     help="Optional: needs the nba_api package and network access to stats.nba.com."):
            from rosterfit.ingest.nba_shots import hexbin_chart, shot_locations

            with st.spinner("Requesting shot locations from stats.nba.com…"):
                locs = shot_locations(r["player"], int(sea))
            if locs is None or locs.empty:
                st.info("Couldn't load exact locations (stats.nba.com unreachable or nba_api not installed). "
                        "The zone chart above uses Basketball-Reference data and is unaffected.")
            else:
                st.plotly_chart(hexbin_chart(locs, "Shot locations"), width="stretch")
    else:
        st.info("No NBA shooting data yet. This player's profile is a projection from college stats.")
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
                                    line_color=P.PRIMARY, fillcolor=P.rgba(P.PRIMARY, 0.18),
                                    hovertemplate="%{theta}: %{r:.0f}th percentile<extra></extra>"))
    fig.update_layout(polar={"radialaxis": {"range": [0, 100], "tickvals": [50, 100], "showticklabels": False},
                             "angularaxis": {"tickfont": {"size": 11}}},
                      title="League percentiles (500+ min)", height=460,
                      margin={"l": 72, "r": 72, "t": 70, "b": 30})
    st.plotly_chart(fig, width="stretch")
    st.caption("Inner ring = league median (50th percentile), outer ring = best in the league. "
               "Ball security is inverted turnover rate.")

if len(seasons):
    st.subheader("Season by season", anchor=False)
    cols = {"season": "Season", "team_id": "Team", "age": "Age", "g": "G", "mp": "MP", "per": "PER",
            "ts_pct": "TS%", "usg_pct": "USG%", "bpm": "BPM", "vorp": "VORP", "ws_per_48": "WS/48",
            "off_rtg": "ORtg", "def_rtg": "DRtg"}
    table = seasons[list(cols)].rename(columns=cols)
    table["Season"] = table["Season"].map(lambda s: ui.season_label(int(s)))
    table["TS%"] = table["TS%"] * 100
    st.dataframe(table, hide_index=True, width="stretch",
                 column_config={"TS%": st.column_config.NumberColumn(format="%.1f%%"),
                                "WS/48": st.column_config.NumberColumn(format="%.3f"),
                                **{c: st.column_config.NumberColumn(format="%.0f")
                                   for c in ["Age", "G", "MP", "ORtg", "DRtg"]},
                                **{c: st.column_config.NumberColumn(format="%.1f")
                                   for c in ["PER", "USG%", "BPM", "VORP"]}})
