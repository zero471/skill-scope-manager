from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

from _scope_lib import (
    REGISTRY_MD,
    REGISTRY_YAML,
    active_instances,
    borrow_candidates,
    collect_audit_issues,
    cwd_active_scope_ids,
    discover_all_registry_skills,
    ensure_scope,
    ensure_skill_record,
    get_instance,
    get_scope,
    get_skill_record,
    load_registry,
    normalize_path,
    now_iso,
    parse_skill_metadata,
    remove_instance,
    resolve_borrow_instance,
    save_registry,
    save_registry_markdown,
    skills_available_here,
    sync_scope_agents,
    upsert_instance,
)


def print_skill_list(registry: dict[str, Any]) -> None:
    print("Managed skills:")
    for skill in sorted(registry.get("skills", []), key=lambda item: item["skill_name"]):
        scope_roots = ", ".join(instance["scope_root"] for instance in skill.get("instances", []))
        print(f"- {skill['skill_name']} [{skill['status']}] ({len(skill.get('instances', []))} instances)")
        print(f"  scopes: {scope_roots}")


def print_where(registry: dict[str, Any], skill_name: str) -> None:
    skill = get_skill_record(registry, skill_name)
    if not skill:
        raise SystemExit(f"Skill not found in registry: {skill_name}")
    print(f"Skill: {skill['skill_name']}")
    print(f"Status: {skill['status']}")
    print(f"Description: {skill['description']}")
    for instance in skill.get("instances", []):
        print(f"- Scope: {instance['scope_root']}")
        print(f"  Dir: {instance['skill_dir']}")
        print(f"  SKILL.md: {instance['skill_md_path']}")
        print(f"  Protected: {instance['is_protected']}")


def print_here(registry: dict[str, Any], cwd: str) -> None:
    matches = skills_available_here(registry, cwd)
    print(f"Active skills for {normalize_path(cwd)}:")
    for match in matches:
        skill = match["skill"]
        scopes = ", ".join(instance["scope_root"] for instance in match["instances"])
        print(f"- {skill['skill_name']} ({scopes})")


def print_audit(registry: dict[str, Any]) -> None:
    issues = collect_audit_issues(registry)
    if not issues:
        print("No audit issues found.")
        return
    print("Audit issues:")
    for issue in issues:
        detail = issue.get("path") or issue.get("skill") or ""
        print(f"- {issue['type']}: {detail}")


def print_discover(registry: dict[str, Any], unregistered_only: bool) -> None:
    registered = {
        normalize_path(instance["skill_md_path"])
        for skill in registry.get("skills", [])
        for instance in skill.get("instances", [])
    }
    discovered = discover_all_registry_skills(registry)
    if unregistered_only:
        discovered = [item for item in discovered if normalize_path(item["skill_md_path"]) not in registered]
    if not discovered:
        print("No matching discovered skills.")
        return
    for item in discovered:
        print(f"- {item['name']}: {item['skill_dir']} -> {item['scope_root']}")


def print_borrow_preview(registry: dict[str, Any], query: str, cwd: str) -> None:
    cwd_path = normalize_path(cwd)
    matches = borrow_candidates(registry, query, cwd_path)
    if not matches:
        print(f"No out-of-scope skills matched query: {query}")
        return
    print(f"Borrow candidates for {query!r} from {cwd_path}:")
    for match in matches:
        skill = match["skill"]
        reasons = ", ".join(match["reasons"])
        print(f"- {skill['skill_name']} [score={match['score']}]")
        print(f"  Why: {reasons}")
        print(f"  Description: {skill['description']}")
        for instance in match["instances"]:
            print(f"  Scope: {instance['scope_root']}")
            print(f"  SKILL.md: {instance['skill_md_path']}")
        print("  Borrow mode: single invocation, requires explicit confirmation each time")


def print_borrow_resolve(registry: dict[str, Any], skill_name: str, cwd: str, scope_root: str | None) -> None:
    try:
        skill, instance, cwd_path = resolve_borrow_instance(registry, skill_name, cwd, scope_root)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Borrow resolve for {skill_name!r} from {cwd_path}:")
    print(f"Skill: {skill['skill_name']}")
    print(f"Description: {skill['description']}")
    print(f"Target scope: {instance['scope_root']}")
    print(f"Skill dir: {instance['skill_dir']}")
    print(f"SKILL.md: {instance['skill_md_path']}")
    print("Borrow mode: single invocation only")
    print("Confirmation required: yes")
    print("Persistence: none")


