"""Pure markdown <-> Notion-block conversion. No network, no I/O — testable with plain dicts."""
import re
import sys

from . import links as lk

FRONTMATTER_RE = re.compile(r"^---\r?\n.*?\r?\n---\s*(?:\n|$)", re.DOTALL)

_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
# Leading emoji (+ variation selector / ZWJ) on a heading — the page's Notion
# icon already carries it, so the synced title stays plain text.
_LEADING_EMOJI_RE = re.compile(r"^[\U0001F000-\U0001FFFF☀-➿️‍]+\s*")


def first_h1_title(body):
    """First ATX H1 in `body` (frontmatter already stripped), emoji-stripped.

    None if the document has no H1 — callers should leave the Notion page
    title untouched in that case rather than clearing it.
    """
    m = _H1_RE.search(body)
    if not m:
        return None
    title = _LEADING_EMOJI_RE.sub("", m.group(1)).strip()
    return title or None

# ---------- Notion blocks -> markdown (pull) ----------


def rich_text_to_md(rich_text, links=None):
    """links: a LinkMap. With it, Notion links to synced pages become Obsidian wikilinks."""
    parts = []
    for rt in rich_text:
        text = rt.get("plain_text", "")
        ann = rt.get("annotations", {})
        href = rt.get("href")

        target = links.name_for_url(href) if links else None
        if target:
            parts.append(lk.to_wikilink(target, text))
            continue

        if ann.get("code"):
            text = f"`{text}`"
        if ann.get("italic"):
            text = f"*{text}*"
        if ann.get("bold"):
            text = f"**{text}**"
        if href:
            text = f"[{text}]({href})"
        parts.append(text)
    return "".join(parts)


def rows_to_md(rows, links=None):
    """rows: the table_row blocks of a table, already fetched."""
    lines = []
    for i, row in enumerate(rows):
        cells = row["table_row"]["cells"]
        cell_texts = [rich_text_to_md(c, links).replace("\n", "<br>") for c in cells]
        lines.append("| " + " | ".join(cell_texts) + " |")
        if i == 0:
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(lines)


def blocks_to_md(blocks, fetch_children=None, links=None, fetch_page_info=None):
    """fetch_children(block_id) -> child blocks. Required only if tables/columns appear.
    links: a LinkMap, to turn Notion page links into wikilinks.
    fetch_page_info: optional callable(page_id) -> (title, icon_emoji) for subpages."""

    def children(block_id):
        if fetch_children is None:
            raise ValueError("this block has children; pass fetch_children")
        return fetch_children(block_id)

    def inline(rich_text):
        return rich_text_to_md(rich_text, links)

    out = []
    for b in blocks:
        t = b["type"]
        if t == "paragraph":
            text = inline(b["paragraph"]["rich_text"])
            if text:
                out.append(text)
        elif t in ("heading_1", "heading_2", "heading_3"):
            level = int(t[-1])
            out.append("#" * level + " " + inline(b[t]["rich_text"]))
        elif t == "bulleted_list_item":
            out.append("- " + inline(b[t]["rich_text"]))
        elif t == "numbered_list_item":
            out.append("1. " + inline(b[t]["rich_text"]))
        elif t == "quote":
            out.append("> " + inline(b[t]["rich_text"]))
        elif t == "callout":
            icon = b["callout"].get("icon", {}).get("emoji", "")
            out.append(f"> {icon} " + inline(b["callout"]["rich_text"]))
        elif t == "code":
            lang = b["code"].get("language", "plain text")
            code_text = inline(b["code"]["rich_text"])
            out.append(f"```{lang}\n{code_text}\n```")
        elif t == "divider":
            out.append("---")
        elif t == "table":
            out.append(rows_to_md(children(b["id"]), links))
        elif t == "column_list":
            parts = []
            for col in children(b["id"]):
                parts.append(blocks_to_md(children(col["id"]), fetch_children, links, fetch_page_info).strip())
            out.append("\n\n".join(p for p in parts if p))
        elif t == "child_page":
            title = b.get("child_page", {}).get("title", "")
            page_id = b["id"]
            target = links.name_for_id(page_id) if links else None
            info_title, icon = fetch_page_info(page_id) if fetch_page_info else (None, None)
            display_title = title or info_title
            prefix = f"{icon} " if icon else ""
            if target:
                out.append(prefix + lk.to_wikilink(target, display_title))
            else:
                url = f"https://www.notion.so/{page_id.replace('-', '')}"
                out.append(prefix + f"[{display_title}]({url})")
        elif t == "link_to_page":
            lp = b.get("link_to_page", {})
            page_id = lp.get("page_id")
            if page_id:
                target = links.name_for_id(page_id) if links else None
                info_title, icon = fetch_page_info(page_id) if fetch_page_info else (None, None)
                display_title = info_title or target or page_id
                prefix = f"{icon} " if icon else ""
                if target:
                    out.append(prefix + lk.to_wikilink(target, display_title))
                else:
                    url = f"https://www.notion.so/{page_id.replace('-', '')}"
                    out.append(prefix + f"[{display_title}]({url})")
        else:
            print(f"  ! unsupported block type skipped: {t}", file=sys.stderr)
            continue
        out.append("")
    return "\n".join(out).strip() + "\n"


# ---------- local markdown -> Notion blocks (push) ----------

