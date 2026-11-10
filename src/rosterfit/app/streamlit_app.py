"""RosterFit front-office dashboard.

    streamlit run src/rosterfit/app/streamlit_app.py

This file only sets up the page, the visual layer and navigation. Each page lives in
``views/``; shared data access and lineup components are in ``common.py``; page
chrome is in ``ui.py``; colour and type tokens are in ``rosterfit.viz.palette``.
"""
import streamlit as st

from rosterfit.app import ui
from rosterfit.viz import palette  # noqa: F401  (registers the Plotly template)

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
