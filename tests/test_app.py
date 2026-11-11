"""Smoke-test every dashboard page headlessly (needs the local warehouse and trained models)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import requires_data

APP = str(Path(__file__).resolve().parents[1] / "src/rosterfit/app/streamlit_app.py")
PAGES = ["views/lineup_lab.py", "views/draft_room.py", "views/roster_moves.py", "views/player_cards.py",
         "views/model_card.py"]

pytestmark = requires_data


@pytest.fixture
def app():
    return AppTest.from_file(APP, default_timeout=300).run()


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_errors(app, page):
    app.switch_page(page).run()
    assert not app.exception, app.exception[0].value


def test_team_choice_persists_across_pages(app):
    app.selectbox(key="team_widget").set_value("BOS").run()
    app.switch_page("views/model_card.py").run()
    app.switch_page("views/draft_room.py").run()
    assert app.selectbox(key="team_widget").value == "BOS"


def test_draft_board_empty_state(app):
    app.switch_page("views/draft_room.py").run()
    app.text_input[0].set_value("zzzzqqq").run()
    assert not app.exception
    assert any("No prospect matches" in i.value for i in app.info)


def test_player_search_ranks_prefix_first(app):
    app.switch_page("views/player_cards.py").run()
    app.text_input[0].set_value("wemb").run()
    player = [s for s in app.selectbox if s.label.startswith("Player")][0]
    assert player.value == "wembavi01"


def test_hosted_copy_points_to_the_react_app(monkeypatch):
    """The public Streamlit address now sends visitors to the React app instead of the dashboard."""
    monkeypatch.setenv("ROSTERFIT_SHOW_MOVED", "1")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == "RosterFit has moved"
    assert "rosterfit.vercel.app" in at.markdown[0].value
