"""H3-B: frozen observable invariants for legacy synthetic cache refactor.

No external provider or broker. Use the exact existing SQLite schema/lineage
and full recompute to catch behavior changes across helper extraction.
"""
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from swing_trading.incremental_cache import (
    SyntheticIncrementalStore, CacheUpdate, full_recompute,
)
from test_incremental_cache import identity, bar, START, FIVE


def observed_state(store, path, key):
    with closing(sqlite3.connect(path)) as c:
        bars = c.execute(
            "SELECT cache_key,start_utc,end_utc,o,h,l,c,volume,revision,first_known_utc,digest "
            "FROM fixture_bars ORDER BY cache_key,start_utc"
        ).fetchall()
        lineage = c.execute(
            "SELECT cache_key,start_utc,event_type,old_digest,new_digest,observed_at_utc "
            "FROM fixture_lineage ORDER BY id"
        ).fetchall()
        indicators = c.execute(
            "SELECT cache_key,start_utc,ema20,atr14,atr_seen,atr_seed_sum,last_close "
            "FROM fixture_checkpoints ORDER BY cache_key,start_utc"
        ).fetchall()
        cursors = c.execute(
            "SELECT cache_key,last_checked_utc,last_full_reconciled_utc "
            "FROM fixture_cursor ORDER BY cache_key"
        ).fetchall()
    return tuple(bars), tuple(lineage), tuple(indicators), tuple(cursors)


class CacheTransactionRefactorGoldenTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db = Path(temporary.name) / "fixture.sqlite"
        self.key = identity()
        self.store = SyntheticIncrementalStore(self.db)
        self.store.initialize()

    def apply(self, bars, *, clock, first, last, complete=False, full=False):
        return self.store.apply_fixture_window(
            self.key, tuple(bars),
            observed_at_utc=START + FIVE * clock,
            scope_start_utc=START + FIVE * first,
            scope_end_utc=START + FIVE * last,
            complete_scope=complete,
            full_session_reconciled=full,
        )

    def test_closed_cold_build_golden_metrics_and_cursor(self):
        result = self.apply([bar(i) for i in range(6)],
                            clock=6, first=0, last=6, complete=True, full=True)
        self.assertEqual((result.inserted, result.revised, result.deleted,
                          result.unchanged, result.lineage_only,
                          result.ignored_open, result.indicator_bars_recomputed),
                         (6, 0, 0, 0, 0, 0, 6))
        self.assertEqual(result.first_dirty_utc, bar(0).start_utc)
        self.assertEqual(result.invalidated_layers, ("L1", "L2", "L3", "L4", "L5"))
        self.assertEqual(
            self.store.read_checkpoints(self.key),
            full_recompute(self.store.read_bars(self.key)),
        )
        self.assertEqual(
            self.store.cursor(self.key).last_full_reconciled_utc,
            START + FIVE * 6,
        )

    def test_golden_sequence_metadata_revision_price_correction_and_delete(self):
        self.apply((bar(i) for i in range(6)),
                   clock=6, first=0, last=6, complete=True, full=True)
        metadata = self.apply([bar(4, rev="r2")],
                              clock=7, first=4, last=7)
        self.assertEqual((metadata.lineage_only, metadata.indicator_bars_recomputed),
                         (1, 0))
        corrected = self.apply([bar(2, close="170", rev="r2")],
                               clock=8, first=2, last=8)
        self.assertEqual((corrected.revised, corrected.indicator_bars_recomputed),
                         (1, 4))
        dropped = self.apply([bar(5)],
                             clock=9, first=4, last=9, complete=True)
        self.assertEqual((dropped.deleted, dropped.indicator_bars_recomputed), (1, 1))
        self.assertEqual(
            tuple(b.start_utc for b in self.store.read_bars(self.key)),
            tuple(bar(i).start_utc for i in (0, 1, 2, 3, 5)),
        )
        self.assertEqual(self.store.read_checkpoints(self.key),
                         full_recompute(self.store.read_bars(self.key)))
        rows = observed_state(self.store, self.db, self.key)
        self.assertEqual(tuple(r[2] for r in rows[1]),
                         ("APPEND",) * 6 + ("LINEAGE_ONLY", "REVISE", "DELETE"))
        self.assertEqual(len(rows[2]), 5)

    def test_incomplete_scope_preserves_bars_and_open_bar_ignored(self):
        self.apply((bar(i) for i in range(5)),
                   clock=5, first=0, last=5, complete=True, full=True)
        preview = self.apply([bar(4)], clock=6, first=2, last=6, complete=False)
        self.assertEqual((preview.deleted, preview.unchanged,
                          preview.indicator_bars_recomputed), (0, 1, 0))
        ignored = self.apply([bar(5, closed=False)],
                             clock=7, first=5, last=7)
        self.assertEqual((ignored.ignored_open,
                          ignored.indicator_bars_recomputed), (1, 0))
        self.assertEqual(len(self.store.read_bars(self.key)), 5)

    def test_cursor_regression_failure_rolls_back_prior_sql_writes(self):
        self.apply((bar(i) for i in range(6)),
                   clock=8, first=0, last=6, complete=True, full=True)
        before = observed_state(self.store, self.db, self.key)
        with self.assertRaisesRegex(ValueError, "regress cache observation clock"):
            self.apply([bar(2, close="170", rev="r2")],
                       clock=7, first=2, last=7)
        self.assertEqual(observed_state(self.store, self.db, self.key), before)
        self.assertEqual(self.store.read_checkpoints(self.key),
                         full_recompute(self.store.read_bars(self.key)))

    def test_bad_window_rejected_before_opening_sqlite(self):
        with patch.object(SyntheticIncrementalStore, "_connect",
                          side_effect=AssertionError("premature database access")):
            with self.assertRaisesRegex(ValueError, "completed observation window"):
                self.apply([bar(0)], clock=0, first=1, last=0)
            with self.assertRaisesRegex(ValueError, "unknown at observation"):
                self.apply([bar(3)], clock=3, first=0, last=3)

    def test_invalid_new_revision_rolls_back_history(self):
        self.apply([bar(2)], clock=4, first=2, last=4)
        original = observed_state(self.store, self.db, self.key)
        earlier = replace(bar(2, rev="r2"),
                          first_known_utc=START + FIVE * 2)
        with self.assertRaisesRegex(ValueError, "move backwards"):
            self.apply([earlier], clock=5, first=2, last=5)
        self.assertEqual(observed_state(self.store, self.db, self.key), original)

    def test_scope_reconciled_only_after_complete_response(self):
        self.apply([bar(0)], clock=2, first=0, last=2)
        old = self.store.cursor(self.key).last_full_reconciled_utc
        self.assertIsNone(old)
        with self.assertRaises(ValueError):
            self.apply([bar(0)], clock=3, first=0, last=3, full=True)
        self.assertIsNone(self.store.cursor(self.key).last_full_reconciled_utc)
        self.apply([bar(0)], clock=4, first=0, last=4, full=True, complete=True)
        self.assertEqual(self.store.cursor(self.key).last_full_reconciled_utc,
                         START + FIVE * 4)

    def test_returned_rights_flags_stay_disabled(self):
        update = self.apply([bar(0)], clock=2, first=0, last=2)
        self.assertIsInstance(update, CacheUpdate)
        self.assertTrue(update.fixture_only)
        self.assertFalse(update.market_authorized)
        self.assertEqual(self.store.read_checkpoints(self.key),
                         full_recompute(self.store.read_bars(self.key)))


if __name__ == "__main__":
    unittest.main()
