from __future__ import annotations

import argparse
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from _scope_lib import (
    PROTECTED_SKILL_NAMES,
    REGISTRY_MD,
    REGISTRY_YAML,
    ensure_scope,
    ensure_skill_record,
    load_registry,
    normalize_path,
    now_iso,
    parse_skill_metadata,
    save_registry,
    save_registry_markdown,
    sync_global_agents_guidance,
    sync_scope_agents,
    upsert_instance,
)


def load_registry_if_exists() -> dict[str, Any] | None:
    if REGISTRY_YAML.exists():
        return load_registry()
    return None


def init_required(force: bool) -> None:
    registry = load_registry_if_exists()
    if not registry:
        return
    complete = bool(registry.get("system_status", {}).get("bootstrap_complete"))
    if complete and not force:
        raise SystemExit(
            "Initialization is already complete. Use --force to run init commands against an existing registry."
        )


def discover_input_skills(source_dirs: list[str]) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    normalized_sources = [normalize_path(path) for path in source_dirs]
    for source_dir in normalized_sources:
        source_path = Path(source_dir)
        if not source_path.exists():
            raise SystemExit(f"Source skill directory does not exist: {source_dir}")
        if not source_path.is_dir():
            raise SystemExit(f"Source skill directory is not a directory: {source_dir}")
        for child in sorted(source_path.iterdir(), key=lambda item: item.name):
            if child.is_dir() and (child / "SKILL.md").exists():
                meta = parse_skill_metadata(child)
                meta["source_skill_root"] = source_dir
                discovered.append(meta)
    return discovered


def suggest_mode(skill: dict[str, Any], duplicate_counts: Counter[str]) -> tuple[str, str]:
    name = skill["name"]
    skill_dir = Path(skill["skill_dir"])
    source_root = Path(skill["source_skill_root"])
    if duplicate_counts[name] > 1:
        return "multi-scope copy", "same skill name appears in multiple provided source directories"
    if source_root.name == "skills" or skill_dir.parent.name == "skills":
        return "local", "source already looks like a scope-local skills directory"
    return "global", "standalone source directory; global is the safest default"


def print_init_status(force: bool) -> None:
    registry = load_registry_if_exists()
    if not registry:
        print("Initialization status: not initialized")
        print(f"Registry path: {REGISTRY_YAML}")
        return
    complete = bool(registry.get("system_status", {}).get("bootstrap_complete"))
    print(f"Initialization status: {'initialized' if complete else 'not initialized'}")
    print(f"Registry path: {REGISTRY_YAML}")
    print(f"Bootstrap complete: {complete}")
    if complete and force:
        print("Force mode: init commands may run against the existing registry.")


def print_init_discover(source_dirs: list[str]) -> None:
    discovered = discover_input_skills(source_dirs)
    if not discovered:
        print("No skills discovered in the provided source directories.")
        return
    duplicate_counts = Counter(item["name"] for item in discovered)
    print("Discovered skills:")
    for skill in discovered:
        suggestion, reason = suggest_mode(skill, duplicate_counts)
        print(f"- {skill['name']}")
        print(f"  Source root: {skill['source_skill_root']}")
        print(f"  Skill dir: {skill['skill_dir']}")
        print(f"  Suggested mode: {suggestion}")
        print(f"  Why: {reason}")


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise SystemExit(f"YAML file does not exist: {file_path}")
    with file_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def validate_targets(
    mode: str,
    targets: list[dict[str, Any]],
    global_root: str,
) -> list[dict[str, Any]]:
    if not targets:
        raise SystemExit("Each placement must contain at least one target.")
    normalized_targets: list[dict[str, Any]] = []
    seen = set()
    for target in targets:
        scope_root = normalize_path(target["scope_root"])
        scope_type = target["scope_type"]
        if scope_type not in {"global", "local"}:
            raise SystemExit(f"Invalid scope_type for target {scope_root}: {scope_type}")
        if scope_type == "global" and scope_root != global_root:
            raise SystemExit(f"Global target must use the declared global root: {scope_root}")
        key = (scope_root, scope_type)
        if key in seen:
            raise SystemExit(f"Duplicate target in placement: {scope_root}")
        seen.add(key)
        normalized_targets.append({"scope_root": scope_root, "scope_type": scope_type})
    if mode in {"global", "local"} and len(normalized_targets) != 1:
        raise SystemExit(f"Mode {mode} requires exactly one target.")
    if mode == "multi-scope copy" and len(normalized_targets) < 2:
        raise SystemExit("Mode multi-scope copy requires at least two targets.")
    return normalized_targets


