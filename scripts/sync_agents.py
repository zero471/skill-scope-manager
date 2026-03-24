from __future__ import annotations

import argparse

from _scope_lib import load_registry, sync_scope_agents


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync AGENTS.md managed blocks from the skill scope registry.")
    parser.add_argument("--scope-root", help="Only sync a single scope root.")
    parser.add_argument("--apply", action="store_true", help="Write changes to disk.")
    args = parser.parse_args()

    registry = load_registry()
    scopes = registry.get("scopes", [])
    if args.scope_root:
        scopes = [scope for scope in scopes if scope["scope_root"] == args.scope_root]
    if not scopes:
        raise SystemExit("No matching scopes found.")
    for scope in scopes:
        sync_scope_agents(registry, scope, apply=args.apply)
        action = "Synced" if args.apply else "Would sync"
        print(f"{action}: {scope['agents_path']}")


if __name__ == "__main__":
    main()
