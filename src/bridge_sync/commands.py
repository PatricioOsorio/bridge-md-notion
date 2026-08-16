"""pull / push orchestration: wires the Notion client to the markdown converters."""
import re

from datetime import datetime

from . import markdown as md
from . import notion
from .config import add_page, get_project_root, load_pages, remove_page
from .links import ID_IN_URL_RE, LinkMap

_page_info_cache = {}


def _get_backup_dir():
    return get_project_root() / ".notion-backups"


def _fetch_page_info(page_id):
    if page_id not in _page_info_cache:
        try:
            p = notion.get_page(page_id)
            t = notion.page_title(p)
            i = notion.page_icon(p)
            _page_info_cache[page_id] = (t, i)
        except Exception:
            _page_info_cache[page_id] = ("", None)
    return _page_info_cache[page_id]


def _local_path(page):
    return get_project_root() / page["path"]


def _link_map():
    return LinkMap(load_pages())


def _page_to_md(page_id):
    blocks = notion.get_all_blocks(page_id)
    return blocks, md.blocks_to_md(blocks, notion.get_all_blocks, _link_map(), _fetch_page_info)


def pull(name, page):
    local_path = _local_path(page)
    blocks, body = _page_to_md(page["id"])

    frontmatter = ""
    if local_path.exists():
        m = md.FRONTMATTER_RE.match(local_path.read_text())
        if m:
            frontmatter = m.group(0).rstrip("\n") + "\n\n"

    try:
        page_obj = notion.get_page(page["id"])
        icon = notion.page_icon(page_obj)
        if icon:
            if frontmatter:
                if re.search(r"^icon:", frontmatter, re.MULTILINE):
                    frontmatter = re.sub(r"^icon:.*$", f'icon: "{icon}"', frontmatter, flags=re.MULTILINE)
                else:
                    frontmatter = re.sub(r"\n---\s*$", f'\nicon: "{icon}"\n---', frontmatter.strip()) + "\n\n"
            else:
                frontmatter = f'---\nicon: "{icon}"\n---\n\n'
    except Exception:
        pass

    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(frontmatter + body)
    print(f"pulled {name} ({len(blocks)} top-level blocks)")
    _run_prettier(local_path)


