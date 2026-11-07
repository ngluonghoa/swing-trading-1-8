"""C3C: offline negative paths for real connector's harmless staging receipt."""
import json
import unittest
from dataclasses import replace
from hashlib import sha256

from swing_trading.drive_c3c_receipt import (
    CHUNK_FOLDER, MANIFEST_FOLDER, FIXTURE_ID, FIXTURE_TEXT, SCHEMA,
    DownloadedDriveMetadata, verify_c3c_connector_readback,
    require_real_market_drive_cache,
)

CHUNK_FILE_ID = "1KO0q-TlcZDD5ZLf1A7v3KzK02d_PO2K6"
MANIFEST_FILE_ID = "17pu_kzMg-brIRsv0CoXgDhZKB8Lc7r0m"
CHUNK_SHA = "9f0f6e1ecb035c2f132edb1f689e6c33b653724a9498dbec232f97002e9d424c"
MANIFEST_SHA = "70bf6e4114ba8d3eadd1d5adc5a39d986feaef7981a6c766d9f865338526cba0"
CHUNK = b"\xef\xbb\xbf" + FIXTURE_TEXT.replace("\n", "\r\n").encode("ascii")
CHUNK_NAME = "st18-c3c-" + CHUNK_SHA + ".synthetic.txt"
MANIFEST_NAME = "st18-c3c-manifest-" + CHUNK_SHA + ".synthetic.json"

def _manifest():
    return {
        "chunk_drive_file_id": CHUNK_FILE_ID,
        "chunk_mime_type": "text/plain",
        "chunk_name": CHUNK_NAME,
        "chunk_parent_folder_id": CHUNK_FOLDER,
        "chunk_sha256": CHUNK_SHA,
        "chunk_size_bytes": 237,
        "environment": "SYNTHETIC_TEST_ONLY",
        "fixture_id": FIXTURE_ID,
        "manifest_parent_folder_id": MANIFEST_FOLDER,
        "market_data_present": False,
        "no_atomic_commit": True,
        "no_external_witness": True,
        "project_id": "SwingTrading1.8",
        "schema": SCHEMA,
        "source_rights_verified": False,
        "trade_allowed": False,
    }

def _bytes(manifest):
    return b"\xef\xbb\xbf" + json.dumps(manifest,sort_keys=True,
                ensure_ascii=True,separators=(",",":")).encode("ascii")

