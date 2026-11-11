"""RosterFit front-office dashboard.

    streamlit run src/rosterfit/app/streamlit_app.py

This file only sets up the page, the visual layer and navigation. Each page lives in
``views/``; shared data access and lineup components are in ``common.py``; page
chrome is in ``ui.py``; colour and type tokens are in ``rosterfit.viz.palette``.

The public demo has moved to the React app. On Streamlit Community Cloud (which runs apps from
/mount/src) this file shows a short page pointing there; run locally it is the full dashboard.
"""
import os
from pathlib import Path

import streamlit as st

from rosterfit.app import ui
from rosterfit.viz import palette  # noqa: F401  (registers the Plotly template)

NEW_HOME = os.environ.get("ROSTERFIT_NEW_HOME", "https://rosterfit.vercel.app")
HOSTED = Path(__file__).resolve().as_posix().startswith("/mount/src/") or os.environ.get("ROSTERFIT_SHOW_MOVED") == "1"

if HOSTED:
    st.set_page_config(page_title="RosterFit has moved", layout="centered")
    st.title("RosterFit has moved")
    st.write(
        "RosterFit now lives at **rosterfit.vercel.app**: the same engine and the same numbers, "
        "in a redesigned interface."
    )
    st.link_button("Open RosterFit", NEW_HOME, type="primary")
    st.stop()

st.set_page_config(page_title="RosterFit", layout="wide", initial_sidebar_state="collapsed")
ui.inject_css()

nav = st.navigation(
    [
        st.Page("views/lineup_lab.py", title="Lineup Lab", default=True),
        st.Page("views/draft_room.py", title="Draft Room", url_path="draft"),
        st.Page("views/roster_moves.py", title="Signings and Trades", url_path="moves"),
        st.Page("views/player_cards.py", title="Player Cards", url_path="players"),
        st.Page("views/model_card.py", title="Model Card", url_path="model"),
    ],
    position="top",
)
nav.run()
ui.footer()
