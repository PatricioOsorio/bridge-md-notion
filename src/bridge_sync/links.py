"""Translate links between Notion and Obsidian. Pure — built from the page map, no I/O."""
import re

NOTION_HOST_RE = re.compile(r"^https?://(?:www\.)?notion\.so/", re.IGNORECASE)
ID_IN_URL_RE = re.compile(r"([0-9a-f]{32})(?:[?#].*)?$", re.IGNORECASE)


def _normalize_id(page_id):
    return page_id.replace("-", "").lower()


def page_url(page_id):
    return f"https://www.notion.so/{_normalize_id(page_id)}"


class LinkMap:
    """name <-> page id, where `name` is the key in notion_pages.json."""

    def __init__(self, pages):
        self.by_name = {name: page["id"] for name, page in pages.items()}
        self.by_id = {_normalize_id(page["id"]): name for name, page in pages.items()}

    def name_for_url(self, href):
        """Wikilink target for a Notion URL, or None if it isn't a mapped page."""
        if not href or not NOTION_HOST_RE.match(href):
            return None
        m = ID_IN_URL_RE.search(href)
        return self.by_id.get(m.group(1).lower()) if m else None

    def name_for_id(self, page_id):
        """Wikilink target for a 32-hex page id (with or without dashes), or None."""
        if not page_id:
            return None
        return self.by_id.get(_normalize_id(page_id))

    def url_for_name(self, name):
        """Notion URL for a wikilink target, or None if that page isn't mapped."""
        page_id = self.by_name.get(name)
        return page_url(page_id) if page_id else None


def to_wikilink(target, text=None):
    """[[target]], or [[target|text]] when visible text differs."""
    if text and text != target:
        return f"[[{target}|{text}]]"
    return f"[[{target}]]"


def split_wikilink(inner):
    """"name|texto" -> ("name", "texto"); "name" -> ("name", "name")."""
    target, sep, alias = inner.partition("|")
    target = target.strip()
    return target, (alias.strip() if sep else target)