def build_init_plan(decisions: dict[str, Any]) -> dict[str, Any]:
    global_root = normalize_path(decisions["global_root"])
    source_skill_dirs = [normalize_path(path) for path in decisions.get("source_skill_dirs", [])]
    if not source_skill_dirs:
        raise SystemExit("Decision file must contain source_skill_dirs.")

    discovered = discover_input_skills(source_skill_dirs)
    discovered_by_dir = {item["skill_dir"]: item for item in discovered}
    if not discovered_by_dir:
        raise SystemExit("No skills discovered from the provided source_skill_dirs.")

    placements = decisions.get("placements", [])
    if not placements:
        raise SystemExit("Decision file must contain placements.")

    plan: dict[str, Any] = {
        "version": 1,
        "created_at": now_iso(),
        "global_root": global_root,
        "source_skill_dirs": source_skill_dirs,
        "registry_path": normalize_path(REGISTRY_YAML),
        "registry_markdown_path": normalize_path(REGISTRY_MD),
        "scopes": [],
        "placements": [],
        "actions": [],
    }

    scopes_by_root: dict[str, dict[str, Any]] = {}

    def ensure_plan_scope(scope_root: str, scope_type: str) -> dict[str, Any]:
        if scope_root in scopes_by_root:
            return scopes_by_root[scope_root]
        scope = {
            "scope_root": scope_root,
            "scope_type": scope_type,
            "skills_dir": normalize_path(Path(scope_root) / "skills"),
            "agents_path": normalize_path(Path(scope_root) / "AGENTS.md"),
            "create_skills_dir": not (Path(scope_root) / "skills").exists(),
            "create_agents": not (Path(scope_root) / "AGENTS.md").exists(),
        }
        scopes_by_root[scope_root] = scope
        plan["scopes"].append(scope)
        plan["actions"].append(
            {
                "type": "ensure-scope-structure",
                "scope_root": scope_root,
                "scope_type": scope_type,
                "skills_dir": scope["skills_dir"],
                "agents_path": scope["agents_path"],
                "create_skills_dir": scope["create_skills_dir"],
                "create_agents": scope["create_agents"],
            }
        )
        return scope

    for placement in placements:
        source_dir = normalize_path(placement["source_dir"])
        if source_dir not in discovered_by_dir:
            raise SystemExit(f"Placement source_dir was not discovered: {source_dir}")
        source_skill = discovered_by_dir[source_dir]
        mode = placement["mode"]
        if mode not in {"global", "local", "multi-scope copy"}:
            raise SystemExit(f"Unsupported placement mode: {mode}")
        targets = validate_targets(mode, placement.get("targets", []), global_root)
        basename = Path(source_dir).name

        plan_entry = {
            "skill_name": source_skill["name"],
            "description": source_skill["description"],
            "source_dir": source_dir,
            "mode": mode,
            "targets": [],
        }

        primary_target = targets[0]
        primary_scope = ensure_plan_scope(primary_target["scope_root"], primary_target["scope_type"])
        primary_destination = normalize_path(Path(primary_scope["skills_dir"]) / basename)
        if primary_destination == source_dir:
            primary_action = "register-skill"
        else:
            primary_action = "move-skill"

        plan_entry["targets"].append(
            {
                "scope_root": primary_target["scope_root"],
                "scope_type": primary_target["scope_type"],
                "destination_dir": primary_destination,
                "action": primary_action,
            }
        )
        plan["actions"].append(
            {
                "type": primary_action,
                "skill_name": source_skill["name"],
                "scope_root": primary_target["scope_root"],
                "scope_type": primary_target["scope_type"],
                "source_dir": source_dir,
                "destination_dir": primary_destination,
            }
        )

        copy_source = primary_destination
        for target in targets[1:]:
            target_scope = ensure_plan_scope(target["scope_root"], target["scope_type"])
            destination_dir = normalize_path(Path(target_scope["skills_dir"]) / basename)
            if destination_dir == primary_destination:
                raise SystemExit(f"Duplicate destination for {source_skill['name']}: {destination_dir}")
            plan_entry["targets"].append(
                {
                    "scope_root": target["scope_root"],
                    "scope_type": target["scope_type"],
                    "destination_dir": destination_dir,
                    "action": "copy-skill",
                }
            )
            plan["actions"].append(
                {
                    "type": "copy-skill",
                    "skill_name": source_skill["name"],
                    "scope_root": target["scope_root"],
                    "scope_type": target["scope_type"],
                    "source_dir": copy_source,
                    "destination_dir": destination_dir,
                }
            )

        plan["placements"].append(plan_entry)

    for scope in plan["scopes"]:
        plan["actions"].append(
            {
                "type": "sync-agents",
                "scope_root": scope["scope_root"],
                "agents_path": scope["agents_path"],
            }
        )
    plan["actions"].append({"type": "write-registry", "path": normalize_path(REGISTRY_YAML)})
    plan["actions"].append({"type": "render-registry-markdown", "path": normalize_path(REGISTRY_MD)})
    return plan


