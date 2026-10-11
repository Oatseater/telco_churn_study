"""Every dashboard page loads without raising an exception.

Note: AppTest.switch_page runs the page file on its own, without the app.py frame
that adds the stylesheet and the persistent disclaimer. The disclaimer is checked
on the full app run here, and on every page in a real browser by
scripts/take_screenshots.py.
"""
import pytest
from streamlit.testing.v1 import AppTest

from src import config

PAGES = ["pages/retention.py", "pages/segments.py", "pages/calculator.py"]


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(config.ROOT / "app.py"), default_timeout=60)
    at.run()
    return at


def test_overview_loads(app):
    assert not app.exception
    assert any(config.DISCLAIMER in m.value for m in app.markdown)


@pytest.mark.parametrize("page", PAGES)
def test_page_loads(app, page):
    app.switch_page(page)
    app.run()
    assert not app.exception, [e.value for e in app.exception]
    assert any("page-header" in m.value for m in app.markdown)


def test_calculator_reacts_to_inputs(app):
    app.switch_page("pages/calculator.py")
    app.run()
    app.selectbox[0].set_value("Established Low-Spend").run()
    assert not app.exception
    app.checkbox[0].check().run()
    assert not app.exception


def test_retention_filters_and_highlight(app):
    app.switch_page("pages/retention.py")
    app.run()
    app.selectbox[0].set_value("Segment").run()
    assert not app.exception
    app.multiselect[1].set_value(["Fiber optic"]).run()
    assert not app.exception
