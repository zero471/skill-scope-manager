from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

import yaml


SKILL_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_YAML = SKILL_ROOT / "registry" / "skill-registry.yaml"
REGISTRY_MD = SKILL_ROOT / "registry" / "skill-registry.md"
MANAGED_BEGIN = "<!-- skill-scope-manager:begin -->"
MANAGED_END = "<!-- skill-scope-manager:end -->"
PROTECTED_SKILL_NAMES = [
    "skill-creator",
    "skill-installer",
    "skill-scope-manager",
]


def now_iso() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def default_agent_home() -> str:
    return normalize_path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


def protected_skill_dirs_for_scope(scope: dict[str, Any]) -> list[Path]:
    if scope.get("scope_type") != "global":
        return []
    skills_dir = Path(scope["skills_dir"])
    system_dir = skills_dir / ".system"
    return [system_dir / name for name in PROTECTED_SKILL_NAMES if name != "skill-scope-manager"]


def load_registry(path: Path = REGISTRY_YAML) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    data.setdefault("system_status", {})
    data.setdefault("protected_skills", [])
    data.setdefault("scopes", [])
    data.setdefault("skills", [])
    return data


def save_registry(data: dict[str, Any], path: Path = REGISTRY_YAML) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            data,
            handle,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )


def parse_skill_metadata(skill_dir: str | Path) -> dict[str, str]:
    skill_dir = Path(skill_dir)
    skill_md = skill_dir / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise ValueError(f"Missing YAML frontmatter: {skill_md}")
    metadata = yaml.safe_load(match.group(1)) or {}
    name = metadata.get("name")
    description = metadata.get("description")
    if not name or not description:
        raise ValueError(f"Missing name/description in {skill_md}")
    return {
        "name": str(name),
        "description": str(description).strip(),
        "skill_md_path": normalize_path(skill_md),
        "skill_dir": normalize_path(skill_dir),
    }


def discover_scope_skills(scope: dict[str, Any]) -> list[dict[str, Any]]:
    skills_dir = Path(scope["skills_dir"])
    discovered: list[dict[str, Any]] = []
    if skills_dir.exists():
        for child in sorted(skills_dir.iterdir(), key=lambda item: item.name):
            if child.is_dir() and (child / "SKILL.md").exists():
                meta = parse_skill_metadata(child)
                meta["scope_id"] = scope["scope_id"]
                meta["scope_root"] = normalize_path(scope["scope_root"])
                meta["agents_path"] = normalize_path(scope["agents_path"])
                meta["is_global"] = bool(scope["scope_type"] == "global")
                meta["is_protected"] = False
                discovered.append(meta)
    if scope["scope_type"] == "global":
        for protected_dir in protected_skill_dirs_for_scope(scope):
            if protected_dir.exists() and (protected_dir / "SKILL.md").exists():
                meta = parse_skill_metadata(protected_dir)
                meta["scope_id"] = scope["scope_id"]
                meta["scope_root"] = normalize_path(scope["scope_root"])
                meta["agents_path"] = normalize_path(scope["agents_path"])
                meta["is_global"] = True
                meta["is_protected"] = True
                discovered.append(meta)
    return discovered


def discover_all_registry_skills(registry: dict[str, Any]) -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for scope in registry.get("scopes", []):
        discovered.extend(discover_scope_skills(scope))
    return discovered


def get_scope(registry: dict[str, Any], scope_root: str) -> dict[str, Any] | None:
    scope_root = normalize_path(scope_root)
    for scope in registry.get("scopes", []):
        if normalize_path(scope["scope_root"]) == scope_root:
            return scope
    return None


def ensure_scope(
    registry: dict[str, Any],
    scope_root: str,
    scope_type: str | None = None,
    agents_path: str | None = None,
    skills_dir: str | None = None,
) -> dict[str, Any]:
    existing = get_scope(registry, scope_root)
    if existing:
        return existing
    root = normalize_path(scope_root)
    inferred_type = scope_type or ("global" if root == default_agent_home() else "local")
    scope_id = slugify(root)
    current_ids = {scope["scope_id"] for scope in registry.get("scopes", [])}
    base_id = scope_id
    suffix = 2
    while scope_id in current_ids:
        scope_id = f"{base_id}-{suffix}"
        suffix += 1
    scope = {
        "scope_id": scope_id,
        "scope_root": root,
        "scope_type": inferred_type,
        "agents_path": normalize_path(agents_path or (Path(root) / "AGENTS.md")),
        "skills_dir": normalize_path(skills_dir or (Path(root) / "skills")),
        "initialized": True,
        "notes": "",
    }
    registry.setdefault("scopes", []).append(scope)
    registry["scopes"] = sorted(registry["scopes"], key=lambda item: item["scope_root"])
    return scope


