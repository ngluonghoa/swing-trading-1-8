"""Fail-closed initial signal engine. All real detector formulas remain SPEC_PENDING."""
from datetime import datetime

from .contracts import SignalDecision, DecisionStatus, Strategy, ZONE_IDS
from .replay import require_utc


def evaluate_unimplemented_zones(strategy: Strategy, as_of_utc: datetime) -> tuple[SignalDecision, ...]:
    """Never emit NOT_DETECTED or DETECTED for an unimplemented zone."""
    require_utc(as_of_utc)
    return tuple(
        SignalDecision(zone_id=zone, strategy=strategy, status=DecisionStatus.UNVERIFIED)
        for zone in ZONE_IDS
    )
