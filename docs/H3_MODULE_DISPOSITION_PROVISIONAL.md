# H3 — Provisional whole-module review matrix

This is static prioritization, NOT a human code quality verdict.
KEEP means no threshold breached, NOT error-free. IMPROVE means inspect
before any behavioral refactor. REPLACE and REMOVE are never automatic;
these require separate consumer, migration and rollback evidence.

| Module | Group | LOC | Max branch | Longest function | Consumers | Proposed | Flags |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| __init__ | domain_and_reference | 3 | 0 | 0 | 0 | KEEP | none |
| adaptive_source_router | source_adapter_and_quality | 289 | 27 | 75 | 0 | IMPROVE | HIGH_BRANCH_SCORE |
| b5_calibration_draft | domain_and_reference | 169 | 16 | 33 | 0 | KEEP | none |
| b5_feature_pack | domain_and_reference | 149 | 28 | 64 | 2 | IMPROVE | HIGH_BRANCH_SCORE |
| b5_formula_geometry | domain_and_reference | 211 | 24 | 76 | 1 | IMPROVE | HIGH_BRANCH_SCORE |
| b5_phase_contract | domain_and_reference | 261 | 46 | 117 | 3 | IMPROVE | FUNCTION_90_PLUS, HIGH_BRANCH_SCORE |
| b5_temporal_split_audit | domain_and_reference | 235 | 35 | 91 | 0 | IMPROVE | FUNCTION_90_PLUS, HIGH_BRANCH_SCORE |
| backtest | domain_and_reference | 71 | 4 | 23 | 0 | KEEP | none |
| c2_fair_source_benchmark | source_adapter_and_quality | 292 | 28 | 41 | 0 | IMPROVE | HIGH_BRANCH_SCORE |
| c2_session_probe_readiness | source_adapter_and_quality | 285 | 40 | 56 | 0 | IMPROVE | HIGH_BRANCH_SCORE |
| c2_source_capability_audit | source_adapter_and_quality | 371 | 47 | 76 | 2 | IMPROVE | HIGH_BRANCH_SCORE |
| cache_fetch_planner | cache_and_persistence | 150 | 30 | 77 | 3 | IMPROVE | HIGH_BRANCH_SCORE |
| cache_snapshot_bundle | cache_and_persistence | 357 | 24 | 61 | 0 | IMPROVE | HIGH_BRANCH_SCORE |
| cache_swap_preview | domain_and_reference | 133 | 16 | 47 | 0 | KEEP | none |
| causal | domain_and_reference | 22 | 4 | 7 | 1 | KEEP | none |
| causal_indicators | domain_and_reference | 236 | 18 | 58 | 2 | KEEP | none |
| contracts | domain_and_reference | 59 | 5 | 6 | 7 | KEEP | none |
| d1_atr_reconciliation | domain_and_reference | 288 | 27 | 113 | 2 | IMPROVE | FUNCTION_90_PLUS, HIGH_BRANCH_SCORE |
| d1_mcp_transport_bridge | source_adapter_and_quality | 292 | 11 | 44 | 2 | KEEP | none |
| dnse_d1_reference_fallback | source_adapter_and_quality | 368 | 30 | 69 | 5 | IMPROVE | HIGH_BRANCH_SCORE |
| durable_evidence | evidence_and_rights | 184 | 12 | 35 | 3 | IMPROVE | DUPLICATE_AST |
| engine | domain_and_reference | 14 | 1 | 7 | 0 | KEEP | none |
| engineering_contracts | engineering_governance | 175 | 10 | 27 | 5 | KEEP | none |
| engineering_release | engineering_governance | 102 | 19 | 20 | 0 | KEEP | none |
| evidence_checkpoint | evidence_and_rights | 184 | 12 | 36 | 1 | KEEP | none |
| evidence_recovery | evidence_and_rights | 81 | 4 | 23 | 1 | KEEP | none |
| fixture_scan | cache_and_persistence | 88 | 8 | 44 | 0 | KEEP | none |
| incremental_cache | cache_and_persistence | 411 | 49 | 121 | 9 | IMPROVE | FUNCTION_90_PLUS, HIGH_BRANCH_SCORE |
| legacy_migration | domain_and_reference | 205 | 24 | 98 | 1 | IMPROVE | FUNCTION_90_PLUS, HIGH_BRANCH_SCORE |
| market_data | domain_and_reference | 161 | 23 | 29 | 17 | IMPROVE | HIGH_BRANCH_SCORE, HIGH_FAN_IN |
| migration_archive | domain_and_reference | 126 | 24 | 69 | 0 | IMPROVE | HIGH_BRANCH_SCORE |
| native_minute_bar_source_plan | source_adapter_and_quality | 252 | 15 | 61 | 3 | KEEP | none |
| partition_chunk_cache | cache_and_persistence | 483 | 26 | 49 | 2 | IMPROVE | HIGH_BRANCH_SCORE |
| provider_custody_host_plan | evidence_and_rights | 393 | 25 | 47 | 0 | IMPROVE | HIGH_BRANCH_SCORE |
| provider_head_custody | evidence_and_rights | 432 | 40 | 84 | 1 | IMPROVE | HIGH_BRANCH_SCORE |
| provider_review_packet | evidence_and_rights | 264 | 37 | 104 | 0 | IMPROVE | FUNCTION_90_PLUS, HIGH_BRANCH_SCORE |
| provider_rights_review | evidence_and_rights | 197 | 17 | 58 | 2 | KEEP | none |
| provider_signed_event_chain | evidence_and_rights | 306 | 26 | 81 | 1 | IMPROVE | HIGH_BRANCH_SCORE |
| quality_audit | domain_and_reference | 181 | 14 | 27 | 1 | KEEP | none |
| reference_checkpoint_mac | evidence_and_rights | 168 | 11 | 22 | 0 | KEEP | none |
| reference_checkpoint_signature | evidence_and_rights | 176 | 15 | 35 | 1 | KEEP | none |
| reference_host_dryrun | evidence_and_rights | 154 | 8 | 29 | 0 | KEEP | none |
| reference_journal | evidence_and_rights | 353 | 31 | 56 | 5 | IMPROVE | HIGH_BRANCH_SCORE, DUPLICATE_AST |
| reference_journal_recovery | evidence_and_rights | 298 | 12 | 66 | 3 | KEEP | none |
| reference_offline_verified_archive | evidence_and_rights | 159 | 15 | 96 | 0 | IMPROVE | FUNCTION_90_PLUS |
| reference_pinned_fd | evidence_and_rights | 163 | 23 | 78 | 1 | IMPROVE | HIGH_BRANCH_SCORE, SILENT_EXCEPT |
| reference_storage_preflight | evidence_and_rights | 143 | 22 | 82 | 2 | IMPROVE | HIGH_BRANCH_SCORE |
| replay | domain_and_reference | 26 | 3 | 5 | 31 | KEEP | HIGH_FAN_IN |
| replay_batch | domain_and_reference | 139 | 13 | 47 | 0 | KEEP | none |
| rvol_tod_contract | domain_and_reference | 191 | 21 | 75 | 0 | IMPROVE | HIGH_BRANCH_SCORE |
| segmented_cache | cache_and_persistence | 295 | 27 | 58 | 1 | IMPROVE | HIGH_BRANCH_SCORE |
| session_calendar | domain_and_reference | 128 | 14 | 21 | 0 | KEEP | none |
| source_capability_evidence | domain_and_reference | 231 | 32 | 76 | 1 | IMPROVE | HIGH_BRANCH_SCORE |
| source_quality | domain_and_reference | 296 | 39 | 58 | 8 | IMPROVE | HIGH_BRANCH_SCORE |
| ssi_historical_availability | source_adapter_and_quality | 95 | 12 | 45 | 0 | KEEP | none |
| ssi_intraday_label_diagnostics | source_adapter_and_quality | 181 | 17 | 87 | 0 | KEEP | none |
| ssi_multivenue_review | source_adapter_and_quality | 129 | 11 | 59 | 0 | KEEP | none |
| ssi_source_qualification | source_adapter_and_quality | 345 | 16 | 64 | 1 | KEEP | none |
| ssi_volume_parity | source_adapter_and_quality | 229 | 20 | 63 | 2 | IMPROVE | HIGH_BRANCH_SCORE |
| vcbs_source_contract | source_adapter_and_quality | 175 | 19 | 41 | 0 | KEEP | none |
| vn_2026_closure_anchors | domain_and_reference | 102 | 8 | 30 | 0 | KEEP | none |
| vn_backtest_execution_fixture | domain_and_reference | 184 | 18 | 38 | 0 | KEEP | none |
| vn_release_rollback | engineering_governance | 345 | 35 | 97 | 0 | IMPROVE | FUNCTION_90_PLUS, HIGH_BRANCH_SCORE |

## Review gates
Any proposed change must freeze current fixture behavior, assess direct
and transitive consumers, test corrupt/stale/source-boundary paths,
and demonstrate a scoped rollback. An unchanged module can be kept.
No market provider rights, live cache, release or OOS are certified.
