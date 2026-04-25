---
name: skill-scope-manager
description: Manage scoped skills across global and local `skills/` directories. Use when the user wants to initialize skill scoping, discover unregistered skills, add/remove/move a skill between scopes, locate the absolute path of a skill for editing, audit drift between disk and AGENTS.md, query which skills are installed and active in the current path, or temporarily invoke an out-of-scope skill by name or by capability description with explicit user approval.
metadata:
  registry_yaml: registry/skill-registry.yaml
  registry_markdown: registry/skill-registry.md
  default_apply_mode: preview-first
---

# Skill Scope Manager

Use this skill to manage the scoped skill registry for the current machine.

## Source of truth

Always read `registry/skill-registry.yaml` first. Treat it as the authority for:

- which skills are managed
- which scopes exist
- which absolute paths each skill instance uses
- whether a skill is globally enabled or disabled
- whether bootstrap initialization is complete

Use `registry/skill-registry.md` as the human-readable table view only.

If `registry/skill-registry.yaml` does not exist, or `bootstrap_complete` is false, also read `references/bootstrap_init.md` before doing any initialization work. Do not load that file during normal daily management.

## Defaults

- Preview first, then apply
- Same skill name may exist in multiple scopes
- A skill with multiple scoped copies is considered active in each of those scopes
- For skill content edits, first resolve the absolute path from the registry, then edit that path
- This skill is not a background watcher; new skill folders become managed only after `discover`/`audit`/`register`
- **Important**: Whenever the skill registry or related skill components are modified, you MUST commit the changes to the git repository located in this skill's directory (`/Users/tmyz/.config/opencode/skills/skill-scope-manager`).

## Commands

For daily management, run the helper script from this skill directory:

```bash
python scripts/skill_scope_registry.py list
python scripts/skill_scope_registry.py where <skill-name>
python scripts/skill_scope_registry.py here --cwd "$PWD"
python scripts/skill_scope_registry.py audit
python scripts/skill_scope_registry.py discover --unregistered-only
python scripts/skill_scope_registry.py borrow-preview --query <text> --cwd "$PWD"
python scripts/skill_scope_registry.py borrow-resolve --skill-name <name> --cwd "$PWD"
python scripts/skill_scope_registry.py register --skill-dir <path> --scope-root <scope>
python scripts/skill_scope_registry.py remove --skill-name <name> --scope-root <scope>
python scripts/skill_scope_registry.py disable --skill-name <name>
python scripts/skill_scope_registry.py enable --skill-name <name>
python scripts/skill_scope_registry.py move --skill-name <name> --from-scope-root <src> --to-scope-root <dst>
python scripts/skill_scope_registry.py sync-agents
```

Add `--apply` to any mutating command after showing the preview to the user.

For first-run initialization only, use the dedicated initialization script:

```bash
python scripts/skill_scope_init.py init-status
python scripts/skill_scope_init.py init-discover --skill-dir <path> [--skill-dir <path> ...]
python scripts/skill_scope_init.py init-preview --decision-file <file> [--plan-out <file>]
python scripts/skill_scope_init.py init-apply --plan-file <file>
```

## Workflow

### Initialization

Initialization is a separate mode. If the registry is missing or `bootstrap_complete` is false:

1. Read `references/bootstrap_init.md`
2. Determine the central fixed path where `skill-scope-manager` should be permanently stored (e.g. `~/Vscode/SKILL/skill-scope-manager`)
3. Determine all target agent global directories (e.g. `~/.codex/skills`, `~/.config/opencode/skills`)
4. Create symlinks from each agent directory pointing back to the central path
5. Use `scripts/skill_scope_init.py` to bootstrap the registry, creating independent global scopes (e.g., `codex_global`, `opencode_global`) to isolate each agent's global skills while sharing the same central registry file.
6. Do not improvise the bootstrap flow from the daily management commands

During initialization, make sure the global `AGENTS.md` also gets a stable guidance block that tells the agent:

- global skill disable requires both `skill-scope-manager` and Codex system settings
- global skill re-enable requires both `skill-scope-manager` and Codex system settings
- newly installed and newly created skills are not scope-managed until `register` is applied

### Add

Use `discover --unregistered-only` to find new skills. Then:

