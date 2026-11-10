from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rosterfit import config
from rosterfit.features.players import PROFILE_COLS

HAS_DATA = config.DB_PATH.exists() and (config.MODEL_DIR / "lineup_model.joblib").exists()
requires_data = pytest.mark.skipif(not HAS_DATA, reason="needs `rosterfit all` to have built data + models")


def make_player(name: str, **overrides) -> dict:
    base = {c: 0.0 for c in PROFILE_COLS}
    base.update(bpm=0.0, obpm=0.0, dbpm=0.0, ts_pct=0.57, usg_pct=20.0, ast_pct=15.0, tov_pct=12.0,
                orb_pct=4.0, drb_pct=14.0, trb_pct=9.0, stl_pct=1.5, blk_pct=1.5, fg3a_rate=0.4,
                fta_rate=0.25, fg3_pct_eb=0.36, fg3a_per_poss=7.0, rim_freq=0.25, rim_fg=0.65,
                mid_freq=0.12, corner3_share=0.25, off_rtg=114.0, def_rtg=115.0, pos_num=3.0)
    base.update(overrides)
    base["player"] = name
    return base


@pytest.fixture
def roster() -> pd.DataFrame:
    rows = [
        make_player("Point God", pos_num=1, ast_pct=35, usg_pct=28, bpm=5, obpm=4.5, fg3_pct_eb=0.39),
        make_player("Wing Shooter", pos_num=2, fg3a_per_poss=11, fg3_pct_eb=0.41, bpm=1.5, corner3_share=0.4),
        make_player("Three and D", pos_num=3, stl_pct=2.5, fg3_pct_eb=0.37, bpm=1.0, dbpm=1.5),
        make_player("Stretch Four", pos_num=4, fg3a_per_poss=8, blk_pct=2.0, bpm=0.5),
        make_player("Rim Anchor", pos_num=5, blk_pct=6.0, fg3a_rate=0.0, fg3a_per_poss=0.0, rim_freq=0.7,
                    orb_pct=12, drb_pct=26, bpm=3.0, dbpm=3.5),
        make_player("Bench Big", pos_num=5, blk_pct=3.5, fg3a_rate=0.02, fg3a_per_poss=0.2, rim_freq=0.6, bpm=-2.5),
        make_player("Bench Guard", pos_num=1, ast_pct=24, usg_pct=22, bpm=-3.0, fg3_pct_eb=0.31),
    ]
    df = pd.DataFrame(rows)
    df.index = [f"p{i}" for i in range(len(df))]
    df["minutes_proxy"] = np.linspace(2500, 600, len(df))
    return df
