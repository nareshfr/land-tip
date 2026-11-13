"""Market Dynamics Engine.

The central economic mechanism that connects household demand, developer
decisions and available land supply into a single market pressure term, then
converts that pressure plus calibration parameters into an annual land-price
growth rate — decomposed for explainability and kept free of double counting.

    dynamics.py - MarketDynamicsEngine
"""

from app.market.dynamics import MarketDynamicsEngine, MarketState, YearGrowth

__all__ = ["MarketDynamicsEngine", "MarketState", "YearGrowth"]
