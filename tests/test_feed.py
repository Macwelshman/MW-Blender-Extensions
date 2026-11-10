"""Generate isolated ZIP fixtures so checks can be exercised independently."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts import feed

ID = "mw_fixture"
MANIFEST = """schema_version = "1.0.0"
id = "mw_fixture"
version = "1.0.0"
name = "MW Fixture"
tagline = "Exercise feed validation"
maintainer = "MW"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]
"""


class FeedTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.archive = self.root / f"{ID}-1.0.0.zip"
        self.write_zip()
        self.row = feed.manifest(self.archive)
        self.source = {"version": "1.0.0"}
        self.rehash()

    def write_zip(self, manifest=MANIFEST, init="def register(): pass\ndef unregister(): pass\n"):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("blender_manifest.toml", manifest)
            archive.writestr("__init__.py", init)

    def rehash(self):
        payload = self.archive.read_bytes()
        self.source["sha256"] = hashlib.sha256(payload).hexdigest()
        self.row.update(archive_url=f"./{self.archive.name}", archive_size=len(payload),
                        archive_hash=f"sha256:{self.source['sha256']}")

    def validate(self):
        (self.root / "sources.json").write_text(json.dumps({ID: self.source}))
        (self.root / "index.json").write_text(json.dumps({"version": "v1", "data": [self.row]}))
        feed.validate(self.root)

    def test_valid(self):
        self.validate()

    def test_outdated(self):
        self.source["version"] = "1.1.0"
        with self.assertRaisesRegex(ValueError, "outdated package"):
            self.validate()

    def test_wrong_size(self):
        self.row["archive_size"] += 1
        with self.assertRaisesRegex(ValueError, "archive size mismatch"):
            self.validate()

    def test_same_length_corruption(self):
        content = self.archive.read_bytes()
        self.archive.write_bytes(bytes([content[0] ^ 1]) + content[1:])
        with self.assertRaisesRegex(ValueError, "index SHA-256 mismatch"):
            self.validate()

    def test_corrupt_zip_with_updated_hashes(self):
        self.archive.write_bytes(b"not a zip")
        self.rehash()
        with self.assertRaisesRegex(ValueError, "not a zip"):
            self.validate()

    def test_release_digest_mismatch(self):
        self.source["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source release SHA-256 mismatch"):
            self.validate()

    def test_invalid_toml(self):
        self.write_zip("id = [")
        self.rehash()
        with self.assertRaisesRegex(ValueError, "Invalid value"):
            self.validate()

    def test_missing_manifest_field(self):
        self.write_zip(MANIFEST.replace('name = "MW Fixture"\n', ""))
        self.rehash()
        with self.assertRaisesRegex(ValueError, "missing name"):
            self.validate()

    def test_invalid_blender_range(self):
        self.write_zip(MANIFEST + 'blender_version_max = "4.2.0"\n')
        self.rehash()
        with self.assertRaisesRegex(ValueError, "invalid Blender compatibility range"):
            self.validate()

    def test_inconsistent_blender_range(self):
        self.row["blender_version_max"] = "5.0.0"
        with self.assertRaisesRegex(ValueError, "inconsistent compatibility declaration"):
            self.validate()

    def test_legacy_compatibility_disagrees(self):
        self.write_zip(init='bl_info = {"blender": (4, 3, 0)}')
        self.rehash()
        with self.assertRaisesRegex(ValueError, "bl_info blender differs"):
            self.validate()

    def test_unsafe_index_url(self):
        self.row["archive_url"] = "../" + self.archive.name
        with self.assertRaisesRegex(ValueError, "invalid archive URL"):
            self.validate()


if __name__ == "__main__":
    unittest.main()