def print_plan_summary(plan: dict[str, Any]) -> None:
    print("Initialization preview:")
    print(f"- Global root: {plan['global_root']}")
    print(f"- Source skill dirs: {', '.join(plan['source_skill_dirs'])}")
    print(f"- Scopes to create or update: {len(plan['scopes'])}")
    for scope in plan["scopes"]:
        print(f"  - {scope['scope_root']} [{scope['scope_type']}]")
        print(f"    skills/: {'create' if scope['create_skills_dir'] else 'reuse'}")
        print(f"    AGENTS.md: {'create' if scope['create_agents'] else 'update managed block'}")
    print(f"- Skill placements: {len(plan['placements'])}")
    for placement in plan["placements"]:
        print(f"  - {placement['skill_name']} [{placement['mode']}]")
        print(f"    source: {placement['source_dir']}")
        for target in placement["targets"]:
            print(f"    {target['action']}: {target['destination_dir']} ({target['scope_root']})")
    print("- Registry actions:")
    print(f"  - write {plan['registry_path']}")
    print(f"  - render {plan['registry_markdown_path']}")
    for scope in plan["scopes"]:
        if scope["scope_type"] == "global":
            print(f"  - update global AGENTS guidance in {scope['agents_path']}")


def create_default_plan_path() -> Path:
    filename = f"init-plan-{now_iso().replace(':', '-').replace('+', '_')}.yaml"
    return REGISTRY_YAML.parent / filename


def write_plan_file(plan: dict[str, Any], path: str | Path) -> Path:
    plan_path = Path(path)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    with plan_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(plan, handle, sort_keys=False, allow_unicode=True, width=120)
    return plan_path


