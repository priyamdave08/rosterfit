import numpy as np
import pandas as pd

from rosterfit.viz import shots


def test_nba_zones_partition_the_frontcourt():
    stack = np.stack(list(shots.NBA_ZONES.values())).astype(int)
    assert stack.sum(0).max() == 1                       # no cell belongs to two zones
    near_basket = (np.hypot(shots._X, shots._Y) < 28)
    assert (stack.sum(0)[near_basket] == 1).all()        # every cell inside 28 ft is covered


def test_corner_three_geometry():
    z = shots.NBA_ZONES
    ix = np.argmin(np.abs(shots._xs - 23.5))
    iy = np.argmin(np.abs(shots._ys - 0.0))
    assert z["Right corner 3"][iy, ix]
    iy_top = np.argmin(np.abs(shots._ys - 25.0))
    ix_mid = np.argmin(np.abs(shots._xs - 0.0))
    assert z["Above-break 3"][iy_top, ix_mid]


def test_zone_chart_builds(roster):
    zones = {name: shots.Zone(0.1, 0.45, 0.44) for name in shots.NBA_ZONES}
    fig = shots.zone_chart(zones, "test")
    assert len(fig.data) == 2


def test_spacing_assignment_is_one_player_per_spot(roster):
    five = roster.iloc[:5]
    assigned = shots.assign_spots(five)
    assert len({s for _, s in assigned}) == 5
    spot = dict(assigned)
    assert shots.SPOTS[spot["Rim Anchor"]][2] == "dunker"
    assert shots.SPOTS[spot["Wing Shooter"]][2] in ("corner", "wing")


def test_spacing_map_flags_congestion(roster):
    clogged = pd.concat([roster.iloc[[0]], pd.DataFrame([roster.iloc[4]] * 2), pd.DataFrame([roster.iloc[5]] * 2)])
    clogged["player"] = ["A", "B", "C", "D", "E"]
    _, summary = shots.spacing_map(clogged)
    assert summary["congested"]
