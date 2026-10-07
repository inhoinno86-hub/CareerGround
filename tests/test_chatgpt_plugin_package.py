import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "build_chatgpt_plugin", Path(__file__).resolve().parents[1] / "scripts/build_chatgpt_plugin.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PluginPackageTests(unittest.TestCase):
    def test_archive_contains_only_skill_manifest_and_explicit_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "trial.zip"
            members = builder.build_archive(output, registered_server_id="asdk_app_synthetic_1")
            self.assertEqual(set(members), {"plugin.json", ".app.json", builder.SKILL})
            with zipfile.ZipFile(output) as archive:
                manifest = json.loads(archive.read("plugin.json"))
                self.assertEqual(manifest["extensions"]["com.openai"]["apps"], "./.app.json")
                self.assertEqual(
                    json.loads(archive.read(".app.json"))["apps"]["careerground"]["id"],
                    "asdk_app_synthetic_1",
                )
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_existing_output_and_symlink_target_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "keep.zip"
            target.write_bytes(b"preserve")
            link = Path(folder) / "link.zip"
            link.symlink_to(target)
            for path in [target, link]:
                with self.assertRaises(FileExistsError):
                    builder.build_archive(path)
            self.assertEqual(target.read_bytes(), b"preserve")

    def test_invalid_binding_never_creates_an_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "invalid.zip"
            for kwargs in [
                {"registered_server_id": "unregistered"},
                {"mcp_url": "http://remote.example/mcp"},
                {"mcp_url": "https://secret@host.example/mcp"},
                {"mcp_url": "https://host.example/mcp?api_key=secret"},
                {
                    "registered_server_id": "asdk_app_synthetic",
                    "mcp_url": "https://host.example/mcp",
                },
            ]:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    builder.build_archive(output, **kwargs)
                self.assertFalse(output.exists())