def get_skill_record(registry: dict[str, Any], skill_name: str) -> dict[str, Any] | None:
    for skill in registry.get("skills", []):
        if skill["skill_name"] == skill_name:
            return skill
    return None


def ensure_skill_record(
    registry: dict[str, Any],
    skill_name: str,
    description: str,
    *,
    is_global_candidate: bool,
) -> dict[str, Any]:
    existing = get_skill_record(registry, skill_name)
    if existing:
        existing["description"] = description
        existing["is_global_candidate"] = existing.get("is_global_candidate", False) or is_global_candidate
        return existing
    skill = {
        "skill_name": skill_name,
        "description": description,
        "status": "active",
        "managed_by_registry": True,
        "is_global_candidate": is_global_candidate,
        "last_verified_at": now_iso(),
        "instances": [],
    }
    registry.setdefault("skills", []).append(skill)
    registry["skills"] = sorted(registry["skills"], key=lambda item: item["skill_name"])
    return skill


def get_instance(skill_record: dict[str, Any], scope_root: str) -> dict[str, Any] | None:
    scope_root = normalize_path(scope_root)
    for instance in skill_record.get("instances", []):
        if normalize_path(instance["scope_root"]) == scope_root:
            return instance
    return None


def upsert_instance(skill_record: dict[str, Any], instance: dict[str, Any]) -> None:
    existing = get_instance(skill_record, instance["scope_root"])
    if existing:
        existing.update(instance)
    else:
        skill_record.setdefault("instances", []).append(instance)
        skill_record["instances"] = sorted(skill_record["instances"], key=lambda item: item["scope_root"])
    skill_record["last_verified_at"] = now_iso()
    skill_record["status"] = "active" if active_instances(skill_record) else "archived"


def active_instances(skill_record: dict[str, Any]) -> list[dict[str, Any]]:
    return [instance for instance in skill_record.get("instances", []) if instance.get("instance_status") == "active"]


def remove_instance(skill_record: dict[str, Any], scope_root: str) -> dict[str, Any] | None:
    scope_root = normalize_path(scope_root)
    removed = None
    kept = []
    for instance in skill_record.get("instances", []):
        if normalize_path(instance["scope_root"]) == scope_root and removed is None:
            removed = instance
            continue
        kept.append(instance)
    skill_record["instances"] = kept
    skill_record["last_verified_at"] = now_iso()
    skill_record["status"] = "active" if active_instances(skill_record) else "archived"
    return removed


def drop_archived_skills(registry: dict[str, Any]) -> None:
    registry["skills"] = [
        skill for skill in registry.get("skills", []) if skill.get("instances")
    ]


def cwd_active_scope_ids(registry: dict[str, Any], cwd: str | Path) -> set[str]:
    cwd_path = normalize_path(cwd)
    active = set()
    for scope in registry.get("scopes", []):
        scope_root = normalize_path(scope["scope_root"])
        if scope["scope_type"] == "global":
            active.add(scope["scope_id"])
            continue
        if cwd_path == scope_root or cwd_path.startswith(scope_root + os.sep):
            active.add(scope["scope_id"])
    return active


def skills_available_here(registry: dict[str, Any], cwd: str | Path) -> list[dict[str, Any]]:
    active_scope_ids = cwd_active_scope_ids(registry, cwd)
    matches = []
    for skill in sorted(registry.get("skills", []), key=lambda item: item["skill_name"]):
        scoped_instances = [
            instance
            for instance in active_instances(skill)
            if instance["scope_id"] in active_scope_ids
        ]
        if scoped_instances:
            matches.append({"skill": skill, "instances": scoped_instances})
    return matches


