"""CLI entry point for bridge-sync."""
import argparse
import sys
from pathlib import Path

from . import commands, config, notion


def build_parser(pages):
    page_names = sorted(pages.keys())
    parser = argparse.ArgumentParser(
        description="Bridge Markdown <-> Notion sync tool."
    )
    parser.add_argument(
        "-C", "--dir",
        default=".",
        help="Target project directory (default: current working directory)"
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    # pull
    pull_p = subparsers.add_parser("pull", help="Pull page(s) from Notion -> local Markdown")
    pull_g = pull_p.add_mutually_exclusive_group(required=True)
    pull_g.add_argument("--page", choices=page_names, metavar="PAGE", help="Single registered page")
    pull_g.add_argument("--all", action="store_true", help="All registered pages")

    # push
    push_p = subparsers.add_parser("push", help="Push local Markdown -> Notion page(s)")
    push_g = push_p.add_mutually_exclusive_group(required=True)
    push_g.add_argument("--page", choices=page_names, metavar="PAGE", help="Single registered page")
    push_g.add_argument("--all", action="store_true", help="All registered pages")

    # create
    create_p = subparsers.add_parser("create", help="Create a new page in Notion and register it")
    create_p.add_argument("--name", required=True, help="Internal short name (e.g. semana-15)")
    create_p.add_argument("--title", required=True, help="Notion visible page title")
    create_p.add_argument("--parent", required=True, help="Parent Notion page ID")
    create_p.add_argument("--path", required=True, help="Relative path to local .md file")

    # delete
    del_p = subparsers.add_parser("delete", help="Send a page to Notion trash")
    del_g = del_p.add_mutually_exclusive_group(required=True)
    del_g.add_argument("--page", choices=page_names, metavar="PAGE", help="Registered page to delete")
    del_g.add_argument("--id", metavar="URL_OR_ID", help="Unregistered page URL or ID")
    del_p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # unlink
    unl_p = subparsers.add_parser("unlink", help="Unregister a page without touching Notion or disk")
    unl_p.add_argument("--page", required=True, choices=page_names, metavar="PAGE")

    # check
    subparsers.add_parser("check", help="Verify workspace integrity and notion_pages.json map")

    return parser


def confirm_prompt(label, page_id, path):
    print(f"About to archive in Notion: '{label}' ({page_id})")
    if path:
        print(f"Local file WILL BE KEPT: {path}")
    answer = input("Type the page name/label to confirm: ").strip()
    return answer == label


def main():
    # Pre-parse -C/--dir before loading config
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("-C", "--dir", default=".")
    pre_args, _ = pre_parser.parse_known_args()

    project_dir = Path(pre_args.dir).resolve()
    config.set_project_root(project_dir)
    config.load_dotenv()

    pages = config.load_pages()
    parser = build_parser(pages)
    args = parser.parse_args()

    try:
        if args.action == "pull":
            targets = pages if args.all else {args.page: pages[args.page]}
            for name, page in targets.items():
                commands.pull(name, page)

        elif args.action == "push":
            targets = pages if args.all else {args.page: pages[args.page]}
            for name, page in targets.items():
                commands.push(name, page)

        elif args.action == "create":
            commands.create(args.name, args.title, args.parent, args.path)

        elif args.action == "unlink":
            commands.unlink(args.page)

        elif args.action == "delete":
            confirm = (lambda l, i, p: True) if args.yes else confirm_prompt
            commands.delete(name=args.page, ref=args.id, confirm=confirm)

        elif args.action == "check":
            commands.check()

    except notion.NotionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
