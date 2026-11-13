"""Infrastructure Development Agent (v1.1, Phase 5).

Replaces the v1 deterministic status schedule with **constrained** project
progression. Each project carries funding, approval, land-acquisition and
construction-progress state; the agent decides per year whether a project
progresses, holds, delays or (in extreme funding failure) cancels.

By default the constraints are permissive (funding available, approvals
forthcoming) so progression is smooth and seeded-deterministic, matching the
intuition that most announced projects do advance. Delays and cancellations
are driven by funding falling below thresholds, which scenarios can force.
"""

from __future__ import annotations

import mesa

from app.schemas import ProjectStatus


# Status progression ladder (DELAYER/cancel are side states, not rungs).
_LADDER = [
    ProjectStatus.PROPOSED.value,
    ProjectStatus.APPROVED.value,
    ProjectStatus.UNDER_CONSTRUCTION.value,
    ProjectStatus.OPERATIONAL.value,
]


class InfrastructureDevelopmentAgent(mesa.Agent):
    """Advances infrastructure projects under funding/approval/land constraints."""

    def __init__(self, model: "mesa.Model"):
        super().__init__(model)
        # Per-project runtime fields are stored on the RuntimeProject records
        # themselves; this agent only reads/writes them via the model.

    # ------------------------------------------------------------------
    def step(self) -> None:
        rng = self.model.random
        year = self.model.current_year
        events: list[dict] = []
        for proj in self.model.projects:
            event = self._progress_project(proj, rng, year)
            if event:
                events.append(event)
        # Publish this year's status-change events to the model.
        self.model.set_infrastructure_events(events)

    # ------------------------------------------------------------------
    def _progress_project(self, proj, rng, year: int) -> dict | None:
        status = proj.status

        # Funding accrues; small noise. Under-construction/operational are funded.
        proj.funding = _clamp(proj.funding + rng.gauss(0.03, 0.02), 0.0, 1.0)

        if status == ProjectStatus.PROPOSED.value:
            return self._from_proposed(proj, rng, year)
        if status == ProjectStatus.APPROVED.value:
            return self._from_approved(proj, rng, year)
        if status == ProjectStatus.UNDER_CONSTRUCTION.value:
            return self._from_construction(proj, rng, year)
        # OPERATIONAL / DELAYED terminal-ish: no automatic promotion.
        return None

    # -- rung transitions ------------------------------------------------
    def _from_proposed(self, proj, rng, year: int) -> dict | None:
        # Needs funding above 0.4 and an approval to advance.
        if proj.funding > 0.4:
            # Approval likely but not guaranteed; seeded noise.
            if rng.random() < 0.85:
                proj.approved = True
                proj.status = ProjectStatus.APPROVED.value
                return _event(proj, ProjectStatus.APPROVED.value, year)
        elif proj.funding < 0.15 and rng.random() < 0.10:
            # Severe funding shortfall -> delay/stagnation.
            proj.status = ProjectStatus.DELAYED.value
            proj.delay_years += 1
            return _event(proj, ProjectStatus.DELAYED.value, year, detail="funding shortfall")
        return None

    def _from_approved(self, proj, rng, year: int) -> dict | None:
        # Needs land acquisition before construction starts.
        proj.land_acquisition = _clamp(proj.land_acquisition + 0.25 + rng.gauss(0.0, 0.05), 0.0, 1.0)
        if proj.land_acquisition >= 0.8:
            proj.construction_progress = 0.05
            proj.status = ProjectStatus.UNDER_CONSTRUCTION.value
            return _event(proj, ProjectStatus.UNDER_CONSTRUCTION.value, year)
        return None

    def _from_construction(self, proj, rng, year: int) -> dict | None:
        # Resume from a delay if one is pending.
        if proj.delay_years > 0:
            proj.delay_years -= 1
            return None
        # Progress builds up; once complete the project is operational.
        proj.construction_progress = _clamp(
            proj.construction_progress + 0.35 + rng.gauss(0.0, 0.04), 0.0, 1.2
        )
        if proj.construction_progress >= 1.0:
            proj.status = ProjectStatus.OPERATIONAL.value
            return _event(proj, ProjectStatus.OPERATIONAL.value, year)
        # Rare funding-driven delay for in-flight projects.
        if proj.funding < 0.25 and rng.random() < 0.15:
            proj.delay_years += 1
            return _event(proj, ProjectStatus.UNDER_CONSTRUCTION.value, year, detail="construction delay")
        return None


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _event(proj, status: str, year: int, detail: str = "") -> dict:
    e = {
        "project_id": proj.project_id,
        "name": proj.name,
        "type": proj.type,
        "status": status,
        "year": year,
    }
    if detail:
        e["detail"] = detail
    return e
