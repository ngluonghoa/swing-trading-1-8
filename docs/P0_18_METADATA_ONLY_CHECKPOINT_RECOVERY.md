# GĐ4/P0.18 — Quote-free metadata checkpoint and independently pinned restore

Date: 2026-11-06. **ENGINEERING PROTOTYPE / synthetic CI only**.

This step extends P0.17 `ReferenceJournal` without changing the SSI-first/DNSE-fallback logic or enabling any trading or licensed source retention. The journal and two providers' optional diagnostic cache remain in **one logical SQLite database**; no two physical storage locations have been created or deployed.

## Default safety decision

**Never back up SSI/DNSE quote cache.** Instead of copying the live SQLite file and deleting `cache` rows afterward—which would leave recoverable quote bytes in free pages or WAL—`create_candidate_journal_checkpoint` reads one verified SQLite snapshot and copies **ONLY** `journal(seq, run_id, body, prev, chained)` into a brand-new SQLite database inside a private temporary directory. No price/volume quote rows are inserted in the snapshot. Cache omission is deliberate and recorded as a count in the checkpoint manifest. The source's own encryption, SQL pages, WAL and expired quote removal are **not** addressed by this export.

Module: `src/swing_trading/reference_journal_recovery.py`:
- `JournalCheckpoint`: exact-schema, canonical JSON candidate metadata (`checkpoint_id`, caller-asserted `store_id`, UTC capture, immutable receipt count/tip, SHA256 of snapshot SQLite bytes, number of source cache rows omitted, `schema_version=1`, `snapshot_kind=METADATA_ONLY`). No signing or automatic approval.
- `create_candidate_journal_checkpoint`: verify original journal+cache integrity, read a single SQLite snapshot transaction, construct fresh metadata-only SQLite with the established P0.17 schema, switch to a standalone SQLite journal mode, verify target chain/count and empty cache, fsync and publish a new file using a no-overwrite hard link. Failure cleans staging directory. Designed for a caller-selected approved local POSIX volume, **not** cloud or Mac/MOCHI deployment.
- `verify_journal_backup_against_pinned`: require an **independently supplied/pinned** typed checkpoint and explicit expected store ID, check whole-file SHA256, journal chain/count and zero cache rows. Blindly re-generating a checkpoint from a compromised backup is not independent verification.
- `restore_journal_from_pinned`: checksum-verify the backup, byte-copy into a fresh private staging directory, recheck its checksum and journal/zero-cache integrity, fsync and publish to a NEW path with no overwrite. Never resurrects original SSI/DNSE diagnostic quotes; the recovered journal is appendable but only metadata remains.
- `verify_journal_history_prefix`: verify a live database against an externally pinned historical tip in a **single consistent read transaction**. Does not certify subsequent unpinned tail writes or authorizations. Live cache may contain opted-in quotes; pinned snapshots never do.

## Verification and limits

Synthetic tests in `tests/test_reference_journal_recovery.py` cover empty journal, both providers in one DB, snapshot omitting opted-in SSI+DNSE quote values and SQLite sidecars, restore without reviving quotes, corruption and wrong store/digest/count/tip rejection, immutable history prefix, no-overwrite, strict manifest schema and original source corruption. Run `python -m unittest discover -s tests -v` on Python 3.11 and 3.12.

**Explicit trust and deployment gates:** Checkpoints must be pinned externally by a separately authorized, protected custodian before they are trustworthy. The `store_id` is a caller declaration, not an attested hardware/source identity. The checkpointer is not connected to a scheduler, cloud backup, Google Drive or remote server, nor does it provide an independently approved storage volume or retention rights. This prototype does not prove crash atomicity on arbitrary network mounts, off-site disaster recovery, encryption, access-control policy, signatures, backup deletion, source SQLite secure erase, operational RTO/RPO or production restore on the user's host.

**No quote-bearing backup has been built.** If a future real-world requirement asks to preserve live diagnostic quotes across machine failures, that requires a **separate, licence-approved encrypted backup/retention/expiry specification**; no silent upgrade from metadata-only.

No usable historical M1/M5/M15 has been approved. SSI B01–B08, DNSE price-basis/first-known, source licensing, B5 SHORT/SWING 24 numeric slots, fill/cost/fees/tax/T+2 and real BT/OOS remain OPEN. `UI-1.0 DESIGN_LOCKED`, CK2, FX2, Scanner and MOCHI untouched; no orders or live buy/sell output.

## NEXT GĐ4/P0.19

After confirming this code + synthetic tests: add explicit tested policy for local runtime directory permissions and journal metadata lifecycle (with signed/external-custody checkpoint workflow as an integration contract), then authenticated host-bound read-only transport, licence/first-known and usable historical intraday evidence. No production activation until user-approved host and permissions exist.