def command_bootstrap(args: argparse.Namespace) -> None:
    raise SystemExit(
        "bootstrap is deprecated. Use scripts/skill_scope_init.py with "
        "init-status, init-discover, init-preview, and init-apply."
    )


def command_register(args: argparse.Namespace) -> None:
    registry = load_registry()
    incoming = parse_skill_metadata(args.skill_dir)
    scope = ensure_scope(registry, args.scope_root, scope_type=args.scope_type)
    destination = Path(scope["skills_dir"]) / Path(incoming["skill_dir"]).name
    needs_move = normalize_path(destination) != normalize_path(incoming["skill_dir"])
    print(f"Register skill: {incoming['name']}")
    print(f"Current dir: {incoming['skill_dir']}")
    print(f"Target scope: {scope['scope_root']}")
    print(f"Target dir: {normalize_path(destination)}")
    if needs_move:
        print("Action: move skill directory into target scope")
    else:
        print("Action: register in place")
    if not args.apply:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if needs_move:
        if destination.exists():
            raise SystemExit(f"Target already exists: {destination}")
        shutil.move(incoming["skill_dir"], destination)
        incoming = parse_skill_metadata(destination)
    skill = ensure_skill_record(
        registry,
        incoming["name"],
        incoming["description"],
        is_global_candidate=bool(scope["scope_type"] == "global"),
    )
    if get_instance(skill, scope["scope_root"]):
        raise SystemExit(f"Skill already has an instance in scope {scope['scope_root']}")
    upsert_instance(
        skill,
        {
            "scope_id": scope["scope_id"],
            "scope_root": scope["scope_root"],
            "skill_dir": incoming["skill_dir"],
            "skill_md_path": incoming["skill_md_path"],
            "agents_path": normalize_path(scope["agents_path"]),
            "instance_status": "active",
            "origin_path": incoming["skill_dir"],
            "is_global": bool(scope["scope_type"] == "global"),
            "is_protected": incoming["name"] in registry.get("protected_skills", []),
        },
    )
    save_registry(registry)
    save_registry_markdown(registry)
    print(f"Registered {incoming['name']}")


def command_remove(args: argparse.Namespace) -> None:
    registry = load_registry()
    skill = get_skill_record(registry, args.skill_name)
    if not skill:
        raise SystemExit(f"Skill not found: {args.skill_name}")
    if args.skill_name in registry.get("protected_skills", []):
        raise SystemExit(f"Protected skill cannot be removed: {args.skill_name}")
    instances = active_instances(skill)
    if len(instances) > 1 and not args.scope_root:
        raise SystemExit("Multiple active instances exist. Provide --scope-root.")
    target_scope = normalize_path(args.scope_root or instances[0]["scope_root"])
    instance = get_instance(skill, target_scope)
    if not instance:
        raise SystemExit(f"No instance found for scope {target_scope}")
    print(f"Remove skill instance: {args.skill_name}")
    print(f"Scope: {instance['scope_root']}")
    print(f"Dir: {instance['skill_dir']}")
    if not args.apply:
        return
    shutil.rmtree(instance["skill_dir"])
    remove_instance(skill, target_scope)
    drop_empty = [entry for entry in registry["skills"] if entry.get("instances")]
    registry["skills"] = drop_empty
    save_registry(registry)
    save_registry_markdown(registry)
    print(f"Removed {args.skill_name} from {target_scope}")


def command_move(args: argparse.Namespace) -> None:
    registry = load_registry()
    skill = get_skill_record(registry, args.skill_name)
    if not skill:
        raise SystemExit(f"Skill not found: {args.skill_name}")
    if args.skill_name in registry.get("protected_skills", []):
        raise SystemExit(f"Protected skill cannot be moved: {args.skill_name}")
    source_scope = normalize_path(args.from_scope_root)
    target_scope = ensure_scope(registry, args.to_scope_root, scope_type=args.scope_type)
    instance = get_instance(skill, source_scope)
    if not instance:
        raise SystemExit(f"No instance found in source scope {source_scope}")
    if get_instance(skill, target_scope["scope_root"]):
        raise SystemExit(f"Skill already has an instance in target scope {target_scope['scope_root']}")
    source_dir = Path(instance["skill_dir"])
    destination = Path(target_scope["skills_dir"]) / source_dir.name
    print(f"Move skill instance: {args.skill_name}")
    print(f"From: {source_dir}")
    print(f"To: {destination}")
    if not args.apply:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SystemExit(f"Target already exists: {destination}")
    shutil.move(source_dir, destination)
    remove_instance(skill, source_scope)
    metadata = parse_skill_metadata(destination)
    upsert_instance(
        skill,
        {
            "scope_id": target_scope["scope_id"],
            "scope_root": target_scope["scope_root"],
            "skill_dir": metadata["skill_dir"],
            "skill_md_path": metadata["skill_md_path"],
            "agents_path": normalize_path(target_scope["agents_path"]),
            "instance_status": "active",
            "origin_path": metadata["skill_dir"],
            "is_global": bool(target_scope["scope_type"] == "global"),
            "is_protected": args.skill_name in registry.get("protected_skills", []),
        },
    )
    save_registry(registry)
    save_registry_markdown(registry)
    print(f"Moved {args.skill_name}")


