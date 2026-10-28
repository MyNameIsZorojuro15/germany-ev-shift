"""The parser must reconcile to KBA's own totals, or nothing built on it can be trusted."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import parse_kba as P  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "fz8_202609.xlsx"


@pytest.fixture(scope="module")
def sep2026():
    return P.parse_file(FIX)


def test_brands_add_up_to_kba_total(sep2026):
    brands, _ = sep2026
    total = brands[brands.is_total].iloc[0]
    parts = brands[~brands.is_total][["total", "bev", "phev"]].sum()
    assert (parts.total, parts.bev, parts.phev) == (total.total, total.bev, total.phev)


def test_known_values_september_2026(sep2026):
    brands, states = sep2026
    bmw = brands.set_index("name").loc["BMW"]
    assert (bmw.total, bmw.bev, bmw.phev) == (18924, 4751, 2351)
    assert brands[brands.is_total].iloc[0].bev == 88599          # KBA FZ 8.4, Elektro (BEV), September 2026
    assert states.set_index("name").loc["Bayern"].bev == 18238


def test_states_add_up_to_germany(sep2026):
    _, states = sep2026
    de = states[states.is_total].iloc[0]
    assert states[~states.is_total].total.sum() == de.total


@pytest.mark.parametrize("raw, value", [("-", 0), ("1.234", 1234), (None, 0), ("12552", 12552)])
def test_number_parsing(raw, value):
    assert P._num(raw) == value


def test_every_downloaded_month_reconciles():
    clean = ROOT / "data" / "clean" / "brand_month.csv"
    if not clean.exists():
        pytest.skip("run src/parse_kba.py first")
    df = pd.read_csv(clean)
    for month, g in df.groupby("month"):
        total = g[g.is_total].iloc[0]
        parts = g[~g.is_total][["total", "bev", "phev"]].sum()
        assert (parts.total, parts.bev) == (total.total, total.bev), month
