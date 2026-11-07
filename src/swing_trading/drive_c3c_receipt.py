"""GĐ4/C3C — strict OFFLINE receipt verifier for an actual harmless Drive smoke.

A connected Google Drive user uploaded ONE fabricated text file and ONE
metadata-only manifest, then downloaded them through the connector. This module
does NO Google API, OAuth, vendor data retrieval, polling, live cache writes,
distributed locking, historical bar processing, key custody or trading.

This is NOT the C3B/ C4A market-data chunk serializer: it proves a *file
transport/readback boundary*, without claiming the Python application can
automatically use those Google OAuth credentials or persist real licensed data.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

CHUNK_FOLDER = "1tC_ksJWo7ecjimVo-fPrg1b7iPdWA7tf"
MANIFEST_FOLDER = "1_U6v9e1WVo3BWZCLyRYSLRLehAsmQqox"
SCHEMA = "SWING18_C3C_GOOGLE_DRIVE_CONNECTOR_SMOKE_MANIFEST_V1"
FIXTURE_ID = "C3C_ONLY_FAKE_NO_MARKET_DATA_20261107"
FIXTURE_TEXT = "\n".join((
    "SWING18_C3C_HARMLESS_CONNECTOR_SMOKE_V1",
    "fixture_id=C3C_ONLY_FAKE_NO_MARKET_DATA_20261107",
    "instrument=TEST_C3C_001",
    "provider=NONE",
    "market_data_present=false",
    "licensed_source_used=false",
    "real_cache_approved=false",
    "trading_allowed=false",
))
FIELDS = frozenset((
    "chunk_drive_file_id", "chunk_mime_type", "chunk_name",
    "chunk_parent_folder_id", "chunk_sha256", "chunk_size_bytes",
    "environment", "fixture_id", "manifest_parent_folder_id",
    "market_data_present", "no_atomic_commit", "no_external_witness",
    "project_id", "schema", "source_rights_verified", "trade_allowed",
))
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_DRIVE_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
MAX_FIXTURE_BYTES = 4096
MAX_MANIFEST_BYTES = 4096


def _digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _name_chunk(sha: str) -> str:
    return f"st18-c3c-{sha}.synthetic.txt"


def _name_manifest(sha: str) -> str:
    return f"st18-c3c-manifest-{sha}.synthetic.json"


def _decode_text(raw: bytes, *, maximum: int) -> str:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= maximum:
        raise ValueError("Bounded downloaded bytes are required")
    # Google Docs text/plain export adds an initial UTF-8 BOM; its line breaks
    # may be CRLF. Treat bytes AS RECEIVED for SHA, never normalized SHA.
    try:
        t = raw.decode("utf-8-sig", errors="strict")
    except UnicodeError as exc:
        raise ValueError("UTF-8 receipt required") from exc
    if "\r" in t.replace("\r\n", ""):
        raise ValueError("Unpaired CR in fixture transport")
    return t.replace("\r\n", "\n")


@dataclass(frozen=True)
class DownloadedDriveMetadata:
    file_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    parent_ids: tuple[str, ...]
    shared: bool
    permission_roles: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.file_id, str) or not _DRIVE_ID.fullmatch(self.file_id):
            raise ValueError("Provider-owned Drive ID required")
        if not isinstance(self.file_name, str) or not self.file_name:
            raise ValueError("Expected file name required")
        if not isinstance(self.mime_type, str) or not self.mime_type:
            raise ValueError("Expected explicit MIME type required")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ValueError("Positive provider-reported byte size required")
        if not isinstance(self.parent_ids, tuple) or len(self.parent_ids) != 1:
            raise ValueError("Exactly one staging parent folder required")
        if self.shared is not False or self.permission_roles != ("owner",):
            raise PermissionError("Fail closed without private owner-only connector evidence")


@dataclass(frozen=True)
class VerifiedC3CReadback:
    chunk_sha256: str
    manifest_sha256: str
    chunk_bytes: int
    manifest_bytes: int
    connector_readback_verified: bool = True
    fixture_only: bool = True
    may_cache_real_market_data: bool = False
    may_claim_atomic_commit: bool = False
    may_claim_external_witness: bool = False
    may_trade: bool = False


def verify_c3c_connector_readback(chunk_bytes: bytes, manifest_bytes: bytes, *,
                                  chunk: DownloadedDriveMetadata,
                                  manifest: DownloadedDriveMetadata) -> VerifiedC3CReadback:
    """Verify downloaded bytes against *caller-supplied* Drive metadata.

    This is an independent offline consistency check, not an attestation that
    Google metadata is authentic. The caller must read both file contents and
    metadata from the connector in a distinct verification step.
    """
    if not isinstance(chunk, DownloadedDriveMetadata) or not isinstance(manifest, DownloadedDriveMetadata):
        raise TypeError("Two typed Drive metadata receipts are required")
    chunk_text = _decode_text(chunk_bytes, maximum=MAX_FIXTURE_BYTES)
    if chunk_text != FIXTURE_TEXT:
        raise ValueError("Non-harmless or unknown synthetic fixture body")
    manifest_text = _decode_text(manifest_bytes, maximum=MAX_MANIFEST_BYTES)
    if manifest_text != manifest_text.strip():
        raise ValueError("No extra whitespace before or after JSON document")
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate manifest JSON key")
            result[key] = value
        return result
    try:
        obj = json.loads(manifest_text, object_pairs_hook=reject_duplicates,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON manifest") from exc
    if type(obj) is not dict or set(obj) != FIELDS:
        raise ValueError("Exact C3C synthetic manifest schema is mandatory")
    # The payload generated in the temporary source Google Doc is canonical
    # ASCII JSON. BOM/CRLF are transport effects, not included in the JSON.
    canonical = json.dumps(obj, ensure_ascii=True, sort_keys=True,
                           separators=(",", ":"), allow_nan=False)
    if manifest_text != canonical:
        raise ValueError("Noncanonical C3C JSON body")
    if (obj["schema"] != SCHEMA or obj["fixture_id"] != FIXTURE_ID
            or obj["project_id"] != "SwingTrading1.8"
            or obj["environment"] != "SYNTHETIC_TEST_ONLY"
            or obj["market_data_present"] is not False
            or obj["source_rights_verified"] is not False
            or obj["trade_allowed"] is not False
            or obj["no_atomic_commit"] is not True
            or obj["no_external_witness"] is not True):
        raise PermissionError("Never authorize market data/trading or infer trusted commit")
    sha = _digest(chunk_bytes)
    if (type(obj["chunk_sha256"]) is not str or not _SHA256.fullmatch(obj["chunk_sha256"])
            or obj["chunk_sha256"] != sha):
        raise ValueError("Downloaded chunk SHA256 does not match manifest")
    if (type(obj["chunk_size_bytes"]) is not int or obj["chunk_size_bytes"] != len(chunk_bytes)):
        raise ValueError("Downloaded chunk length mismatch")
    if (obj["chunk_drive_file_id"] != chunk.file_id
            or obj["chunk_parent_folder_id"] != CHUNK_FOLDER
            or obj["manifest_parent_folder_id"] != MANIFEST_FOLDER):
        raise ValueError("Incorrect Drive IDs or folder namespace")
    if (chunk.parent_ids != (CHUNK_FOLDER,) or manifest.parent_ids != (MANIFEST_FOLDER,)
            or chunk.size_bytes != len(chunk_bytes) or manifest.size_bytes != len(manifest_bytes)
            or chunk.mime_type != "text/plain" or manifest.mime_type != "application/json"
            or obj["chunk_mime_type"] != chunk.mime_type):
        raise ValueError("Downloaded provider metadata is not the expected staging type")
    if (obj["chunk_name"] != _name_chunk(sha) or chunk.file_name != _name_chunk(sha)
            or manifest.file_name != _name_manifest(sha)):
        raise ValueError("Content-addressed synthetic Drive file name mismatch")
    return VerifiedC3CReadback(
        chunk_sha256=sha, manifest_sha256=_digest(manifest_bytes),
        chunk_bytes=len(chunk_bytes), manifest_bytes=len(manifest_bytes),
    )


def require_real_market_drive_cache(*_args: object, **_kwargs: object) -> None:
    raise PermissionError("C3C is a harmless Drive connector smoke, NOT a licensed market cache adapter")
