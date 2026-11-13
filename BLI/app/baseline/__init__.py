"""Baseline valuation seed.

Wraps the pre-existing CatBoost house/plot price model as the Year-0 anchor.
The rest of the system (agents, simulation, future valuation) initialises every
expectation relative to the output of :func:`baseline_valuation`.
"""

from app.baseline.seed import BaselineSeed, get_seed, baseline_valuation

__all__ = ["BaselineSeed", "get_seed", "baseline_valuation"]
