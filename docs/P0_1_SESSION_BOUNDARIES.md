# GĐ4/P0.1 — Session boundary implementation notes

Source: canonical Google Drive 05 Data Contract, sections 2–4.

Implemented:
- Explicit exchange, local trading date, UTC window, session type, version, source and verification status.
- Fail-closed matching: one verified continuous session per intraday bar; no crossing a gap or blending auction rows.
- Timestamp START/END/UNKNOWN must have independently verified endpoint semantics before conversion.
- Unit tests use synthetic fixture hours only; NO official trading-hour claims.

NOT IMPLEMENTED / NOT VERIFIED:
- Exchange calendars, holidays, auction/after-hours classifications and provider-specific timestamp parsing.
- Three-axis candle-quality schema, full provider observation lineage, SSI B01–B08.
- Executable detector rules, actual historical backtest, cloud runtime and live trading.

This validator checks only session structure, not complete signal eligibility.
