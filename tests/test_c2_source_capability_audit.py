"""C2A disconnected, synthetic capability/shape tests. No MCP or price storage."""
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone, timedelta

from swing_trading.incremental_cache import Provider
from swing_trading.cache_fetch_planner import SourceCapability
from swing_trading.c2_source_capability_audit import (
    ConnectedEndpoint as E, DataNeed as N, FetchBoundary as B,
    RefreshVerdict as V, ProbeState as S, EndpointContract,
    InMemoryShapeAudit, endpoint_contract, advise_connected_refresh,
    conservative_c1_m1_capability,
    audit_transient_response, require_authorized_c2_source,
    MAX_SERIALIZED_RESPONSE_BYTES,
)

NOW = datetime(2026, 11, 7, 4, 0, tzinfo=timezone.utc)


def ssi_row(**changes):
    row = dict(trading_date="06/11/2026", open=10000, high=10200,
               low=9900, close=10100, volume=12300, symbol="FPT")
    row.update(changes)
    return row


def ssi_d1(*rows, status="ok"):
    return {"status": status, "data": {"stocks": list(rows)}, "error": None}


def ssi_minute(*rows, status="ok"):
    return {"status": status, "data": {"ticks": list(rows)}, "error": None}


def dnse(*rows):
    data = {k: [] for k in ("t", "o", "h", "l", "c", "v")}
    for row in rows:
        for key in data:
            data[key].append(row[key])
    return {"data": data}


def dnse_row(t=1783414800, **changes):
    row = dict(t=t, o=10.0, h=10.2, l=9.9, c=10.1, v=12300)
    row.update(changes)
    return row


def vcbs_row(**changes):
    row = dict(tradingDate="2026-11-06", priceBasis="raw", price_unit="VND",
               volumeScope="matched", openPrice=10000, highPrice=10200,
               lowPrice=9900, closePrice=10100, volume=12300)
    row.update(changes)
    return row


def run(ep, payload):
    return audit_transient_response(ep, payload, checked_at_utc=NOW)


class EndpointContractTests(unittest.TestCase):
    def test_exactly_seven_known_surfaces(self):
        self.assertEqual(len(tuple(E)), 7)

    def test_every_contract_provider_matches(self):
        expected = {E.SSI_D1_DETAILED:Provider.SSI, E.SSI_INTRADAY_SESSION:Provider.SSI,
                    E.SSI_INTRADAY_LATEST:Provider.SSI, E.DNSE_D1_HISTORY:Provider.DNSE,
                    E.VCBS_D1_WINDOW:Provider.VCBS, E.VCBS_INTRADAY_PRICE_POINTS:Provider.VCBS,
                    E.VCBS_QUOTE_BATCH:Provider.VCBS}
        for ep, provider in expected.items():
            with self.subTest(ep=ep): self.assertEqual(endpoint_contract(ep).provider, provider)

    def test_only_vcbs_daily_exposes_calendar_window(self):
        self.assertEqual([ep for ep in E if endpoint_contract(ep).bounded_calendar_dates],
                         [E.VCBS_D1_WINDOW])

    def test_all_surfaces_no_changed_since_revision_cursor(self):
        for ep in E:
            with self.subTest(ep=ep):
                c = endpoint_contract(ep)
                self.assertFalse(c.source_change_cursor)
                self.assertFalse(c.exact_subday_range)
                self.assertFalse(c.vendor_revision_provenance)

    def test_no_surface_qualified_minute_or_entitled(self):
        for ep in E:
            with self.subTest(ep=ep):
                c = endpoint_contract(ep)
                self.assertFalse(c.qualified_minute_ohlcv)
                self.assertFalse(c.historical_retention_authorized)
                self.assertFalse(c.exchange_freshness_verified)
                self.assertFalse(c.trading_actionable)

    def test_price_units_differ_across_source_surfaces(self):
        self.assertEqual(endpoint_contract(E.DNSE_D1_HISTORY).price_units, "THOUSAND_VND")
        self.assertEqual(endpoint_contract(E.VCBS_QUOTE_BATCH).price_units, "THOUSAND_VND")
        self.assertEqual(endpoint_contract(E.VCBS_D1_WINDOW).price_units, "VND")

    def test_ssi_minute_session_is_candidate_not_qualified(self):
        c = endpoint_contract(E.SSI_INTRADAY_SESSION)
        self.assertEqual(c.need, N.MINUTE_OHLCV)
        self.assertEqual(c.boundary, B.WHOLE_SESSION)
        self.assertFalse(c.qualified_minute_ohlcv)

    def test_vcbs_minute_points_not_minute_ohlcv(self):
        self.assertEqual(endpoint_contract(E.VCBS_INTRADAY_PRICE_POINTS).need,
                         N.MINUTE_PRICE_REFERENCE)

    def test_latest_ssi_is_reference_not_minute_history(self):
        self.assertEqual(endpoint_contract(E.SSI_INTRADAY_LATEST).need, N.QUOTE_REFERENCE)

    def test_unknown_endpoint_fails_typecheck(self):
        with self.assertRaises(TypeError): endpoint_contract("vcbs_get_history.D")

    def test_cannot_promote_contract_by_dataclass_replacement(self):
        with self.assertRaises(ValueError):
            replace(endpoint_contract(E.DNSE_D1_HISTORY), historical_retention_authorized=True)
        with self.assertRaises(ValueError):
            replace(endpoint_contract(E.SSI_INTRADAY_SESSION), source_change_cursor=True)

    def test_contract_immutable(self):
        with self.assertRaises(FrozenInstanceError): endpoint_contract(E.VCBS_D1_WINDOW).provider = Provider.SSI


