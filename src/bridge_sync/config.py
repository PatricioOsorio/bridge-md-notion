"""Repo paths, .env loading and the page map. CWD-aware, no network."""
import json
import os
from pathlib import Path

_project_root = None


def set_project_root(path):
    global _project_root
    _project_root = Path(path).resolve()


def get_project_root():
    global _project_root
    if _project_root is not None:
        return _project_root
    return Path.cwd().resolve()


def get_pages_file():
    return get_project_root() / "scripts" / "notion_pages.json"


def load_dotenv():
    env_path = get_project_root() / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def load_raw(path=None):
    """The file as-is, comments included. Use when rewriting it."""
    pages_path = Path(path) if path else get_pages_file()
    if not pages_path.exists():
        return {}
    return json.loads(pages_path.read_text())


def load_pages(path=None):
    """name -> {"id", "path"}. Keys starting with "_" are comments, not pages."""
    return {k: v for k, v in load_raw(path).items() if not k.startswith("_")}


def dump_pages(raw):
    """Serialize keeping one page per line, so adding a page is a one-line git diff."""
    items = list(raw.items())
    lines = ["{"]
    for i, (key, value) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if key.startswith("_"):
            body = json.dumps(value, ensure_ascii=False)
        else:
            body = f'{{ "id": {json.dumps(value["id"])}, "path": {json.dumps(value["path"])} }}'
        lines.append(f"  {json.dumps(key)}: {body}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def add_page(name, page_id, rel_path, path=None):
    """Register a page in notion_pages.json. Refuses to overwrite an existing name."""
    pages_path = Path(path) if path else get_pages_file()
    raw = load_raw(pages_path)
    if name in raw:
        raise ValueError(f"'{name}' already in {pages_path.name} (id {raw[name]['id']})")
    raw[name] = {"id": page_id, "path": rel_path}
    pages_path.parent.mkdir(parents=True, exist_ok=True)
    pages_path.write_text(dump_pages(raw))


def remove_page(name, path=None):
    """Stop syncing a page. Touches only the map — the local .md and Notion stay put."""
    pages_path = Path(path) if path else get_pages_file()
    raw = load_raw(pages_path)
    if name not in raw or name.startswith("_"):
        raise ValueError(f"'{name}' is not in {pages_path.name}")
    entry = raw.pop(name)
    pages_path.write_text(dump_pages(raw))
    return entry