def tokenize_query(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-zA-Z0-9]+", text.lower()) if token]


def borrow_candidates(registry: dict[str, Any], query: str, cwd: str | Path) -> list[dict[str, Any]]:
    cwd_path = normalize_path(cwd)
    active_scope_ids = cwd_active_scope_ids(registry, cwd_path)
    query_text = query.strip()
    query_lower = query_text.lower()
    tokens = tokenize_query(query_text)
    candidates: list[dict[str, Any]] = []

    for skill in sorted(registry.get("skills", []), key=lambda item: item["skill_name"]):
        if skill.get("status") != "active":
            continue
        available_here = any(instance["scope_id"] in active_scope_ids for instance in active_instances(skill))
        if available_here:
            continue

        name = skill["skill_name"]
        name_lower = name.lower()
        description = skill.get("description", "")
        description_lower = description.lower()
        score = 0
        reasons: list[str] = []

        if query_text and query_text == name:
            score += 1000
            reasons.append("exact name match")
        elif query_lower and query_lower == name_lower:
            score += 900
            reasons.append("case-insensitive name match")

        if query_lower and query_lower in name_lower and query_lower != name_lower:
            score += 250
            reasons.append("name contains query")
        if query_lower and query_lower in description_lower:
            score += 150
            reasons.append("description contains query")

        token_hits = 0
        for token in tokens:
            if token in name_lower:
                score += 80
                token_hits += 1
            elif token in description_lower:
                score += 35
                token_hits += 1
        if token_hits:
            reasons.append(f"{token_hits} keyword hits")

        if score <= 0:
            continue

        scoped_instances = []
        for instance in active_instances(skill):
            if instance["scope_id"] in active_scope_ids:
                continue
            scoped_instances.append(instance)
        if not scoped_instances:
            continue

        candidates.append(
            {
                "skill": skill,
                "instances": scoped_instances,
                "score": score,
                "reasons": reasons or ["fuzzy description match"],
                "cwd": cwd_path,
            }
        )

    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["skill"]["skill_name"],
            item["instances"][0]["scope_root"],
        )
    )
    return candidates


