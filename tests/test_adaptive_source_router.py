"""C1C: all tests fabricated; no market data or provider calls."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from swing_trading.incremental_cache import Provider
from swing_trading.adaptive_source_router import (
    DiagnosticObservation, PriceBasis, PriceUnit, ProviderProbe, RouteMode,
    SourceTask, candidate_precedence, preview_adaptive_route, RouteDecision,
)

NOW = datetime(2026, 11, 7, 3, 0, tzinfo=timezone.utc)


def candidate(provider=Provider.DNSE, task=SourceTask.D1_OHLCV, **changes):
    d = dict(provider=provider, task=task, price_basis=PriceBasis.RAW,
             price_unit=PriceUnit.VND, observed_at_utc=NOW-timedelta(minutes=2),
             valid_until_utc=NOW+timedelta(minutes=10), native_ohlcv=True,
             complete=True, non_provisional=True, clock_and_calendar_checked=True,
             price_basis_checked=True, volume_scope_checked=True,
             corporate_action_checked=True, ohlc_invariants_checked=True,
             comparative_quality_checked=True)
    d.update(changes)
    return DiagnosticObservation(**d)


def probe(provider, ms=1000, ok=True, task=SourceTask.D1_OHLCV, at=NOW):
    return ProviderProbe(provider, task, at, ok, ms)


def select(*obs, task=SourceTask.D1_OHLCV, basis=PriceBasis.RAW, probes=(), **kw):
    return preview_adaptive_route(task=task, price_basis=basis, as_of_utc=NOW,
                                  observations=tuple(obs), probes=tuple(probes), **kw)


class AdaptiveRouterTests(unittest.TestCase):
    def test_task_specific_precedence(self):
        self.assertEqual(candidate_precedence(SourceTask.D1_OHLCV),
                         (Provider.DNSE,Provider.SSI,Provider.VCBS))
        self.assertEqual(candidate_precedence(SourceTask.M1_OHLCV),(Provider.SSI,))

    def test_no_source_is_blocked(self):
        r=select()
        self.assertEqual(r.mode,RouteMode.BLOCKED)
        self.assertEqual(len(r.rejected),3)
        self.assertIsNone(r.selected)

    def test_dnse_preferred_d1_when_all_diagnostics_pass(self):
        r=select(candidate(Provider.SSI),candidate(Provider.DNSE),candidate(Provider.VCBS))
        self.assertEqual(r.selected,Provider.DNSE)
        self.assertEqual(r.ordered_eligible,(Provider.DNSE,Provider.SSI,Provider.VCBS))
        self.assertTrue(r.reference_only)
        self.assertFalse(r.source_authority_verified)
        self.assertFalse(r.indicator_eligible)
        self.assertFalse(r.persistence_authorized)
        self.assertFalse(r.trading_actionable)

    def test_ssi_m1_even_when_dnse_and_vcbs_claim_minute(self):
        obs=[candidate(p,SourceTask.M1_OHLCV) for p in Provider]
        r=select(*obs,task=SourceTask.M1_OHLCV)
        self.assertEqual(r.selected,Provider.SSI)
        self.assertEqual(r.ordered_eligible,(Provider.SSI,))
        self.assertEqual({x[0] for x in r.rejected},{Provider.DNSE,Provider.VCBS})

    def test_intraday_without_ssi_blocked_not_vcbs_price_points(self):
        r=select(candidate(Provider.VCBS,SourceTask.M1_OHLCV),task=SourceTask.M1_OHLCV)
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_dnse_fail_falls_back_to_ssi_diagnostic_only(self):
        r=select(candidate(Provider.DNSE,error_code="DOWNSTREAM_UNAVAILABLE"),candidate(Provider.SSI))
        self.assertEqual(r.selected,Provider.SSI)
        self.assertIn((Provider.DNSE,"SOURCE_ERROR:DOWNSTREAM_UNAVAILABLE"),r.rejected)

    def test_ssi_fails_eligibility_vcbs_can_be_reference_candidate(self):
        r=select(candidate(Provider.DNSE,price_basis=PriceBasis.ADJUSTED),
                 candidate(Provider.SSI,native_ohlcv=False),candidate(Provider.VCBS))
        self.assertEqual(r.selected,Provider.VCBS)
        self.assertFalse(r.trading_actionable)

    def test_adjusted_dnse_does_not_silently_satisfy_raw(self):
        r=select(candidate(Provider.DNSE,price_basis=PriceBasis.ADJUSTED))
        self.assertEqual(r.mode,RouteMode.BLOCKED)
        self.assertIn("PRICE_BASIS_MISMATCH",str(r.rejected))

    def test_raw_not_silent_adjusted(self):
        r=select(candidate(Provider.SSI),basis=PriceBasis.ADJUSTED)
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_adjusted_allowed_only_with_explicit_matching_checked_basis(self):
        a=candidate(Provider.DNSE,price_basis=PriceBasis.ADJUSTED)
        r=select(a,basis=PriceBasis.ADJUSTED)
        self.assertEqual(r.selected,Provider.DNSE)
        self.assertFalse(r.indicator_eligible)

    def test_thousand_vnd_no_implicit_conversion(self):
        r=select(candidate(Provider.VCBS,price_unit=PriceUnit.THOUSAND_VND))
        self.assertEqual(r.mode,RouteMode.BLOCKED)
        self.assertIn("PRICE_UNIT_NOT_NORMALIZED_TO_VND",str(r.rejected))

    def test_vcbs_shs_volume_scope_mismatch_blocked(self):
        r=select(candidate(Provider.VCBS,volume_scope_checked=False))
        self.assertEqual(r.mode,RouteMode.BLOCKED)
        self.assertIn("VOLUME_SCOPE_UNVERIFIED",str(r.rejected))

    def test_vcbs_invalid_vgi_ohlc_blocked(self):
        r=select(candidate(Provider.VCBS,ohlc_invariants_checked=False))
        self.assertEqual(r.mode,RouteMode.BLOCKED)
        self.assertIn("INVALID_OR_UNVERIFIED_OHLC",str(r.rejected))

    def test_no_provisional_open_bar_in_confirmed_route(self):
        r=select(candidate(Provider.DNSE,non_provisional=False))
        self.assertEqual(r.mode,RouteMode.BLOCKED)
        self.assertIn("OPEN_BAR_NOT_FINAL",str(r.rejected))

    def test_incomplete_mcp_page_blocked(self):
        r=select(candidate(Provider.SSI,complete=False))
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_no_calendar_or_clock_gate(self):
        r=select(candidate(Provider.SSI,clock_and_calendar_checked=False))
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_unchecked_corporate_action_history_blocked(self):
        r=select(candidate(Provider.DNSE,corporate_action_checked=False))
        self.assertIn("CORPORATE_ACTION_REVISION_UNVERIFIED",str(r.rejected))

    def test_unchecked_price_basis_blocked(self):
        r=select(candidate(Provider.DNSE,price_basis_checked=False))
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_cross_provider_parity_gate(self):
        r=select(candidate(Provider.VCBS,comparative_quality_checked=False))
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_old_snapshot_blocked(self):
        r=select(candidate(Provider.DNSE,valid_until_utc=NOW-timedelta(seconds=1)))
        self.assertEqual(r.mode,RouteMode.BLOCKED)
        self.assertIn("SOURCE_FRESHNESS_UNCONFIRMED",str(r.rejected))

    def test_future_snapshot_blocked(self):
        r=select(candidate(Provider.DNSE,observed_at_utc=NOW+timedelta(minutes=1),valid_until_utc=NOW+timedelta(minutes=5)))
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_bad_observation_clock_order_rejected(self):
        with self.assertRaises(ValueError):
            candidate(valid_until_utc=NOW-timedelta(minutes=10))

    def test_duplicate_provider_cannot_overwrite(self):
        with self.assertRaises(ValueError):
            select(candidate(Provider.DNSE),candidate(Provider.DNSE))

    def test_task_mismatch_not_promoted(self):
        r=select(candidate(Provider.DNSE,task=SourceTask.M1_OHLCV))
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_strict_bool_type_not_truthy_one(self):
        with self.assertRaises(TypeError):
            candidate(native_ohlcv=1)

    def test_missing_explicit_basis_rejected(self):
        with self.assertRaises(TypeError):
            candidate(price_basis="RAW")

    def test_bad_task_type_rejected(self):
        with self.assertRaises(TypeError):
            candidate_precedence("D1")

    def test_no_automatic_trading_rights_even_if_caller_claims_all_checks(self):
        r=select(*(candidate(p) for p in Provider))
        for field in ("source_authority_verified","rights_verified", "persistence_authorized",
                      "indicator_eligible","trading_actionable","live_adapter_deployed"):
            self.assertFalse(getattr(r,field))
            with self.assertRaises(ValueError):
                replace(r,**{field:True})

    def test_reference_only_false_is_forbidden(self):
        with self.assertRaises(ValueError):
            replace(select(candidate()),reference_only=False)

    def test_bad_probe_future_and_negative_rejected(self):
        with self.assertRaises(ValueError):
            probe(Provider.DNSE,ms=-1)
        with self.assertRaises(ValueError):
            probe(Provider.DNSE,ms=0)

    def test_without_comparable_samples_default_precedence_remains(self):
        p=(probe(Provider.SSI,ms=10),)
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.DNSE)
        self.assertEqual(r.ranking_reason,"TASK_SPECIFIC_DEFAULT_WHILE_PERFORMANCE_INSUFFICIENT")

    def test_latency_reordering_only_after_enough_comparable_samples(self):
        p=tuple(probe(Provider.DNSE,ms=2000+i,at=NOW-timedelta(seconds=10-i)) for i in range(5)) + tuple(
            probe(Provider.SSI,ms=500+i,at=NOW-timedelta(seconds=10-i)) for i in range(5))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.SSI)
        self.assertEqual(r.ordered_eligible,(Provider.SSI,Provider.DNSE))
        self.assertIn("LATENCY",r.ranking_reason)

    def test_speed_may_prefer_dnse_when_measured_fast(self):
        p=tuple(probe(Provider.DNSE,ms=1100,at=NOW-timedelta(seconds=i)) for i in range(5))+tuple(
            probe(Provider.SSI,ms=1550,at=NOW-timedelta(seconds=i)) for i in range(5))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.DNSE)

    def test_failure_penalty_deprioritizes_unstable_but_not_circuit_open(self):
        d=tuple(probe(Provider.DNSE,ms=600,ok=i%2==0,at=NOW-timedelta(seconds=6-i)) for i in range(6))
        s=tuple(probe(Provider.SSI,ms=1300,at=NOW-timedelta(seconds=6-i)) for i in range(6))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=d+s)
        self.assertEqual(r.selected,Provider.SSI)

    def test_three_consecutive_failures_circuit(self):
        p=tuple(probe(Provider.DNSE,ok=False,ms=1200,at=NOW-timedelta(seconds=2-i)) for i in range(3))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.SSI)
        self.assertIn("RECENT_FAILURE_CIRCUIT_OPEN",str(r.rejected))

    def test_circuit_expired_after_cooldown(self):
        p=tuple(probe(Provider.DNSE,ok=False,ms=1200,at=NOW-timedelta(minutes=20,seconds=i)) for i in range(3))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.DNSE)

    def test_stale_probes_ignore_and_use_default(self):
        p=tuple(probe(Provider.DNSE,ms=3000,at=NOW-timedelta(hours=3,seconds=i)) for i in range(5))+tuple(
            probe(Provider.SSI,ms=200,at=NOW-timedelta(hours=3,seconds=i)) for i in range(5))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.DNSE)

    def test_m1_probes_do_not_affect_d1_ranking(self):
        p=tuple(probe(Provider.DNSE,ms=3000,task=SourceTask.M1_OHLCV) for _ in range(5))+tuple(
            probe(Provider.SSI,ms=200,task=SourceTask.M1_OHLCV) for _ in range(5))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.DNSE)

    def test_probe_in_future_ignored(self):
        p=tuple(probe(Provider.DNSE,ms=3000,at=NOW+timedelta(seconds=i+1)) for i in range(5))+tuple(
            probe(Provider.SSI,ms=200,at=NOW+timedelta(seconds=i+1)) for i in range(5))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.DNSE)

    def test_early_reorder_when_only_one_provider_eligible_disallowed(self):
        p=tuple(probe(Provider.SSI,ms=3000,at=NOW-timedelta(seconds=i)) for i in range(5))
        r=select(candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.SSI)
        self.assertIn("INSUFFICIENT",r.ranking_reason)

    def test_rejected_provider_bad_quality_never_reenters_by_speed(self):
        p=tuple(probe(Provider.DNSE,ms=5,at=NOW-timedelta(seconds=i)) for i in range(10))+tuple(
            probe(Provider.SSI,ms=3000,at=NOW-timedelta(seconds=i)) for i in range(10))
        r=select(candidate(Provider.DNSE,comparative_quality_checked=False),candidate(Provider.SSI),probes=p)
        self.assertEqual(r.selected,Provider.SSI)

    def test_no_eligible_even_with_thousands_of_fast_probes(self):
        p=tuple(probe(Provider.DNSE,ms=10) for _ in range(100))
        r=select(candidate(Provider.DNSE,complete=False),probes=p)
        self.assertEqual(r.mode,RouteMode.BLOCKED)

    def test_bounded_sample_ranking(self):
        p=tuple(probe(Provider.DNSE,ms=500,at=NOW-timedelta(minutes=50,seconds=i)) for i in range(90))
        p+=tuple(probe(Provider.SSI,ms=1000,at=NOW-timedelta(seconds=i)) for i in range(10))
        r=select(candidate(Provider.DNSE),candidate(Provider.SSI),probes=p,max_samples=10)
        self.assertEqual(r.selected,Provider.DNSE)

    def test_invalid_sample_configuration_rejected(self):
        with self.assertRaises(ValueError):
            select(candidate(),minimum_comparable_samples=1)
        with self.assertRaises(ValueError):
            select(candidate(),max_samples=2)


if __name__=='__main__':
    unittest.main()