class RefreshAdviceTests(unittest.TestCase):
    def test_c1_minute_planner_ssi_is_full_session_not_windowed(self):
        self.assertIs(conservative_c1_m1_capability(E.SSI_INTRADAY_SESSION),
                      SourceCapability.FULL_SESSION)

    def test_c1_minute_planner_all_other_surfaces_unknown(self):
        for ep in E:
            if ep is E.SSI_INTRADAY_SESSION:
                continue
            with self.subTest(ep=ep):
                self.assertIs(conservative_c1_m1_capability(ep), SourceCapability.UNKNOWN)

    def test_c1_minute_planner_rejects_invented_endpoint(self):
        with self.assertRaises(TypeError): conservative_c1_m1_capability("SSI")

    def test_dnse_d1_cannot_shortcut_full_history(self):
        d = advise_connected_refresh(E.DNSE_D1_HISTORY, N.D1_OHLCV)
        self.assertEqual(d.verdict, V.REFETCH_FULL_HISTORY)
        self.assertFalse(d.supports_delta_from_last_change)

    def test_ssi_d1_bucket_not_precise_calendar_window(self):
        self.assertEqual(advise_connected_refresh(E.SSI_D1_DETAILED, N.D1_OHLCV).verdict,
                         V.REFETCH_COARSE_DAILY_RANGE)

    def test_vcbs_d1_has_calendar_bounded_request_not_revision_cursor(self):
        d = advise_connected_refresh(E.VCBS_D1_WINDOW, N.D1_OHLCV)
        self.assertEqual(d.verdict, V.REVALIDATE_DATE_WINDOW)
        self.assertFalse(d.supports_delta_from_last_change)

    def test_ssi_minute_refetches_whole_session(self):
        d = advise_connected_refresh(E.SSI_INTRADAY_SESSION, N.MINUTE_OHLCV)
        self.assertEqual(d.verdict, V.REFETCH_WHOLE_SESSION)

    def test_ssi_latest_cannot_replace_minute_history(self):
        self.assertEqual(advise_connected_refresh(E.SSI_INTRADAY_LATEST, N.MINUTE_OHLCV).verdict,
                         V.BLOCKED)

    def test_dnse_d1_cannot_replace_ssi_minute(self):
        self.assertEqual(advise_connected_refresh(E.DNSE_D1_HISTORY, N.MINUTE_OHLCV).verdict,
                         V.BLOCKED)

    def test_vcbs_price_point_cannot_replace_minute_ohlcv(self):
        self.assertEqual(advise_connected_refresh(E.VCBS_INTRADAY_PRICE_POINTS,N.MINUTE_OHLCV).verdict,
                         V.BLOCKED)

    def test_vcbs_minute_price_reference_stays_reference(self):
        self.assertEqual(advise_connected_refresh(E.VCBS_INTRADAY_PRICE_POINTS,
                         N.MINUTE_PRICE_REFERENCE).verdict, V.REFERENCE_SNAPSHOT)

    def test_vcbs_batch_snapshot_not_candle(self):
        self.assertEqual(advise_connected_refresh(E.VCBS_QUOTE_BATCH,N.QUOTE_REFERENCE).verdict,
                         V.REFERENCE_SNAPSHOT)

    def test_every_endpoint_blocks_changed_since_requirement(self):
        for ep in E:
            with self.subTest(ep=ep):
                d = advise_connected_refresh(ep, endpoint_contract(ep).need,
                                             changed_since_required=True)
                self.assertEqual(d.verdict, V.BLOCKED)
                self.assertFalse(d.supports_delta_from_last_change)

    def test_every_advice_is_nonactionable(self):
        for ep in E:
            d = advise_connected_refresh(ep, endpoint_contract(ep).need)
            self.assertTrue(d.metadata_only)
            self.assertFalse(d.source_authority_verified)
            self.assertFalse(d.production_adapter_enabled)
            self.assertFalse(d.retention_authorized)
            self.assertFalse(d.trading_actionable)
            with self.assertRaises(ValueError): replace(d, retention_authorized=True)

    def test_bad_type_flags_rejected(self):
        with self.assertRaises(TypeError):
            advise_connected_refresh(E.SSI_D1_DETAILED,"D1_OHLCV")
        with self.assertRaises(TypeError):
            advise_connected_refresh(E.SSI_D1_DETAILED,N.D1_OHLCV,changed_since_required=1)


