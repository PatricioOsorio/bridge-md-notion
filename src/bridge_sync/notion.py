"""Notion REST client (stdlib urllib). Raises NotionError; never exits the process."""
import json
import os
import urllib.error
import urllib.request

NOTION_VERSION = "2022-06-28"
API = "https://api.notion.com/v1"
MAX_CHILDREN_PER_CALL = 100


class NotionError(Exception):
    pass


def api_request(method, path, body=None):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise NotionError("NOTION_TOKEN not set. Put it in .env (see documentation)")
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body is not None else None

    for attempt in range(3):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Notion-Version", NOTION_VERSION)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise NotionError(f"Notion API error {e.code} on {method} {path}: {e.read().decode()}")
        except urllib.error.URLError as e:
            if attempt == 2:
                raise NotionError(f"Network error on {method} {path}: {e.reason}")


def get_all_blocks(block_id):
    blocks = []
    cursor = None
    while True:
        qs = f"?start_cursor={cursor}" if cursor else ""
        res = api_request("GET", f"/blocks/{block_id}/children{qs}")
        blocks.extend(res["results"])
        if not res.get("has_more"):
            break
        cursor = res["next_cursor"]
    return blocks


def create_page(parent_id, title, icon=None):
    """New empty child page under parent_id. Returns its page ID."""
    body = {
        "parent": {"page_id": parent_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
    }
    if icon:
        body["icon"] = {"type": "emoji", "emoji": icon}
    res = api_request("POST", "/pages", body)
    return res["id"]


def set_page_icon(page_id, icon):
    """Set the emoji icon of an existing page."""
    return api_request("PATCH", f"/pages/{page_id}", {"icon": {"type": "emoji", "emoji": icon}})


def get_page(page_id):
    return api_request("GET", f"/pages/{page_id}")


def page_title(page):
    """Plain-text title of a page object, or "" if it has none."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop["title"])
    return ""


def page_icon(page):
    """Emoji icon of a page object, or None if it has none."""
    icon = page.get("icon")
    if icon and icon.get("type") == "emoji":
        return icon.get("emoji")
    return None


def archive_page(page_id):
    """Move the page to Notion's trash."""
    return api_request("PATCH", f"/pages/{page_id}", {"archived": True})


def replace_children(page_id, existing, new_blocks):
    """Delete existing non-subpage blocks, then append new_blocks."""
    for b in existing:
        if b.get("type") == "child_page":
            continue
        try:
            api_request("DELETE", f"/blocks/{b['id']}")
        except NotionError:
            pass
    for start in range(0, len(new_blocks), MAX_CHILDREN_PER_CALL):
        chunk = new_blocks[start:start + MAX_CHILDREN_PER_CALL]
        api_request("PATCH", f"/blocks/{page_id}/children", {"children": chunk})
