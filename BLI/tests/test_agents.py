"""Mesa model + cluster tests."""

from __future__ import annotations

from shapely.geometry import Point

from app.agents.model import UrbanAlphaModel
from app.baseline import baseline_valuation
from app.spatial.localities import locality_centroid


def _model(years=3, households=20, developers=3, seed=7):
    base = baseline_valuation(location="Whitefield", total_sqft=2400)
    infra = [
        {"project_id": "metro", "name": "Whitefield Metro", "source": "BMRCL",
         "type": "metro", "status": "UNDER_CONSTRUCTION",
         "announcement_date": "2020-01-01", "geometry": "POINT (77.7499 12.9696)"},
    ]
    m = UrbanAlphaModel(baseline=base, infrastructure=infra, years=years,
                       households=households, developers=developers, seed=seed)
    m.set_within_2km({"metro"})
    return m


def test_model_records_year_zero_snapshot():
    m = _model(years=3)
    # Year 0 is recorded at construction time.
    assert m.timeline[0]["year"] == 0
    assert m.timeline[0]["land_value_index"] == 1.0
    assert m.timeline[0]["interest_rate"] == 8.5


def test_model_step_advances_year_and_timeline():
    m = _model(years=4)
    for _ in range(4):
        m.step()
    assert len(m.timeline) == 5  # Year 0 + 4 steps
    assert m.timeline[-1]["year"] == 4
    # Metro becomes operational within the horizon -> active infra grows.
    assert m.timeline[-1]["active_infrastructure"] >= 1


def test_model_is_deterministic_with_seed():
    def run():
        m = _model(years=3, seed=99)
        for _ in range(3):
            m.step()
        return m.timeline[-1]["land_value_index"]
    assert run() == run()


def test_demand_utility_formula_components():
    m = _model(years=2, households=10, developers=2)
    # Year-0 baseline utility was computed; first step uses the formula.
    m.step()
    snap = m.timeline[-1]
    # mean demand utility is finite and recorded.
    assert isinstance(snap["mean_demand_utility"], float)
    assert isinstance(snap["mean_developer_profit_margin"], float)
