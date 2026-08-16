#!/usr/bin/env python3
"""Offline self-check for bridge_sync package."""
import unittest
from bridge_sync.links import LinkMap
from bridge_sync.markdown import (
    blocks_to_md,
    md_inline_to_rich_text,
    md_to_blocks,
    rich_text_to_md,
)


class TestBridgeSync(unittest.TestCase):
    def test_rich_text_to_md(self):
        rt = [
            {"plain_text": "peso", "annotations": {"bold": True}, "href": None},
            {"plain_text": " normal", "annotations": {}, "href": None},
        ]
        self.assertEqual(rich_text_to_md(rt), "**peso** normal")

    def test_blocks_to_md(self):
        blocks = [
            {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Título", "annotations": {}, "href": None}]}},
            {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Contenido", "annotations": {}, "href": None}]}},
        ]
        md = blocks_to_md(blocks)
        self.assertEqual(md, "# Título\n\nContenido\n")

    def test_md_to_blocks_table(self):
        text = (
            "# Título\n\n"
            "| Ejercicio | Peso |\n"
            "| --- | --- |\n"
            "| Press | 20kg |\n"
        )
        blocks = md_to_blocks(text)
        types = [b["type"] for b in blocks]
        self.assertEqual(types, ["heading_1", "table"])
        table = blocks[1]["table"]
        self.assertEqual(table["table_width"], 2)
        self.assertEqual(len(table["children"]), 2)

    def test_link_map(self):
        pages = {"semana-01": {"id": "3a30b31fce98801dbdf9d153cf7c2f34", "path": "logs/semana-01.md"}}
        lm = LinkMap(pages)
        self.assertEqual(lm.name_for_id("3a30b31fce98801dbdf9d153cf7c2f34"), "semana-01")

    def test_split_wikilink_strips_heading_anchor(self):
        from bridge_sync.links import split_wikilink

        self.assertEqual(split_wikilink("calentamiento"), ("calentamiento", "calentamiento"))
        self.assertEqual(
            split_wikilink("calentamiento#🅿️ Push (Lunes / Viernes)"),
            ("calentamiento", "calentamiento"),
        )
        self.assertEqual(
            split_wikilink("calentamiento#Push|ver calentamiento"),
            ("calentamiento", "ver calentamiento"),
        )

    def test_frontmatter_regex(self):
        from bridge_sync.markdown import FRONTMATTER_RE
        text1 = "---\ntags:\n  - gym\n---\n\n# Body"
        text2 = "---\ntags:\n  - gym\n---\n# Body"
        text3 = "---\ntags:\n  - gym\n---   \n# Body"
        self.assertEqual(FRONTMATTER_RE.sub("", text1), "# Body")
        self.assertEqual(FRONTMATTER_RE.sub("", text2), "# Body")
        self.assertEqual(FRONTMATTER_RE.sub("", text3), "# Body")

    def test_check_integrity(self):
        import tempfile
        from pathlib import Path
        from bridge_sync import config, commands

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scripts_dir = tmp_path / "scripts"
            scripts_dir.mkdir()

            md_file = tmp_path / "note.md"
            md_file.write_text("# Note")

            pages_file = scripts_dir / "notion_pages.json"
            pages_file.write_text('{\n  "note": {"id": "123", "path": "note.md"}\n}\n')

            config.set_project_root(tmp_path)
            commands.check()

            pages_file.write_text('{\n  "wrong_name": {"id": "123", "path": "note.md"}\n}\n')
            with self.assertRaises(ValueError):
                commands.check()


if __name__ == "__main__":
    unittest.main()