class C3CReceiptTests(unittest.TestCase):
    def setUp(self):
        self.fixture = CHUNK
        self.info = _manifest()
        self.manifest_raw = _bytes(self.info)
        self.chunk_meta = DownloadedDriveMetadata(
            CHUNK_FILE_ID,CHUNK_NAME,"text/plain",len(CHUNK),(CHUNK_FOLDER,),False,("owner",))
        self.manifest_meta = DownloadedDriveMetadata(
            MANIFEST_FILE_ID,MANIFEST_NAME,"application/json",len(self.manifest_raw),
            (MANIFEST_FOLDER,),False,("owner",))

    def verify(self,*,chunk=None,manifest=None,chunk_meta=None,manifest_meta=None):
        return verify_c3c_connector_readback(
            self.fixture if chunk is None else chunk,
            self.manifest_raw if manifest is None else manifest,
            chunk=self.chunk_meta if chunk_meta is None else chunk_meta,
            manifest=self.manifest_meta if manifest_meta is None else manifest_meta,
        )

    def rewrite(self,**kwargs):
        return _bytes(dict(self.info,**kwargs))

    def test_known_actual_drive_fixture_export_digest(self):
        self.assertEqual(len(CHUNK),237)
        self.assertEqual(sha256(CHUNK).hexdigest(),CHUNK_SHA)
        self.assertEqual(len(self.manifest_raw),742)
        self.assertEqual(sha256(self.manifest_raw).hexdigest(),MANIFEST_SHA)

    def test_offline_readback_accepts_exact_reported_original_files(self):
        r=self.verify()
        self.assertTrue(r.connector_readback_verified)
        self.assertEqual((r.chunk_sha256,r.manifest_sha256,r.chunk_bytes,r.manifest_bytes),
                         (CHUNK_SHA,MANIFEST_SHA,237,742))
        self.assertFalse(r.may_trade)
        self.assertFalse(r.may_cache_real_market_data)
        self.assertFalse(r.may_claim_atomic_commit)
        self.assertFalse(r.may_claim_external_witness)

    def test_lf_only_utf8_fixture_body_can_be_safely_parsed_when_metadata_matches(self):
        a=FIXTURE_TEXT.encode("ascii")
        z=self.rewrite(chunk_sha256=sha256(a).hexdigest(),chunk_size_bytes=len(a),
                       chunk_name="st18-c3c-"+sha256(a).hexdigest()+".synthetic.txt")
        self.verify(chunk=a,manifest=z,
                    chunk_meta=replace(self.chunk_meta,file_name="st18-c3c-"+sha256(a).hexdigest()+".synthetic.txt",
                                       size_bytes=len(a)),
                    manifest_meta=replace(self.manifest_meta,
                       file_name="st18-c3c-manifest-"+sha256(a).hexdigest()+".synthetic.json",
                       size_bytes=len(z)))

    def test_modified_chunk_content_fails_closed(self):
        with self.assertRaises(ValueError):
            self.verify(chunk=self.fixture+b"TAMPER")

    def test_truncated_chunk_fails_closed(self):
        with self.assertRaises(ValueError):
            self.verify(chunk=self.fixture[:-1])

    def test_non_synthetic_market_data_injection_denied(self):
        with self.assertRaises(ValueError):
            self.verify(chunk=self.fixture+b"\r\nclose=100.0")

    def test_extra_manifest_key_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest=self.rewrite(hidden_vendor_quote="TOP_SECRET"))

    def test_duplicate_manifest_key_denied(self):
        body=self.manifest_raw.decode("utf-8-sig")
        modified=body.replace('"chunk_mime_type":"text/plain",',
                              '"chunk_mime_type":"text/plain","chunk_mime_type":"text/plain",')
        with self.assertRaises(ValueError):
            self.verify(manifest=b"\xef\xbb\xbf"+modified.encode("utf8"))

    def test_forged_licensed_market_data_flag_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(manifest=self.rewrite(market_data_present=True))

    def test_forged_source_rights_flag_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(manifest=self.rewrite(source_rights_verified=True))

    def test_forged_trade_flag_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(manifest=self.rewrite(trade_allowed=True))

    def test_forged_atomic_commit_flag_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(manifest=self.rewrite(no_atomic_commit=False))

    def test_forged_external_witness_flag_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(manifest=self.rewrite(no_external_witness=False))

    def test_broken_chunk_sha_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest=self.rewrite(chunk_sha256="0"*64))

    def test_broken_chunk_file_id_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest=self.rewrite(chunk_drive_file_id="not-original-id"))

    def test_broken_chunk_parent_declared_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest=self.rewrite(chunk_parent_folder_id=MANIFEST_FOLDER))

    def test_broken_manifest_parent_declared_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest=self.rewrite(manifest_parent_folder_id=CHUNK_FOLDER))

    def test_wrong_chunk_metadata_parent_denied(self):
        with self.assertRaises(ValueError):
            self.verify(chunk_meta=replace(self.chunk_meta,parent_ids=(MANIFEST_FOLDER,)))

    def test_wrong_manifest_metadata_parent_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest_meta=replace(self.manifest_meta,parent_ids=(CHUNK_FOLDER,)))

    def test_wrong_chunk_metadata_size_denied(self):
        with self.assertRaises(ValueError):
            self.verify(chunk_meta=replace(self.chunk_meta,size_bytes=len(self.fixture)+1))

    def test_wrong_manifest_metadata_size_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest_meta=replace(self.manifest_meta,size_bytes=len(self.manifest_raw)-1))

    def test_unknown_chunk_mime_denied(self):
        with self.assertRaises(ValueError):
            self.verify(chunk_meta=replace(self.chunk_meta,mime_type="application/octet-stream"))

    def test_unknown_manifest_mime_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest_meta=replace(self.manifest_meta,mime_type="text/plain"))

    def test_publicly_shared_metadata_denied(self):
        with self.assertRaises(PermissionError):
            replace(self.chunk_meta,shared=True)

    def test_missing_owner_only_evidence_denied(self):
        with self.assertRaises(PermissionError):
            replace(self.manifest_meta,permission_roles=())

    def test_noncanonical_json_denied(self):
        z=json.dumps(self.info,sort_keys=True,indent=2).encode("ascii")
        with self.assertRaises(ValueError):
            self.verify(manifest=z)

    def test_other_project_schema_denied(self):
        with self.assertRaises(PermissionError):
            self.verify(manifest=self.rewrite(schema="FOREX1_FAKE_MANIFEST"))

    def test_wrong_manifest_name_denied(self):
        with self.assertRaises(ValueError):
            self.verify(manifest_meta=replace(self.manifest_meta,file_name="manifest.json"))

    def test_wrong_chunk_name_denied(self):
        with self.assertRaises(ValueError):
            self.verify(chunk_meta=replace(self.chunk_meta,file_name="foo.txt"))

    def test_real_market_transport_remains_closed(self):
        with self.assertRaises(PermissionError):
            require_real_market_drive_cache()

if __name__=="__main__":
    unittest.main()