def command_sync_agents(args: argparse.Namespace) -> None:
    registry = load_registry()
    scopes = registry.get("scopes", [])
    if args.scope_root:
        scopes = [scope for scope in scopes if normalize_path(scope["scope_root"]) == normalize_path(args.scope_root)]
    if not scopes:
        raise SystemExit("No matching scopes found.")
    for scope in scopes:
        sync_scope_agents(registry, scope, apply=args.apply)
        action = "Synced" if args.apply else "Would sync"
        print(f"{action}: {scope['agents_path']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the scoped Codex skill registry.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list")

    where_parser = subparsers.add_parser("where")
    where_parser.add_argument("skill_name")

    here_parser = subparsers.add_parser("here")
    here_parser.add_argument("--cwd", default=str(Path.cwd()))

    subparsers.add_parser("audit")

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("--unregistered-only", action="store_true")

    borrow_preview_parser = subparsers.add_parser("borrow-preview")
    borrow_preview_parser.add_argument("--query", required=True)
    borrow_preview_parser.add_argument("--cwd", default=str(Path.cwd()))

    borrow_resolve_parser = subparsers.add_parser("borrow-resolve")
    borrow_resolve_parser.add_argument("--skill-name", required=True)
    borrow_resolve_parser.add_argument("--scope-root")
    borrow_resolve_parser.add_argument("--cwd", default=str(Path.cwd()))

    bootstrap_parser = subparsers.add_parser("bootstrap")
    bootstrap_parser.add_argument("--apply", action="store_true")

    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--skill-dir", required=True)
    register_parser.add_argument("--scope-root", required=True)
    register_parser.add_argument("--scope-type", choices=["global", "local"])
    register_parser.add_argument("--apply", action="store_true")

    remove_parser = subparsers.add_parser("remove")
    remove_parser.add_argument("--skill-name", required=True)
    remove_parser.add_argument("--scope-root")
    remove_parser.add_argument("--apply", action="store_true")

    move_parser = subparsers.add_parser("move")
    move_parser.add_argument("--skill-name", required=True)
    move_parser.add_argument("--from-scope-root", required=True)
    move_parser.add_argument("--to-scope-root", required=True)
    move_parser.add_argument("--scope-type", choices=["global", "local"])
    move_parser.add_argument("--apply", action="store_true")

    sync_parser = subparsers.add_parser("sync-agents")
    sync_parser.add_argument("--scope-root")
    sync_parser.add_argument("--apply", action="store_true")

    subparsers.add_parser("render-md")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list":
        print_skill_list(load_registry())
    elif args.command == "where":
        print_where(load_registry(), args.skill_name)
    elif args.command == "here":
        print_here(load_registry(), args.cwd)
    elif args.command == "audit":
        registry = load_registry()
        registry["system_status"]["last_audit_at"] = now_iso()
        save_registry(registry)
        save_registry_markdown(registry)
        print_audit(registry)
    elif args.command == "discover":
        print_discover(load_registry(), args.unregistered_only)
    elif args.command == "borrow-preview":
        print_borrow_preview(load_registry(), args.query, args.cwd)
    elif args.command == "borrow-resolve":
        print_borrow_resolve(load_registry(), args.skill_name, args.cwd, args.scope_root)
    elif args.command == "bootstrap":
        command_bootstrap(args)
    elif args.command == "register":
        command_register(args)
    elif args.command == "remove":
        command_remove(args)
    elif args.command == "move":
        command_move(args)
    elif args.command == "sync-agents":
        command_sync_agents(args)
    elif args.command == "render-md":
        registry = load_registry()
        save_registry_markdown(registry)
        print(REGISTRY_MD)


if __name__ == "__main__":
    main()