class TransientShapeTests(unittest.TestCase):
    def test_ssi_d1_known_schema(self):
        a=run(E.SSI_D1_DETAILED,ssi_d1(ssi_row()))
        self.assertEqual((a.state,a.observed_rows,a.rejected_rows), (S.SHAPE_RETURNED,1,0))

    def test_ssi_intraday_session_known_schema(self):
        a=run(E.SSI_INTRADAY_SESSION,ssi_minute(ssi_row(trading_date="11/06/2026 09:45:00")))
        self.assertEqual(a.state,S.SHAPE_RETURNED)
        self.assertEqual(a.provider,Provider.SSI)

    def test_ssi_latest_single(self):
        self.assertEqual(run(E.SSI_INTRADAY_LATEST,ssi_minute(ssi_row())).state,S.SHAPE_RETURNED)

    def test_ssi_latest_multiple_rows_rejected(self):
        self.assertEqual(run(E.SSI_INTRADAY_LATEST,ssi_minute(ssi_row(),ssi_row())).state,S.SCHEMA_REJECTED)

    def test_ssi_empty_not_qualified(self):
        self.assertEqual(run(E.SSI_D1_DETAILED,ssi_d1()).state,S.EMPTY_UNVERIFIED)

    def test_ssi_source_error_not_empty_success(self):
        self.assertEqual(run(E.SSI_D1_DETAILED,ssi_d1(status="error")).state,S.SOURCE_ERROR)

    def test_ssi_missing_candle_field_rejected(self):
        row=ssi_row();del row["high"]
        self.assertEqual(run(E.SSI_D1_DETAILED,ssi_d1(row)).state,S.SCHEMA_REJECTED)

    def test_ohlc_high_less_than_open_rejected(self):
        self.assertEqual(run(E.SSI_D1_DETAILED,ssi_d1(ssi_row(high=9800))).state,S.SCHEMA_REJECTED)

    def test_bool_volume_rejected(self):
        self.assertEqual(run(E.SSI_D1_DETAILED,ssi_d1(ssi_row(volume=True))).state,S.SCHEMA_REJECTED)

    def test_nonfinite_price_rejected(self):
        self.assertEqual(run(E.SSI_D1_DETAILED,ssi_d1(ssi_row(close="NaN"))).state,S.SCHEMA_REJECTED)

    def test_negative_volume_rejected(self):
        self.assertEqual(run(E.SSI_D1_DETAILED,ssi_d1(ssi_row(volume=-1))).state,S.SCHEMA_REJECTED)

    def test_dnse_day_arrays(self):
        a=run(E.DNSE_D1_HISTORY,dnse(dnse_row()))
        self.assertEqual((a.state,a.provider,a.observed_rows),(S.SHAPE_RETURNED,Provider.DNSE,1))

    def test_dnse_length_mismatch_fails_closed(self):
        p=dnse(dnse_row());p["data"]["c"].append(100)
        self.assertEqual(run(E.DNSE_D1_HISTORY,p).state,S.SCHEMA_REJECTED)

    def test_dnse_reordered_timestamps_rejected(self):
        p=dnse(dnse_row(t=200),dnse_row(t=100))
        self.assertEqual(run(E.DNSE_D1_HISTORY,p).state,S.SCHEMA_REJECTED)

    def test_dnse_equal_timestamps_rejected(self):
        p=dnse(dnse_row(t=200),dnse_row(t=200))
        self.assertEqual(run(E.DNSE_D1_HISTORY,p).state,S.SCHEMA_REJECTED)

    def test_dnse_no_dates_or_no_arrays(self):
        self.assertEqual(run(E.DNSE_D1_HISTORY,{"data":{}}).state,S.SCHEMA_REJECTED)

    def test_vcbs_raw_daily_shape(self):
        a=run(E.VCBS_D1_WINDOW,[vcbs_row()])
        self.assertEqual((a.state,a.observed_rows,a.rejected_rows),(S.SHAPE_RETURNED,1,0))

    def test_vcbs_missing_price_unit_fails(self):
        row=vcbs_row();del row["price_unit"]
        self.assertEqual(run(E.VCBS_D1_WINDOW,[row]).state,S.SCHEMA_REJECTED)

    def test_vcbs_adjusted_basis_rejected_as_raw(self):
        self.assertEqual(run(E.VCBS_D1_WINDOW,[vcbs_row(priceBasis="adjusted")]).state,S.SCHEMA_REJECTED)

    def test_vcbs_unverified_volume_scope_rejected(self):
        self.assertEqual(run(E.VCBS_D1_WINDOW,[vcbs_row(volumeScope="mixed")]).state,S.SCHEMA_REJECTED)

    def test_vcbs_open_gt_high_anomaly_detected(self):
        self.assertEqual(run(E.VCBS_D1_WINDOW,[vcbs_row(openPrice=10500)]).state,S.SCHEMA_REJECTED)

    def test_vcbs_d1_empty_unverified(self):
        self.assertEqual(run(E.VCBS_D1_WINDOW,[]).state,S.EMPTY_UNVERIFIED)

    def test_vcbs_price_series_shape(self):
        p={"data_status":"available","dataPoints":1,"series":[{"time":"09:15","price":10000}]}
        self.assertEqual(run(E.VCBS_INTRADAY_PRICE_POINTS,p).state,S.SHAPE_RETURNED)

    def test_vcbs_price_series_wrong_count(self):
        p={"data_status":"available","dataPoints":2,"series":[{"time":"09:15","price":10000}]}
        self.assertEqual(run(E.VCBS_INTRADAY_PRICE_POINTS,p).state,S.SCHEMA_REJECTED)

    def test_vcbs_price_series_missing_price(self):
        p={"data_status":"available","dataPoints":1,"series":[{"time":"09:15"}]}
        self.assertEqual(run(E.VCBS_INTRADAY_PRICE_POINTS,p).state,S.SCHEMA_REJECTED)

    def test_vcbs_no_data_not_false_price_zero(self):
        self.assertEqual(run(E.VCBS_INTRADAY_PRICE_POINTS,{"data_status":"no_data","series":[],"dataPoints":0}).state,S.EMPTY_UNVERIFIED)

    def test_vcbs_error_not_empty(self):
        self.assertEqual(run(E.VCBS_INTRADAY_PRICE_POINTS,{"data_status":"error"}).state,S.SOURCE_ERROR)

    def test_vcbs_quote_batch_shape_unverified(self):
        self.assertEqual(run(E.VCBS_QUOTE_BATCH,{"data_status":"complete","quotes":[]}).state,S.SCHEMA_REJECTED)

    def test_empty_ssi_wrong_type(self):
        self.assertEqual(run(E.SSI_INTRADAY_SESSION,{"status":"ok","data":{"ticks":"not list"}}).state,S.SCHEMA_REJECTED)

    def test_payload_nonserializable_rejected(self):
        with self.assertRaises(ValueError):run(E.VCBS_D1_WINDOW,[{1,2}])

    def test_payload_too_large_rejected(self):
        with self.assertRaises(ValueError):run(E.VCBS_D1_WINDOW,[{"long":"x" * MAX_SERIALIZED_RESPONSE_BYTES}])

    def test_wrong_clock_rejected(self):
        with self.assertRaises(ValueError):
            audit_transient_response(E.SSI_D1_DETAILED,ssi_d1(),checked_at_utc=NOW.replace(tzinfo=None))

    def test_metadata_response_does_not_contain_market_values(self):
        p=ssi_d1(ssi_row(close=10101));a=run(E.SSI_D1_DETAILED,p)
        s=repr(a)
        self.assertNotIn("10101",s)
        self.assertNotIn("FPT",s)
        self.assertGreater(a.approx_serialized_bytes,0)

    def test_privileges_stay_false_and_require_fails(self):
        a=run(E.DNSE_D1_HISTORY,dnse(dnse_row()))
        self.assertTrue(a.reference_only)
        self.assertFalse(a.source_rights_verified)
        self.assertFalse(a.licensed_retention_approved)
        self.assertFalse(a.indicator_eligible)
        self.assertFalse(a.live_trading_enabled)
        with self.assertRaises(PermissionError):require_authorized_c2_source(a)
        with self.assertRaises(ValueError):replace(a,licensed_retention_approved=True)

    def test_fake_report_authority_rejected(self):
        with self.assertRaises(TypeError):require_authorized_c2_source({"ok":True})

    def test_report_immutable(self):
        a=run(E.SSI_D1_DETAILED,ssi_d1(ssi_row()))
        with self.assertRaises(FrozenInstanceError):a.source_rights_verified=True


if __name__ == "__main__": unittest.main()
