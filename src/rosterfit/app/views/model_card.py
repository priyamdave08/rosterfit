"""Model Card: how the lineup and prospect models are trained and how well they predict."""
import pandas as pd
import plotly.express as px
import streamlit as st

from rosterfit.app import common as C
from rosterfit.app import ui
from rosterfit.viz import palette as P

ctx = C.context()
lm, pm = ctx.lineup_model.metrics, ctx.prospect_model.metrics
ui.page_header("Model Card", "How the two models are trained, and how well they predict on seasons and draft "
               "classes they never saw.")

ui.section("Lineup efficiency model")
st.markdown("""
Predicts a lineup's offensive and defensive rating (per 100 possessions, vs league average) from the five
players' **prior-season** profiles. Trained on every team-season since 2011-12 (a team-season is the
minutes-weighted average of the lineups it played). Ridge + gradient boosting blend, validated
**leave-one-season-out**.""")
a, b, c = st.columns(3)
a.metric("Net rating R²", f"{lm['net_r2']:.2f}", f"{lm['net_r2'] - lm['net_r2_bpm_baseline']:+.2f} vs BPM-only",
         help="Out of sample. Baseline: average player BPM alone.")
b.metric("Offense R²", f"{lm['off_rtg_rel_r2_blend']:.2f}",
         f"{lm['off_rtg_rel_r2_blend'] - lm['off_rtg_rel_r2_bpm_baseline']:+.2f} vs BPM-only")
c.metric("Defense R²", f"{lm['def_rtg_rel_r2_blend']:.2f}",
         f"{lm['def_rtg_rel_r2_blend'] - lm['def_rtg_rel_r2_bpm_baseline']:+.2f} vs BPM-only")

ui.section("Prospect outcome model")
st.markdown("""
**Outcome definition (latent trajectories).** A group-based finite mixture model is fit to every draftee's
four-season path of VORP and minutes. BIC picks the number of groups; each group is named from its mean path.
*Bust* = groups out of the league by year 4. *Hit* = groups averaging ≥ 1.5 VORP over four seasons.""")
order = list(ctx.prospect_model.tier_names)  # worst to best
colors = dict(zip(order, P.ORDINAL, strict=False))
groups = pd.DataFrame([{"Group": g["name"], "Season": y + 1, "Minutes": g["mean_mp_path"][y],
                        "VORP": g["mean_vorp_path"][y], "Players": g["n"]}
                       for g in ctx.prospect_model.groups for y in range(4)])
left, right = st.columns(2)
for col, metric, title in ((left, "Minutes", "Mean minutes by NBA season"), (right, "VORP", "Mean VORP by NBA season")):
    fig = px.line(groups, x="Season", y=metric, color="Group", markers=True, title=title,
                  category_orders={"Group": order[::-1]}, color_discrete_map=colors)
    fig.update_layout(height=360, margin=C.CHART_MARGIN, xaxis_dtick=1, legend_title_text="")
    col.plotly_chart(fig, width="stretch")
st.caption("Groups are coloured from worst (cool) to best (warm).")

comp = pd.DataFrame({
    "Metric": ["P(hit) AUC", "P(hit) AUC, 1st round only", "P(bust) AUC", "Expected-value Spearman ρ"],
    "College stats only": [pm["hit_auc_stats"], pm["hit_auc_stats_round1"], pm["bust_auc_stats"], pm["ev_spearman_stats"]],
    "Draft slot only": [pm["hit_auc_pick"], pm["hit_auc_pick_round1"], pm["bust_auc_pick"], pm["ev_spearman_pick"]],
}).round(3)
st.dataframe(comp, hide_index=True, width="stretch")
st.markdown("""
**How to read this.** Draft slot is a strong signal because it encodes scouting, medicals and interviews,
and because teams give high picks more minutes. College stats alone **rank first-round outcomes better than the
actual draft order did** and predict 4-year value better than slot, but slot is still better at predicting who
washes out of the league (second-round contracts are non-guaranteed).""")

ui.section("College to NBA translation", "Out-of-sample correlation between each projected stat and the player's "
           "actual early-career NBA number.")
tr = {k.replace("translate_r_", ""): v for k, v in pm.items() if k.startswith("translate_r_")}
tr = pd.DataFrame(sorted(((C.PROFILE_LABELS.get(k, k), v) for k, v in tr.items()), key=lambda kv: kv[1]),
                  columns=["Stat", "r"])
fig = px.bar(tr, x="r", y="Stat", orientation="h", text=tr["r"].map(lambda v: f"{v:.2f}"))
fig.update_traces(textposition="inside", insidetextanchor="end", textfont_color="#FFFFFF")
fig.update_layout(height=600, margin={**C.CHART_MARGIN, "t": 8}, xaxis_title="Correlation (r)", yaxis_title="",
                  xaxis_range=[0, 1])
st.plotly_chart(fig, width="stretch")
with st.expander("All metrics (raw)"):
    st.json({"lineup": lm, "prospect": pm})
