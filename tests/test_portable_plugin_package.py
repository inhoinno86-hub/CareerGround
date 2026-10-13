import importlib.util
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "portable_builder", ROOT / "scripts/build_chatgpt_plugin.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class PortablePackageTests(unittest.TestCase):
    def test_every_skill_can_read_resources_within_its_own_directory(self):
        files = builder.portable_files()
        for skill, resources in builder.PORTABLE_SKILL_RESOURCES.items():
            for resource in resources:
                self.assertEqual(files[f"skills/{skill}/{resource}"], files[resource])
            skill_text = files[f"skills/{skill}/SKILL.md"].decode()
            self.assertNotIn("../../references", skill_text)
            self.assertNotIn("../career-review/SKILL.md", skill_text)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "scoped.zip"
            builder.build_archive(output, variant="portable")
            with zipfile.ZipFile(output) as archive:
                archive.extractall(Path(folder) / "extracted")
            setup = Path(folder) / "extracted/skills/setup"
            self.assertTrue((setup / "references/workflow.md").is_file())
            self.assertTrue((setup / "templates/project-instructions.md").is_file())

    def test_archive_has_exact_reviewed_inventory_and_no_binding_or_local_noise(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            shutil.copytree(builder.PORTABLE_SOURCE, source)
            (source / ".env").write_text("SYNTHETIC_SECRET_DO_NOT_PACKAGE")
            (source / "private-profile.json").write_text("SYNTHETIC_PERSONAL_DO_NOT_PACKAGE")
            output = Path(folder) / "portable.zip"
            with patch.object(builder, "PORTABLE_SOURCE", source):
                members = builder.build_archive(output, variant="portable")
            self.assertEqual(set(members), set(builder.PORTABLE_MEMBERS))
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(set(archive.namelist()), set(builder.PORTABLE_MEMBERS))
                contents = b"\n".join(archive.read(name) for name in members)
                self.assertNotIn(b"SYNTHETIC_SECRET_DO_NOT_PACKAGE", contents)
                self.assertNotIn(b"SYNTHETIC_PERSONAL_DO_NOT_PACKAGE", contents)
                manifest = json.loads(archive.read("plugin.json"))
                self.assertEqual(manifest["name"], "careerground-portable")
                self.assertEqual(
                    manifest["extensions"]["com.openai"]["onboardingSkill"],
                    "./skills/setup/SKILL.md",
                )
                self.assertNotIn("apps", manifest["extensions"]["com.openai"])
                self.assertFalse({"mcp.json", ".app.json", ".mcp.json"} & set(members))
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                builder.build_archive(output, variant="portable")

    def test_portable_cannot_add_any_server_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "bad.zip"
            for binding in [
                {"mcp_url": "https://host.example/mcp"},
                {"registered_server_id": "asdk_app_synthetic"},
            ]:
                with self.assertRaisesRegex(ValueError, "does not support server"):
                    builder.build_archive(output, variant="portable", **binding)
                self.assertFalse(output.exists())

    def test_symlink_source_directory_member_and_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            shutil.copytree(builder.PORTABLE_SOURCE, source)
            link = root / "linked-source"
            link.symlink_to(source, target_is_directory=True)
            with patch.object(builder, "PORTABLE_SOURCE", link), self.assertRaises(ValueError):
                builder.build_archive(root / "bad.zip", variant="portable")
            target = root / "external.md"
            target.write_text("external")
            (source / "README.md").unlink()
            (source / "README.md").symlink_to(target)
            with patch.object(builder, "PORTABLE_SOURCE", source), self.assertRaises(ValueError):
                builder.build_archive(root / "bad.zip", variant="portable")
            self.assertEqual(target.read_text(), "external")
            output = root / "out.zip"
            output.symlink_to(target)
            with self.assertRaises(FileExistsError):
                builder.build_archive(output, variant="portable")
            self.assertEqual(target.read_text(), "external")

    def test_missing_resource_and_escaping_markdown_link_fail_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            shutil.copytree(builder.PORTABLE_SOURCE, source)
            output = Path(folder) / "bad.zip"
            readme = source / "README.md"
            readme.write_text("[escape](../outside.md)")
            with patch.object(builder, "PORTABLE_SOURCE", source), self.assertRaises(ValueError):
                builder.build_archive(output, variant="portable")
            readme.write_text("[missing](not-in-package.md)")
            with patch.object(builder, "PORTABLE_SOURCE", source), self.assertRaises(ValueError):
                builder.build_archive(output, variant="portable")
            readme.unlink()
            with patch.object(builder, "PORTABLE_SOURCE", source), self.assertRaises(ValueError):
                builder.build_archive(output, variant="portable")
            self.assertFalse(output.exists())

    def test_symlink_parent_directory_is_rejected_for_sources_and_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source"
            shutil.copytree(builder.PORTABLE_SOURCE, source)
            target = root / "templates-real"
            (source / "templates").rename(target)
            (source / "templates").symlink_to(target, target_is_directory=True)
            with patch.object(builder, "PORTABLE_SOURCE", source), self.assertRaises(ValueError):
                builder.build_archive(root / "bad.zip", variant="portable")
            output_folder = root / "output"
            output_folder.mkdir()
            link = root / "linked-output"
            link.symlink_to(output_folder, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Symlink output directory"):
                builder.build_archive(link / "bad.zip", variant="portable")
            self.assertFalse((output_folder / "bad.zip").exists())