1. Ask the user which scope root should own the new skill
2. Run `register` without `--apply`
3. Show the preview
4. Re-run with `--apply`

If a user has just created a skill, explicitly remind them that the new folder is not scope-managed until registration is applied.

### Remove

Use `where <skill-name>` first.

- If a skill has one instance, remove it directly
- If a skill has multiple instances, ask which scoped copy to remove

Always preview first.

### Disable or enable

Use `disable` and `enable` for a lightweight, recoverable switch.

- `disable` keeps the skill directory and registry entry intact
- `enable` restores the skill from the same registry entry
- Disabled state belongs in the registry, not in `AGENTS.md`
- `AGENTS.md` should only list currently active skills

When the user wants a skill fully hidden, remind them that there are two separate layers:

1. Disable it in `skill-scope-manager` so local scope resolution and `AGENTS.md` stop exposing it
2. Disable it in Codex system settings as well if they also want the client-level global skill list to stop surfacing it

For global skills, the inverse is also true when re-enabling:

1. Enable it in `skill-scope-manager` so local scope resolution and `AGENTS.md` can expose it again
2. Enable it in Codex system settings as well if they also want the client-level global skill list to surface it again

Use `remove` only when the user wants to delete the scoped copy itself.

### Modify

Use `where <skill-name>` to resolve the absolute path.

- If there is one instance, edit that path
- If there are multiple instances, ask whether to edit one instance or all instances

If the change is a scope change rather than a content change, use `move`.

### Query

- `list`: all managed skills and their scopes
- `where <skill-name>`: all absolute paths for that skill
- `here --cwd <path>`: which skills are active in a path
- `audit`: registry, disk, and AGENTS.md drift

### Temporary cross-scope invocation

Use this workflow when the user explicitly wants to call a skill that is outside the current scope.

1. Resolve candidates with `borrow-preview`
2. If needed, narrow to a single target with `borrow-resolve`
3. Show the user:
   - the target skill name
   - the target scope
   - the absolute `SKILL.md` path
   - that this is a one-time, out-of-scope invocation
4. Only after the user confirms, read the target `SKILL.md`
5. Use that skill for the current task only

Rules:

- Do not modify `AGENTS.md`
- Do not modify registry scope assignments
- Do not add the target skill to the current scope
- Do not cache approvals across the session
- Every out-of-scope invocation requires a fresh explanation and a fresh confirmation

If the requested skill is already available in the current scope, say so and do not treat it as a borrow.

#### User confirmation template

When an out-of-scope skill has been resolved, use a clear confirmation message before reading that skill.

Use this template:

```text
The skill you requested is outside the current scope.

Target skill: <skill-name>
Target scope: <scope-root>
Target SKILL.md: <absolute-skill-md-path>

Before I borrow this out-of-scope skill, please use the client's slash permission command to give the agent enough access for this task.

Use at least Default Access. If this borrowed skill may need broader filesystem reads or execution outside the current scope, switch to Full Access first.

After that, please explicitly confirm that I may read and execute this out-of-scope skill for this one invocation.

This borrow is one-time only:
- it will not change AGENTS.md
- it will not change the registry
- it will not add the skill to the current scope
- it will not persist after this task

If you approve, I will load this skill and use it once for the current task.
```

Rules for this confirmation:

- Always show the absolute `SKILL.md` path
- Always say that the skill is outside the current scope
- Always ask for explicit approval before reading the target `SKILL.md`
- Always tell the user to adjust the agent's access level through the client's slash permission command before approving the borrow
- Always mention `Default Access` as the minimum recommended level
- Always mention `Full Access` when broader filesystem reads or execution may be needed
- Even if the current environment already appears to have enough filesystem access, still require explicit user approval as a scope-boundary confirmation
- If the user does not approve, stop the borrow flow and continue without loading the out-of-scope skill

## AGENTS.md management

Use `sync-agents` to maintain a managed block inside each scope's `AGENTS.md`.

Managed block markers:

```md
<!-- skill-scope-manager:begin -->
...
<!-- skill-scope-manager:end -->
```

Do not overwrite content outside this block.

## References

- Registry schema and behavior details: `references/registry_schema.md`
- Initialization-only guide: `references/bootstrap_init.md`
