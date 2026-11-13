"""Infrastructure Development Agent tests."""

from __future__ import annotations

import mesa
from shapely.geometry import Point

from app.agents.infrastructure_agent import InfrastructureDevelopmentAgent
from app.agents.model import RuntimeProject, UrbanAlphaModel
from app.baseline import baseline_valuation
from app.schemas import ProjectStatus


def test_infrastructure_agent_advances_under_construction():
    base = baseline_valuation(location="Whitefield", total_sqft=2400)
    infra = [{
        "project_id": "metro1",
        "name": "Metro Project",
        "source": "BMRCL",
        "type": "metro",
        "status": "UNDER_CONSTRUCTION",
        "construction_progress": 0.70,
        "funding": 0.90,
    }]
    m = UrbanAlphaModel(baseline=base, infrastructure=infra, years=3, seed=42)
    proj = m.projects[0]
    assert proj.status == ProjectStatus.UNDER_CONSTRUCTION.value

    # After step, construction advances towards operational
    m.infra_agent.step()
    # At 0.70 + ~0.35 = > 1.0, should become OPERATIONAL
    assert proj.status == ProjectStatus.OPERATIONAL.value
    assert any(e["status"] == ProjectStatus.OPERATIONAL.value for e in m._year_events)


def test_infrastructure_agent_delays_on_funding_shortfall():
    base = baseline_valuation(location="Whitefield", total_sqft=2400)
    infra = [{
        "project_id": "road1",
        "name": "Road Project",
        "source": "BDA",
        "type": "road",
        "status": "PROPOSED",
        "funding": 0.05,  # extreme funding shortfall
    }]
    # Run multiple steps with a seed that triggers funding delay
    m = UrbanAlphaModel(baseline=base, infrastructure=infra, years=5, seed=1)
    proj = m.projects[0]
    proj.funding = 0.05

    for _ in range(5):
        m.infra_agent.step()
        if proj.status == ProjectStatus.DELAYED.value:
            break

    # Should remain held or delayed, definitely NOT operational
    assert proj.status != ProjectStatus.OPERATIONAL.value
