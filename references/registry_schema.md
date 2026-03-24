# Registry Schema

`registry/skill-registry.yaml` is the machine-readable authority for skill scoping.

## Top-level keys

- `system_status`
- `protected_skills`
- `scopes`
- `skills`

## `system_status`

- `registry_version`
- `bootstrap_complete`
- `initialized_at`
- `last_audit_at`
- `notes`

## `protected_skills`

Skill names that should not be removed or moved by normal management flows.

## `scopes`

Each scope entry defines a root directory where a scoped `AGENTS.md` and `skills/` directory live.

Required fields:

- `scope_id`
- `scope_root`
- `scope_type`
- `agents_path`
- `skills_dir`
- `initialized`

## `skills`

Each skill record is keyed by `skill_name` and contains an `instances` list.

Required fields:

- `skill_name`
- `description`
- `status`
- `managed_by_registry`
- `is_global_candidate`
- `last_verified_at`
- `instances`

`status` is the global availability switch for the skill record.

Allowed values:

- `active`
- `disabled`

## `instances`

Each instance represents one scoped copy of the skill.

Required fields:

- `scope_id`
- `scope_root`
- `skill_dir`
- `skill_md_path`
- `agents_path`
- `instance_status`
- `origin_path`
- `is_global`
- `is_protected`

`instance_status` is installation metadata for the scoped copy. In the current lightweight model, global enable/disable is controlled by the parent skill record's `status`, while `AGENTS.md` only reflects active skills after registry sync.

## Same-name multi-scope rule

If the same `skill_name` appears in multiple scopes, store it as one skill record with multiple `instances`. This means the skill is active in all of those scopes.

## Disable model

- Keep enable/disable state in `skills[].status`
- Do not store disabled markers in `AGENTS.md`
- Treat `AGENTS.md` as a generated projection of active skills only
- Use `disable` / `enable` for recoverable switching
- Use `remove` only for deleting the scoped copy itself

## Temporary cross-scope invocation

Cross-scope borrowing is not part of the registry state.

- Do not persist approvals in the registry
- Do not add temporary borrow metadata to `skills` or `instances`
- Resolve borrow targets from existing registry entries only
- Treat borrowing as a single-invocation workflow driven by user confirmation
- If a skill already belongs to the current path's active scopes, it is not a borrow