_INLINE_RE = re.compile(
    r"\[\[(?P<wiki>[^\]|]+(?:\|[^\]]+)?)\]\]"
    r"|\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)]+)\)"
    r"|\*\*\*(?P<bolditalic>\S.+?\S)\*\*\*"
    r"|\*\*(?P<bold>\S.+?\S|\S)\*\*|(?<!\w)__(?P<bold2>\S.+?\S|\S)__(?!\w)"
    r"|`(?P<code>.+?)`"
    r"|(?<!\*)\*(?P<italic>[^\s*].*?\b|\S)\*(?!\*)"
    r"|(?<!\w)_(?P<italic2>\S.+?\S|\S)_(?!\w)"
)


def _text_run(content, bold=False, italic=False, code=False, href=None):
    obj = {"type": "text", "text": {"content": content}}
    if href:
        obj["text"]["link"] = {"url": href}
    ann = {}
    if bold:
        ann["bold"] = True
    if italic:
        ann["italic"] = True
    if code:
        ann["code"] = True
    if ann:
        obj["annotations"] = ann
    return obj


def md_inline_to_rich_text(text, links=None):
    """links: a LinkMap. With it, [[wikilinks]] become real Notion page links."""
    runs = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            runs.append(_text_run(text[pos:m.start()]))
        if m.group("wiki"):
            target, label = lk.split_wikilink(m.group("wiki"))
            url = links.url_for_name(target) if links else None
            runs.append(_text_run(label, href=url) if url else _text_run(m.group(0)))
        elif m.group("ltext"):
            runs.append(_text_run(m.group("ltext"), href=m.group("lurl")))
        elif m.group("bolditalic"):
            runs.append(_text_run(m.group("bolditalic"), bold=True, italic=True))
        elif m.group("bold") or m.group("bold2"):
            runs.append(_text_run(m.group("bold") or m.group("bold2"), bold=True))
        elif m.group("code"):
            runs.append(_text_run(m.group("code"), code=True))
        elif m.group("italic") or m.group("italic2"):
            runs.append(_text_run(m.group("italic") or m.group("italic2"), italic=True))
        pos = m.end()
    if pos < len(text):
        runs.append(_text_run(text[pos:]))
    return runs or [_text_run("")]


_PAGE_LINK_LINE_RE = re.compile(
    r"^(?:[-*]\s+|\d+\.\s+)?(?P<prefix>.*?)"
    r"(?:\[\[(?P<wiki>[^\]|]+)(?:\|(?P<alias>[^\]]+))?\]\]|\[(?P<ltext>[^\]]+)\]\((?P<lurl>[^)]+)\))\s*$"
)


def _extract_page_link_block(line, links, check_page_valid=None):
    if not links:
        return None
    m = _PAGE_LINK_LINE_RE.match(line)
    if not m:
        return None
    prefix = (m.group("prefix") or "").strip()
    if prefix and any(c.isalpha() for c in prefix):
        return None
    target = None
    if m.group("wiki"):
        target = m.group("wiki").strip()
    elif m.group("lurl"):
        target = links.name_for_url(m.group("lurl"))
    if not target:
        return None
    page_id = links.by_name.get(target)
    if not page_id:
        return None
    if check_page_valid and not check_page_valid(page_id):
        return None
    return {"type": "link_to_page", "link_to_page": {"type": "page_id", "page_id": page_id}}


def _line_to_block(line, links=None, check_page_valid=None):
    page_block = _extract_page_link_block(line, links, check_page_valid)
    if page_block:
        return page_block
    if line.startswith("#### "):
        return {"type": "heading_3", "heading_3": {"rich_text": md_inline_to_rich_text(line[5:], links)}}
    if line.startswith("### "):
        return {"type": "heading_3", "heading_3": {"rich_text": md_inline_to_rich_text(line[4:], links)}}
    if line.startswith("## "):
        return {"type": "heading_2", "heading_2": {"rich_text": md_inline_to_rich_text(line[3:], links)}}
    if line.startswith("# "):
        return {"type": "heading_1", "heading_1": {"rich_text": md_inline_to_rich_text(line[2:], links)}}
    if line.startswith("> "):
        return {"type": "quote", "quote": {"rich_text": md_inline_to_rich_text(line[2:], links)}}
    if line.startswith("- "):
        return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": md_inline_to_rich_text(line[2:], links)}}
    if re.match(r"^\d+\.\s", line):
        content = re.sub(r"^\d+\.\s", "", line)
        return {"type": "numbered_list_item", "numbered_list_item": {"rich_text": md_inline_to_rich_text(content, links)}}
    if line == "---":
        return {"type": "divider", "divider": {}}
    return {"type": "paragraph", "paragraph": {"rich_text": md_inline_to_rich_text(line, links)}}


def _is_separator_row(cells):
    return all(set(c.replace("-", "").replace(":", "").strip()) == set() for c in cells)


def _table_block(rows, links=None):
    width = len(rows[0])
    children = []
    for row in rows:
        cells = [md_inline_to_rich_text(c.replace("<br>", "\n"), links) for c in row]
        children.append({"type": "table_row", "table_row": {"cells": cells}})
    return {
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": children,
        },
    }


def md_to_blocks(text, links=None, check_page_valid=None):
    lines = text.strip("\n").split("\n")
    blocks = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("```"):
            lang = line[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n and lines[i].strip().startswith("```"):
                i += 1
            code_content = "\n".join(code_lines)
            blocks.append({
                "type": "code",
                "code": {
                    "rich_text": md_inline_to_rich_text(code_content, links),
                    "language": lang.lower(),
                },
            })
            continue
        if line.startswith("|"):
            table_rows = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not _is_separator_row(cells):
                    table_rows.append(cells)
                i += 1
            if table_rows:
                blocks.append(_table_block(table_rows, links))
            continue
        blocks.append(_line_to_block(line, links, check_page_valid))
        i += 1
    return blocks
