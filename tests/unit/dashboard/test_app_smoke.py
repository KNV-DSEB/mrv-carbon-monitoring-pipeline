"""Smoke test: the Streamlit app runs end to end with no exceptions.

Streamlit's ``AppTest`` executes ``dashboard/app.py`` headlessly against the
committed ``data/demo/`` snapshots — which is exactly the spec-08 guarantee: the
dashboard renders with **no Google Earth Engine credentials and no network**.
The UI itself isn't unit-tested; this proves it actually runs.
"""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[3] / "dashboard" / "app.py"


def test_app_runs_credential_free_without_exceptions():
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()

    assert not at.exception, [str(e.value) for e in at.exception]

    # The honesty banner is always rendered, and says what this is NOT.
    assert at.warning, "the honesty banner must always be present"
    assert "AWD" in at.warning[0].value

    # Three tabs (optical / SAR / cross-check) and the data tables that serve as
    # the contrast-relief channel for the charts.
    assert len(at.tabs) == 3
    assert len(at.dataframe) >= 3
