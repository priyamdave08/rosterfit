"""Display labels shared by the Streamlit app and the API (presentation only)."""
from __future__ import annotations

from rosterfit.features.college import FEATURE_LABELS

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
PROFILE_LABELS = {
    "bpm": "BPM", "obpm": "Offensive BPM", "dbpm": "Defensive BPM", "ts_pct": "True shooting", "usg_pct": "Usage",
    "ast_pct": "Assist rate", "tov_pct": "Turnover rate", "orb_pct": "Off. rebound rate", "drb_pct": "Def. rebound rate",
    "trb_pct": "Rebound rate", "stl_pct": "Steal rate", "blk_pct": "Block rate", "fg3a_rate": "3PA rate",
    "fta_rate": "Free-throw rate", "fg3_pct_eb": "3P% (shrunk)", "fg3a_per_poss": "3PA per 100", "rim_freq": "Rim frequency",
    "rim_fg": "Rim FG%", "mid_freq": "Mid-range frequency", "corner3_share": "Corner-3 share",
    "off_rtg": "Offensive rating", "def_rtg": "Defensive rating", "pos_num": "Position",
}
SHOOTER_HELP = ("Players taking 5.5+ threes per 100 possessions at a Bayes-shrunk 35.5% or better (above league "
                "average). A 34% shooter on volume counts as zero.")
NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}
CHART_MARGIN = {"l": 8, "r": 8, "t": 44, "b": 8}