def resolve_borrow_instance(
    registry: dict[str, Any],
    skill_name: str,
    cwd: str | Path,
    scope_root: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    cwd_path = normalize_path(cwd)
    active_scope_ids = cwd_active_scope_ids(registry, cwd_path)
    skill = get_skill_record(registry, skill_name)
    if not skill:
        raise ValueError(f"Skill not found in registry: {skill_name}")
    if skill.get("status") != "active":
        raise ValueError(f"Skill is not active: {skill_name}")

    available_here = [instance for instance in active_instances(skill) if instance["scope_id"] in active_scope_ids]
    if available_here:
        raise ValueError(f"Skill is already available in this scope: {skill_name}")

    candidates = [instance for instance in active_instances(skill) if instance["scope_id"] not in active_scope_ids]
    if scope_root:
        target_scope_root = normalize_path(scope_root)
        candidates = [instance for instance in candidates if normalize_path(instance["scope_root"]) == target_scope_root]
        if not candidates:
            raise ValueError(f"No out-of-scope instance found for {skill_name} in {target_scope_root}")

    if len(candidates) > 1:
        roots = ", ".join(instance["scope_root"] for instance in candidates)
        raise ValueError(f"Multiple out-of-scope instances exist for {skill_name}. Choose one of: {roots}")

    if not candidates:
        raise ValueError(f"No out-of-scope active instance found for {skill_name}")

    return skill, candidates[0], cwd_path


def build_scope_block(registry: dict[str, Any], scope: dict[str, Any]) -> str:
    lines = [MANAGED_BEGIN, "## Available skills", ""]
    items = []
    for skill in sorted(registry.get("skills", []), key=lambda item: item["skill_name"]):
        for instance in active_instances(skill):
            if instance["scope_id"] != scope["scope_id"]:
                continue
            items.append(
                f"- {skill['skill_name']}: {skill['description']} "
                f"(file: {instance['skill_md_path']})"
            )
    if items:
        lines.extend(items)
    else:
        lines.append("_No managed skills in this scope._")
    lines.extend(["", MANAGED_END])
    return "\n".join(lines)


def sync_scope_agents(registry: dict[str, Any], scope: dict[str, Any], apply: bool) -> str:
    agents_path = Path(scope["agents_path"])
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    block = build_scope_block(registry, scope)
    if MANAGED_BEGIN in existing and MANAGED_END in existing:
        updated = re.sub(
            rf"{re.escape(MANAGED_BEGIN)}.*?{re.escape(MANAGED_END)}",
            block,
            existing,
            flags=re.S,
        )
    else:
        separator = "\n\n" if existing and not existing.endswith("\n") else "\n"
        updated = existing + separator + block if existing else block + "\n"
    if apply:
        agents_path.parent.mkdir(parents=True, exist_ok=True)
        agents_path.write_text(updated, encoding="utf-8")
    return updated


def render_registry_markdown(registry: dict[str, Any]) -> str:
    lines = [
        "# Skill Scope Registry",
        "",
        "## System Status",
        "",
        f"- Bootstrap complete: `{registry['system_status'].get('bootstrap_complete', False)}`",
        f"- Initialized at: `{registry['system_status'].get('initialized_at', '')}`",
        f"- Last audit at: `{registry['system_status'].get('last_audit_at', '')}`",
        f"- Registry version: `{registry['system_status'].get('registry_version', 1)}`",
        "",
        "## Scopes",
        "",
        "| Scope ID | Root | Type | Skills Dir | AGENTS | Initialized |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for scope in sorted(registry.get("scopes", []), key=lambda item: item["scope_root"]):
        lines.append(
            f"| `{scope['scope_id']}` | `{scope['scope_root']}` | `{scope['scope_type']}` | "
            f"`{scope['skills_dir']}` | `{scope['agents_path']}` | `{scope['initialized']}` |"
        )
    lines.extend(["", "## Skills", "", "| Skill | Status | Instances | Scopes | Paths |", "| --- | --- | --- | --- | --- |"])
    for skill in sorted(registry.get("skills", []), key=lambda item: item["skill_name"]):
        scopes = "<br>".join(f"`{instance['scope_root']}`" for instance in skill.get("instances", []))
        paths = "<br>".join(f"`{instance['skill_dir']}`" for instance in skill.get("instances", []))
        lines.append(
            f"| `{skill['skill_name']}` | `{skill['status']}` | `{len(skill.get('instances', []))}` | "
            f"{scopes or '-'} | {paths or '-'} |"
        )
    return "\n".join(lines) + "\n"


def save_registry_markdown(registry: dict[str, Any], path: Path = REGISTRY_MD) -> None:
    path.write_text(render_registry_markdown(registry), encoding="utf-8")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def collect_audit_issues(registry: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    registered_paths = set()
    for scope in registry.get("scopes", []):
        if not Path(scope["agents_path"]).exists():
            issues.append({"type": "missing_agents", "path": normalize_path(scope["agents_path"])})
        if not Path(scope["skills_dir"]).exists():
            issues.append({"type": "missing_skills_dir", "path": normalize_path(scope["skills_dir"])})
    for skill in registry.get("skills", []):
        hashes = set()
        for instance in skill.get("instances", []):
            skill_md_path = normalize_path(instance["skill_md_path"])
            registered_paths.add(skill_md_path)
            if not Path(skill_md_path).exists():
                issues.append({"type": "missing_instance", "skill": skill["skill_name"], "path": skill_md_path})
                continue
            hashes.add(sha256_file(skill_md_path))
            agents_path = Path(instance["agents_path"])
            if agents_path.exists():
                text = agents_path.read_text(encoding="utf-8")
                if skill_md_path not in text:
                    issues.append(
                        {
                            "type": "agents_missing_reference",
                            "skill": skill["skill_name"],
                            "path": normalize_path(agents_path),
                        }
                    )
        if len(hashes) > 1:
            issues.append({"type": "content_divergence", "skill": skill["skill_name"]})
    for discovered in discover_all_registry_skills(registry):
        if discovered["skill_md_path"] not in registered_paths:
            issues.append(
                {
                    "type": "unregistered_instance",
                    "skill": discovered["name"],
                    "path": discovered["skill_md_path"],
                }
            )
    return issues


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip("/").lower())
    return cleaned.strip("-") or "scope"