def _run_prettier(path):
    import subprocess
    try:
        subprocess.run(
            ["npx", "prettier", "--write", str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


_page_valid_cache = {}


def _check_page_valid(page_id):
    if page_id not in _page_valid_cache:
        try:
            notion.get_page(page_id)
            _page_valid_cache[page_id] = True
        except Exception:
            _page_valid_cache[page_id] = False
    return _page_valid_cache[page_id]


def push(name, page):
    local_path = _local_path(page)
    if not local_path.exists():
        raise FileNotFoundError(f"{local_path} does not exist, nothing to push")

    text = local_path.read_text()
    body = md.FRONTMATTER_RE.sub("", text)
    new_blocks = md.md_to_blocks(body, _link_map(), _check_page_valid)

    m_icon = re.search(r"^icon:\s*[\"']?([^\n\"']+)[\"']?", text, re.MULTILINE)
    if m_icon:
        try:
            notion.set_page_icon(page["id"], m_icon.group(1).strip())
        except Exception:
            pass

    existing, current_md = _page_to_md(page["id"])
    backup_dir = _get_backup_dir()
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.md"
    backup.write_text(current_md)

    notion.replace_children(page["id"], existing, new_blocks)
    print(f"pushed {name} ({len(existing)} blocks replaced with {len(new_blocks)}, backup: {backup.name})")


def _backup(name, text):
    backup_dir = _get_backup_dir()
    backup_dir.mkdir(exist_ok=True)
    path = backup_dir / f"{name}-{datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text(text)
    return path


def parse_page_ref(ref):
    compact = ref.strip().replace("-", "")
    m = ID_IN_URL_RE.search(compact)
    if not m:
        raise ValueError(f"no Notion page id found in {ref!r}")
    return m.group(1).lower()


def orphaned_wikilinks(name, data_dir=None):
    root = get_project_root()
    data_dir = data_dir or (root / "data")
    if not data_dir.exists():
        return []
    needle = f"[[{name}"
    hits = []
    for path in sorted(data_dir.rglob("*.md")):
        text = path.read_text()
        if f"{needle}]]" in text or f"{needle}|" in text:
            hits.append(_display_path(path))
    return hits


def _display_path(path):
    root = get_project_root()
    try:
        return path.relative_to(root)
    except ValueError:
        return path


def unlink(name):
    entry = remove_page(name)
    print(f"unlinked {name} — Notion page {entry['id']} and {entry['path']} both left untouched")
    _warn_orphans(name)


def _warn_orphans(name):
    orphans = orphaned_wikilinks(name)
    if orphans:
        print(f"  ! [[{name}]] still referenced in: {', '.join(str(o) for o in orphans)}")
        print("    those links stay readable in Obsidian but upload as plain text now")


def delete(name=None, ref=None, confirm=None):
    pages = load_pages()

    if name:
        page = pages[name]
        page_id, label, path = page["id"], name, page["path"]
    else:
        page_id = parse_page_ref(ref)
        path = None
        registered = [n for n, p in pages.items() if p["id"].replace("-", "") == page_id]
        if registered:
            raise ValueError(
                f"that page is registered as '{registered[0]}' — use --page {registered[0]} "
                "so the local file gets updated first"
            )
        label = notion.page_title(notion.get_page(page_id)) or page_id

    if confirm and not confirm(label, page_id, path):
        print("aborted, nothing changed")
        return

    if name:
        pull(name, pages[name])
    else:
        _, body = _page_to_md(page_id)
        saved = _backup(label.replace("/", "-"), body)
        print(f"saved a copy to {saved.relative_to(get_project_root())}")

    notion.archive_page(page_id)
    print(f"archived '{label}' in Notion (recoverable from its trash)")

    if name:
        remove_page(name)
        print(f"unregistered {name} — {path} stays on disk")
        _warn_orphans(name)
def create(name, title, parent_id, rel_path):
    local_path = get_project_root() / rel_path
    icon = None
    if local_path.exists():
        text = local_path.read_text()
        m_icon = re.search(r"^icon:\s*[\"']?([^\n\"']+)[\"']?", text, re.MULTILINE)
        if m_icon:
            icon = m_icon.group(1).strip()

    page_id = notion.create_page(parent_id, title, icon=icon)
    add_page(name, page_id, rel_path)
    print(f"created {name} in Notion ({page_id}) and registered it")

    if not local_path.exists():
        print(f"  {rel_path} does not exist yet — page is empty, push it once you write it")
        return
    body = md.FRONTMATTER_RE.sub("", local_path.read_text())
    blocks = md.md_to_blocks(body, _link_map())
    notion.replace_children(page_id, [], blocks)
    print(f"  uploaded {rel_path} ({len(blocks)} blocks)")


def check():
    """Verify integrity of local project workspace and notion_pages.json map."""
    from pathlib import Path
    pages = load_pages()
    if not pages:
        raise ValueError("notion_pages.json is empty or not found in workspace")

    errors = []
    root = get_project_root()
    stems = []

    for name, page in pages.items():
        if not page.get("id") or not page.get("path"):
            errors.append(f"Page '{name}' is missing 'id' or 'path' in map")
            continue

        local_file = root / page["path"]
        if not local_file.exists():
            errors.append(f"Page '{name}' -> {page['path']} does not exist on disk")

        stem = Path(page["path"]).stem
        if name != stem:
            errors.append(f"Key '{name}' does not match file stem '{stem}' ({page['path']})")
        stems.append(stem)

    if len(stems) != len(set(stems)):
        duplicates = [s for s in stems if stems.count(s) > 1]
        errors.append(f"Duplicate markdown basenames found: {set(duplicates)}")

    if errors:
        raise ValueError("Workspace integrity errors found:\n  - " + "\n  - ".join(errors))

    print(f"Workspace integrity OK ({len(pages)} registered pages validated)")