def build_registry_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    registry = {
        "system_status": {
            "registry_version": 1,
            "bootstrap_complete": True,
            "initialized_at": now_iso(),
            "last_audit_at": now_iso(),
            "notes": "Initialized from an explicit bootstrap plan.",
        },
        "protected_skills": sorted(PROTECTED_SKILL_NAMES),
        "scopes": [],
        "skills": [],
    }
    scope_map: dict[str, dict[str, Any]] = {}
    for scope in plan["scopes"]:
        scope_record = ensure_scope(
            registry,
            scope["scope_root"],
            scope_type=scope["scope_type"],
            agents_path=scope["agents_path"],
            skills_dir=scope["skills_dir"],
        )
        scope_map[scope["scope_root"]] = scope_record

    for placement in plan["placements"]:
        for target in placement["targets"]:
            metadata = parse_skill_metadata(target["destination_dir"])
            scope = scope_map[target["scope_root"]]
            skill = ensure_skill_record(
                registry,
                metadata["name"],
                metadata["description"],
                is_global_candidate=bool(scope["scope_type"] == "global"),
            )
            upsert_instance(
                skill,
                {
                    "scope_id": scope["scope_id"],
                    "scope_root": scope["scope_root"],
                    "skill_dir": metadata["skill_dir"],
                    "skill_md_path": metadata["skill_md_path"],
                    "agents_path": normalize_path(scope["agents_path"]),
                    "instance_status": "active",
                    "origin_path": placement["source_dir"],
                    "is_global": bool(scope["scope_type"] == "global"),
                    "is_protected": metadata["name"] in registry["protected_skills"],
                },
            )
    return registry


def command_init_preview(args: argparse.Namespace) -> None:
    init_required(args.force)
    decisions = load_yaml_file(args.decision_file)
    plan = build_init_plan(decisions)
    print_plan_summary(plan)
    plan_path = write_plan_file(plan, args.plan_out or create_default_plan_path())
    print(f"Plan file: {plan_path}")


def command_init_apply(args: argparse.Namespace) -> None:
    init_required(args.force)
    plan = load_yaml_file(args.plan_file)

    for scope in plan["scopes"]:
        Path(scope["skills_dir"]).mkdir(parents=True, exist_ok=True)
        agents_path = Path(scope["agents_path"])
        if not agents_path.exists():
            agents_path.parent.mkdir(parents=True, exist_ok=True)
            agents_path.write_text("", encoding="utf-8")
        if scope["scope_type"] == "global":
            sync_global_agents_guidance(agents_path, apply=True)

    for placement in plan["placements"]:
        primary_target = placement["targets"][0]
        if primary_target["action"] == "move-skill":
            source = Path(placement["source_dir"])
            destination = Path(primary_target["destination_dir"])
            if destination.exists():
                raise SystemExit(f"Target already exists: {destination}")
            shutil.move(str(source), str(destination))
        elif primary_target["action"] == "register-skill":
            if not Path(primary_target["destination_dir"]).exists():
                raise SystemExit(f"Register-in-place destination does not exist: {primary_target['destination_dir']}")

        for target in placement["targets"][1:]:
            source = Path(placement["targets"][0]["destination_dir"])
            destination = Path(target["destination_dir"])
            if destination.exists():
                raise SystemExit(f"Target already exists: {destination}")
            shutil.copytree(source, destination)

    registry = build_registry_from_plan(plan)
    save_registry(registry)
    save_registry_markdown(registry)
    for scope in registry["scopes"]:
        sync_scope_agents(registry, scope, apply=True)
    print(f"Wrote {REGISTRY_YAML}")
    print(f"Wrote {REGISTRY_MD}")
    for scope in registry["scopes"]:
        if scope["scope_type"] == "global":
            print(f"Updated global guidance: {scope['agents_path']}")
        print(f"Synced: {scope['agents_path']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize a scoped agent skill registry.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("init-status")
    status_parser.add_argument("--force", action="store_true")

    discover_parser = subparsers.add_parser("init-discover")
    discover_parser.add_argument("--skill-dir", action="append", required=True)

    preview_parser = subparsers.add_parser("init-preview")
    preview_parser.add_argument("--decision-file", required=True)
    preview_parser.add_argument("--plan-out")
    preview_parser.add_argument("--force", action="store_true")

    apply_parser = subparsers.add_parser("init-apply")
    apply_parser.add_argument("--plan-file", required=True)
    apply_parser.add_argument("--force", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-status":
        print_init_status(args.force)
    elif args.command == "init-discover":
        print_init_discover(args.skill_dir)
    elif args.command == "init-preview":
        command_init_preview(args)
    elif args.command == "init-apply":
        command_init_apply(args)


if __name__ == "__main__":
    main()
