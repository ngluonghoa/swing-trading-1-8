# H2-C — Semantic cache compatibility and no-surprise storage swaps

Scope: two existing synthetic-only stores. No production migration, independent source trust, Google Drive write, DB schema change, trade signal or performance claim.

## Why H2-B's shared interface is not sufficient

C3B and C4A both provide get_head / read_partition, but a method-level ABI match cannot prove that a new backend returns the same timestamped market revisions, adjustment scope, first-known timestamps, provider identity or indicator state. H2-C therefore adds a separate consumer-side *read-only semantic preview* on exact pinned fake data.

## Implemented

- src/swing_trading/cache_swap_preview.py: compare_synthetic_cache_backends checks only exact C3B SyntheticDrivePartitionIndex and C4A SyntheticWeeklyChunkStore types; no arbitrary callbacks, no provider/cloud/broker access.
- Requires typed synthetic CacheIdentity; explicit lowercase 64-digit SHA pins for both current cache heads. Rejects missing/stale heads before reading. Both original backend read paths independently validate their manifest lineage, content-addressed SHA and first-known/source identity.
- Reads FULL partition (not partial selected weekly windows), computes canonical bar revision/first-known digest and FULL EMA20/ATR14 checkpoints, checks exact row sequence and values. Produces immutable FixtureCacheSwitchReview with fixture_equivalent and explicit failure reasons.
- If OHLCV agrees but revision or first-known timestamps differ, equivalence FAILS. A changed dirty week/EMA/ATR difference fails. Unverified candidate/provider/head/tampered chunk fails closed rather than silently promoting it.
- Hard-false rights/release flags cannot be promoted by constructing or modifying a review. Positive result is only a *synthetic fixture equivalent* report; it is not a witness, signed LKG or authorization to change live storage.

## Regression acceptance

tests/test_h2_cache_swap.py covers parity of both directions; OHLCV revision, first-known and changed-price mismatch; stale/forged heads, wrong provider/indicator, corrupted weekly chunk, malformed pins, invalid backend with malicious property, self-replacement and false release authority. Existing C3B/C4A tests still cover 5→20→1→20, crash, one dirty weekly window, no-overwrite and full global indicator recomputation.

## Still BLOCKED / outside H2

No source-vendor entitlement, immutable off-host authenticated revocation/current head, licensed data on Drive, real network delta/5-minute savings, compare-and-swap cloud writer, production backup/restore, real N/N−1 migrations, cross-venue corporate actions or current broker/inventory state. Do NOT use successful fixture parity to claim any of these.

The compatibility preview itself is additive and safe to roll back as a single scoped PR; it does not mutate the C3B/C4A serializer, SQLite schema or active head.
