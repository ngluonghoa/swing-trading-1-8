"""H2-C: semantic, not just structural, compatibility between old cache stores."""
from dataclasses import replace
from datetime import timedelta
import unittest

from swing_trading.cache_swap_preview import (
    compare_synthetic_cache_backends, FixtureCacheSwitchReview,
)
from swing_trading.incremental_cache import Provider
from swing_trading.partition_chunk_cache import SyntheticDrivePartitionIndex
from swing_trading.segmented_cache import SyntheticWeeklyChunkStore
from test_h2_legacy_ports import identity, bar, NOW


class CacheBackendSwapTests(unittest.TestCase):
    def setUp(self):
        self.key = identity()
        self.original = tuple(bar(i) for i in range(15))
        self.old = SyntheticDrivePartitionIndex()
        self.candidate = SyntheticWeeklyChunkStore()
        self.old.stage_and_publish(
            self.key, self.original, expected_head_sha256=None, created_at_utc=NOW
        )
        self.candidate.commit(
            self.key, self.original, expected_head=None, observed_at_utc=NOW
        )

    def review(self, **updates):
        args = dict(
            identity=self.key, old_backend=self.old, candidate_backend=self.candidate,
            pinned_old_sha256=self.old.get_head(self.key),
            pinned_candidate_sha256=self.candidate.get_head(self.key),
        )
        args.update(updates)
        return compare_synthetic_cache_backends(**args)

    def test_real_old_backends_semantically_equivalent(self):
        result = self.review()
        self.assertTrue(result.fixture_equivalent)
        self.assertEqual(result.reasons, ())
        self.assertEqual((result.old_rows, result.candidate_rows), (15, 15))
        self.assertEqual(result.old_content_sha256, result.candidate_content_sha256)
        self.assertEqual(result.partition_sha256, self.key.fingerprint)
        self.assertFalse(result.real_migration_approved)

    def test_real_backends_can_be_compared_in_reverse(self):
        result = self.review(
            old_backend=self.candidate, candidate_backend=self.old,
            pinned_old_sha256=self.candidate.get_head(self.key),
            pinned_candidate_sha256=self.old.get_head(self.key),
        )
        self.assertTrue(result.fixture_equivalent)

    def test_revised_value_denies_equivalence_without_touching_old(self):
        changed = tuple(bar(i, revision="r2", change=True) if i == 8 else bar(i)
                        for i in range(15))
        previous = self.old.get_head(self.key)
        self.candidate.commit(
            self.key, changed, expected_head=self.candidate.get_head(self.key),
            observed_at_utc=NOW,
        )
        diff = self.review()
        self.assertFalse(diff.fixture_equivalent)
        self.assertIn("BAR_OR_REVISION_OR_FIRST_KNOWN_MISMATCH", diff.reasons)
        self.assertIn("GLOBAL_EMA_ATR_CHECKPOINT_MISMATCH", diff.reasons)
        self.assertEqual(self.old.get_head(self.key), previous)
        self.assertEqual(self.old.read_partition(self.key, pinned_digest=previous),
                         self.original)

    def test_same_ohlcv_but_different_revision_denied(self):
        revised = tuple(replace(bar(i), revision="r2") if i == 8 else bar(i)
                        for i in range(15))
        self.candidate.commit(
            self.key, revised, expected_head=self.candidate.get_head(self.key),
            observed_at_utc=NOW,
        )
        r = self.review()
        self.assertFalse(r.fixture_equivalent)
        self.assertEqual(r.reasons, ("BAR_OR_REVISION_OR_FIRST_KNOWN_MISMATCH",))
        self.assertNotEqual(r.old_content_sha256, r.candidate_content_sha256)

    def test_same_ohlcv_but_new_first_known_time_denied(self):
        revised = tuple(replace(bar(i), first_known_utc=bar(i).first_known_utc
                                + timedelta(minutes=1)) if i == 8 else bar(i)
                        for i in range(15))
        self.candidate.commit(
            self.key, revised, expected_head=self.candidate.get_head(self.key),
            observed_at_utc=NOW,
        )
        r = self.review()
        self.assertFalse(r.fixture_equivalent)
        self.assertIn("BAR_OR_REVISION_OR_FIRST_KNOWN_MISMATCH", r.reasons)

    def test_stale_candidate_pin_denied(self):
        with self.assertRaisesRegex(ValueError, "STALE_OR_MISSING_CANDIDATE_HEAD"):
            self.review(pinned_candidate_sha256="1" * 64)

    def test_stale_old_pin_denied(self):
        with self.assertRaisesRegex(ValueError, "STALE_OR_MISSING_OLD_HEAD"):
            self.review(pinned_old_sha256="1" * 64)

    def test_untyped_or_malformed_pin_denied(self):
        for bad in (None, "HEAD", "A" * 64):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.review(pinned_old_sha256=bad)

    def test_cross_provider_fails_no_silent_swap(self):
        with self.assertRaisesRegex(ValueError, "STALE_OR_MISSING_OLD_HEAD"):
            self.review(identity=identity(provider=Provider.VCBS))

    def test_different_indicator_fails_no_silent_swap(self):
        with self.assertRaises(ValueError):
            self.review(identity=identity(indicator="EMA21ATR14"))

    def test_corrupted_new_chunk_raises_without_approving(self):
        self.candidate.corrupt_latest_window_for_test(self.key)
        with self.assertRaises(ValueError):
            self.review()

    def test_invalid_backend_type_does_not_execute_arbitrary_code(self):
        class Arbitrary:
            called = False

            @property
            def read_port_descriptor(self):
                self.called = True
                raise AssertionError("should never be accessed")

        unsafe = Arbitrary()
        with self.assertRaises(TypeError):
            self.review(candidate_backend=unsafe)
        self.assertFalse(unsafe.called)

    def test_same_backend_not_a_replacement(self):
        with self.assertRaises(ValueError):
            self.review(candidate_backend=self.old)

    def test_review_never_confers_data_license_or_deployment(self):
        result = self.review()
        for field in ("licensed_data_authorized", "real_migration_approved",
                      "trading_authorized"):
            with self.subTest(field=field), self.assertRaises(PermissionError):
                replace(result, **{field: True})

    def test_forged_equivalence_receipt_denied(self):
        baseline = self.review()
        with self.assertRaises(ValueError):
            replace(baseline, fixture_equivalent=False)
        with self.assertRaises(ValueError):
            FixtureCacheSwitchReview(
                partition_sha256=self.key.fingerprint,
                old_head_sha256="0" * 64, candidate_head_sha256="0" * 64,
                old_rows=0, candidate_rows=1, old_content_sha256="0" * 64,
                candidate_content_sha256="0" * 64,
                fixture_equivalent=True, reasons=(),
            )


if __name__ == "__main__":
    unittest.main()
