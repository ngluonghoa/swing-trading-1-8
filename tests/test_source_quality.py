"""P0.2 synthetic-only source revision and three-axis quality tests."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from swing_trading.market_data import InstrumentClass, MarketBarKey, PriceBasis, Timeframe
from swing_trading.source_quality import (
    CanonicalCandleV12, CoverageState, LifecycleState, ObservationOrigin,
    ObservationRevisionV12, ProviderObservationKeyV12, QualityState,
    SourceEvidence, resolve_as_known,
)

T = datetime(2026, 11, 6, 2, 0, tzinfo=timezone.utc)
m = lambda n: T + timedelta(minutes=n)


def market_key():
    return MarketBarKey(
        "HOSE:ABC:registry-v1", "HOSE", InstrumentClass.STOCK, Timeframe.M15,
        "fixture-session-A", T, PriceBasis.RAW, "fixture-calendar-v1", "fixture-aggregation-v1",
    )


def candle(**changes):
    key = market_key()
    obs = ProviderObservationKeyV12("SWING_1_8", key, "FIXTURE", ObservationOrigin.NATIVE, "stream-1")
    rev = ObservationRevisionV12(obs, "r1", "adjust-v1", "ingest-v1", m(15), m(20))
    src = SourceEvidence(
        "synthetic://bars", "fixture-data-v1", "record-1",
        True, True, True, True,
    )
    values = dict(
        market_bar_key=key, observation_key=obs, observation_revision=rev,
        bar_end_utc=m(15),
        open=Decimal("10"), high=Decimal("12"), low=Decimal("9"), close=Decimal("11"),
        volume=0, matched_value=None, observed_minutes=15, expected_minutes=15,
        source_event_ids=("event-1",), raw_digest_sha256="a" * 64,
        normalized_digest_sha256="b" * 64, retrieved_at_utc=m(20),
        verified_at_utc=m(25), lifecycle_state=LifecycleState.CLOSED,
        coverage_state=CoverageState.COMPLETE, quality_state=QualityState.VERIFIED,
        calendar_cutoff_verified=True, quality_flags=frozenset(), provenance=src,
    )
    values.update(changes)
    return CanonicalCandleV12(**values)


class SourceQualityTests(unittest.TestCase):
    def test_provenance_identity_is_separate_from_bar_identity(self):
        c = candle()
        new_obs = replace(c.observation_key, provider_id="OTHER")
        self.assertEqual(new_obs.market_bar_key, c.market_bar_key)
        self.assertNotEqual(new_obs, c.observation_key)
        with self.assertRaises(ValueError):
            replace(c, observation_key=new_obs)

    def test_revision_must_match_provider_observation(self):
        c = candle()
        wrong_revision = replace(c.observation_revision, observation_key=replace(
            c.observation_key, source_stream_id="another"
        ))
        with self.assertRaises(ValueError):
            replace(c, observation_revision=wrong_revision)

    def test_zero_volume_is_recorded_zero_not_absence(self):
        c = candle()
        self.assertTrue(c.confirmation_prerequisites(m(30)))
        self.assertEqual(c.volume, 0)
        self.assertFalse(replace(c, volume=None).confirmation_prerequisites(m(30)))

    def test_three_independent_quality_axes_fail_closed(self):
        c = candle()
        for variant in (
            replace(c, lifecycle_state=LifecycleState.OPEN),
            replace(c, coverage_state=CoverageState.SPARSE_UNVERIFIED),
            replace(c, coverage_state=CoverageState.UNKNOWN),
            replace(c, coverage_state=CoverageState.RANGE_PARTIAL),
            replace(c, coverage_state=CoverageState.INVALID),
            replace(c, quality_state=QualityState.WARN),
            replace(c, quality_state=QualityState.UNVERIFIED),
            replace(c, quality_state=QualityState.BLOCKED),
        ):
            with self.subTest(variant=(variant.lifecycle_state, variant.coverage_state, variant.quality_state)):
                self.assertFalse(variant.confirmation_prerequisites(m(30)))

    def test_incomplete_or_unknown_minutes_and_partial_policy(self):
        c = candle()
        self.assertFalse(replace(c, observed_minutes=13).confirmation_prerequisites(m(30)))
        partial = replace(c, coverage_state=CoverageState.SESSION_PARTIAL, observed_minutes=13)
        self.assertFalse(partial.confirmation_prerequisites(m(30)))
        documented = replace(partial, provenance=replace(c.provenance, session_partial_policy_verified=True))
        self.assertTrue(documented.confirmation_prerequisites(m(30)))
        self.assertFalse(replace(c, coverage_state=CoverageState.SPARSE_UNVERIFIED,
                                 observed_minutes=None).confirmation_prerequisites(m(30)))

    def test_source_permissions_and_semantics_are_never_assumed(self):
        c = candle()
        for name in ("entitlement_verified", "timestamp_semantics_verified",
                     "price_basis_verified", "coverage_policy_verified"):
            with self.subTest(name=name):
                evidence = replace(c.provenance, **{name: False})
                self.assertFalse(replace(c, provenance=evidence).confirmation_prerequisites(m(30)))

    def test_unverified_cutoff_unknown_price_basis_and_flags(self):
        c = candle()
        self.assertFalse(replace(c, calendar_cutoff_verified=False).confirmation_prerequisites(m(30)))
        unknown_key = replace(c.market_bar_key, price_basis=PriceBasis.UNKNOWN)
        unknown_obs = replace(c.observation_key, market_bar_key=unknown_key)
        unknown_rev = replace(c.observation_revision, observation_key=unknown_obs)
        self.assertFalse(replace(c, market_bar_key=unknown_key, observation_key=unknown_obs,
                                 observation_revision=unknown_rev).confirmation_prerequisites(m(30)))
        self.assertFalse(replace(c, quality_flags=frozenset({"SOURCE_TIME_AMBIGUOUS"}))
                         .confirmation_prerequisites(m(30)))

    def test_future_verification_and_revisions_do_not_leak(self):
        c = candle()
        self.assertFalse(c.confirmation_prerequisites(m(24)))
        self.assertFalse(c.confirmation_prerequisites(m(14)))
        later_revision = replace(c.observation_revision,
                                 source_revision_or_payload_digest="r2",
                                 first_known_time_utc=m(40), retrieved_at_utc=m(40))
        later_candle = replace(c, observation_revision=later_revision,
                              retrieved_at_utc=m(40), verified_at_utc=m(42))
        self.assertFalse(later_candle.confirmation_prerequisites(m(30)))
        self.assertEqual(resolve_as_known(c.market_bar_key, (c, later_candle), m(30)).selected, c)
        result = resolve_as_known(c.market_bar_key, (c, later_candle), m(50))
        self.assertIsNone(result.selected)
        self.assertEqual(result.reason, "SOURCE_OR_REVISION_CONFLICT")
        self.assertFalse(result.confirmation_prerequisites(m(50)))

    def test_two_providers_are_conflict_not_silent_preference(self):
        c = candle()
        alternate_obs = replace(c.observation_key, provider_id="ANOTHER_FIXTURE")
        alternate_rev = replace(c.observation_revision, observation_key=alternate_obs)
        other = replace(c, observation_key=alternate_obs, observation_revision=alternate_rev)
        x = resolve_as_known(c.market_bar_key, (c, other), m(30))
        self.assertEqual(x.visible_candidate_count, 2)
        self.assertIsNone(x.selected)
        self.assertFalse(x.confirmation_prerequisites(m(30)))

    def test_no_visible_revision_is_not_no_trade(self):
        c = candle()
        x = resolve_as_known(c.market_bar_key, (c,), m(10))
        self.assertEqual(x.reason, "NO_VISIBLE_REVISION")
        self.assertIsNone(x.selected)

    def test_strict_validation_of_ohlcv_and_digests(self):
        with self.assertRaises(TypeError):
            candle(open=10.0)
        with self.assertRaises(ValueError):
            candle(open=Decimal("NaN"))
        with self.assertRaises(ValueError):
            candle(high=Decimal("8"))
        with self.assertRaises(ValueError):
            candle(volume=-1)
        with self.assertRaises(ValueError):
            candle(volume=True)
        with self.assertRaises(ValueError):
            candle(raw_digest_sha256="short")
        with self.assertRaises(ValueError):
            candle(matched_value=Decimal("Infinity"))

    def test_revision_identity_retrieval_and_time_validation(self):
        c = candle()
        with self.assertRaises(ValueError):
            replace(c, retrieved_at_utc=m(40))
        with self.assertRaises(ValueError):
            replace(c.observation_revision, first_known_time_utc=m(21))
        with self.assertRaises(ValueError):
            replace(c, verified_at_utc=m(19))
        with self.assertRaises(ValueError):
            replace(c, bar_end_utc=T)

    def test_invalid_enums_or_conflicting_market_keys(self):
        c = candle()
        with self.assertRaises(TypeError):
            replace(c, quality_state="VERIFIED")
        with self.assertRaises(TypeError):
            replace(c.observation_key, origin="NATIVE")
        with self.assertRaises(TypeError):
            replace(c, calendar_cutoff_verified=1)
        with self.assertRaises(TypeError):
            replace(c.provenance, entitlement_verified=1)
        with self.assertRaises(ValueError):
            resolve_as_known(c.market_bar_key, (replace(
                c, market_bar_key=replace(c.market_bar_key, calendar_version="other")),), m(30))
        with self.assertRaises(TypeError):
            resolve_as_known(c.market_bar_key, [c], m(30))

    def test_unknown_scope_is_not_verified(self):
        c = candle()
        with self.assertRaises(ValueError):
            replace(c.provenance, source_snapshot_id="")
        with self.assertRaises(ValueError):
            replace(c.observation_key, source_stream_id="")
        with self.assertRaises(ValueError):
            replace(c.observation_revision, adjustment_revision="")
        with self.assertRaises(ValueError):
            replace(c, quality_flags=frozenset({""}))


if __name__ == "__main__":
    unittest.main()
