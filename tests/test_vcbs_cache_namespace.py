"""Synthetic three-provider cache isolation after adding VCBS to C1.

No real provider payloads, quotes or network calls used.
"""
import tempfile
from pathlib import Path
import unittest

from swing_trading.incremental_cache import Provider, SyntheticIncrementalStore
from test_incremental_cache import identity, bar, START, FIVE


class VcbsProviderNamespaceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/'three_provider_fixture.sqlite'
        self.store=SyntheticIncrementalStore(self.path)
        self.store.initialize()

    def write(self, key, bars, at=3, scope=0, complete=True):
        return self.store.apply_fixture_window(
            key, tuple(bars), observed_at_utc=START+FIVE*at,
            scope_start_utc=START+FIVE*scope, scope_end_utc=START+FIVE*at,
            complete_scope=complete, full_session_reconciled=complete,
        )

    def test_provider_enum_contains_exact_three_sources(self):
        self.assertEqual({p.value for p in Provider}, {"SSI", "DNSE", "VCBS"})

    def test_provider_identity_hashes_distinct(self):
        hashes={identity(p).fingerprint for p in Provider}
        self.assertEqual(len(hashes),3)

    def test_three_provider_fixture_bars_isolated(self):
        for p in Provider:
            self.write(identity(p), [bar(0),bar(1)], at=2)
        for p in Provider:
            self.assertEqual(len(self.store.read_bars(identity(p))),2)
            self.assertEqual(len(self.store.read_checkpoints(identity(p))),2)

    def test_vcbs_revision_does_not_touch_ssi_or_dnse(self):
        for p in Provider:
            self.write(identity(p), [bar(0),bar(1)], at=2)
        before={p:self.store.read_checkpoints(identity(p)) for p in (Provider.SSI,Provider.DNSE)}
        revised=bar(1,close='999',rev='r2')
        update=self.write(identity(Provider.VCBS),[revised],at=3,scope=1,complete=False)
        self.assertEqual(update.revised,1)
        for p in (Provider.SSI,Provider.DNSE):
            self.assertEqual(self.store.read_checkpoints(identity(p)), before[p])
            self.assertEqual(self.store.read_bars(identity(p))[-1].close,bar(1).close)

    def test_three_provider_restart_isolated(self):
        for p in Provider:
            self.write(identity(p), [bar(0)],at=1)
        self.store=SyntheticIncrementalStore(self.path)
        for p in Provider:
            self.assertEqual(len(self.store.read_bars(identity(p))),1)


if __name__=="__main__": unittest.main()
