# Initialization Mode

Load this file only when:

- `registry/skill-registry.yaml` does not exist, or
- `bootstrap_complete` is false

Do not load this file during normal daily skill management.

## Goal

Initialize a centralized scoped agent skill layout for a user who has not yet set up a registry.

The initialization flow must:

- prompt the user for the **Central Manager Directory** (a fixed, centralized path where `skill-scope-manager` itself should reside, e.g. `~/Vscode/SKILL/skill-scope-manager`).
- ask the user to provide a list of **Agent Global Skill Directories** (e.g. `~/.codex/skills`, `~/.config/opencode/skills`).
- establish symlinks from each of the Agent Global Skill Directories pointing back to the Central Manager Directory, ensuring a single source of truth across all agents.
- create distinct `global` scopes in the registry for each agent (e.g., `codex_global` mapped to `~/.codex`, `opencode_global` mapped to `~/.config/opencode`).
- register the manager itself into these new global scopes.
- use user-provided current skill storage directories to discover existing skills
- ask the user to provide explicit local scope roots for other skills
- generate a preview plan before making changes
- apply only the exact previewed plan

## Required interaction order

1. Run `python scripts/skill_scope_init.py init-status`
2. Ask the user for:
   - **Central Manager Directory**
   - **List of Agent Global Skill Directories**
   - **Current skill storage directories** for discovery
3. **Execute Symlinking Setup**: 
   - Remove any existing `skill-scope-manager` in the target agent global directories
   - Run `ln -s <Central Manager Directory> <Agent Global Skill Directory>/skill-scope-manager` for each agent
4. **Register the Global Scopes**:
   - For each agent, run `python scripts/skill_scope_registry.py register --skill-dir <Central Manager Directory> --scope-root <Agent Root> --scope-type global --apply`
   - Rename the generic `global` or generated `scope_id` in `registry/skill-registry.yaml` to an isolated name like `codex_global`, `opencode_global`, etc.
5. Run `python scripts/skill_scope_init.py init-discover --skill-dir ...` to find remaining skills.
6. Show discovered skills with classification suggestions:
   - `global` (and for which agent's global scope)
   - `local`
   - `multi-scope copy`
7. Ask the user to confirm a placement decision for every discovered skill.
8. For every `local` or `multi-scope copy` decision, require explicit `scope_root` paths.
9. Write a decision file.
10. Run `init-preview`
11. Show the preview to the user.
12. Apply only after explicit confirmation with `init-apply`.

## Centralized Symlink Setup

The initialization tool must create symlinks automatically. For example, if the central path is `~/Vscode/SKILL/skill-scope-manager` and the target is `~/.codex/skills`:
- Remove any existing `~/.codex/skills/skill-scope-manager`
- Create symlink: `ln -s ~/Vscode/SKILL/skill-scope-manager ~/.codex/skills/skill-scope-manager`

## Decision file

The decision file must contain:

- `central_manager_dir`
- `agent_global_roots` (a list of agent root paths, e.g. `~/.codex`, `~/.config/opencode`)
- `source_skill_dirs`
- `placements`

Each placement must contain:

- `source_dir`
- `mode`
- `targets`

Each target must contain:

- `scope_root`
- `scope_type`

Allowed `mode` values:

- `global`
- `local`
- `multi-scope copy`

Allowed `scope_type` values:

- `global`
- `local`

Rules:

- `global` requires exactly one target and that target must be the declared `global_root`
- `local` requires exactly one explicit local scope target
- `multi-scope copy` requires at least two explicit targets
- Do not invent scope paths for the user

## Preview requirements

The preview must clearly show:

- which scopes will be created or updated
- which `skills/` directories will be created
- which `AGENTS.md` files will be created or updated
- that the global `AGENTS.md` guidance block will be created or refreshed
- which skills will be moved
- which skills will be copied
- where the registry and registry markdown will be written

The preview plan is the source of truth for `init-apply`.

## Apply requirements

`init-apply` must:

- create only the selected scope structures
- execute only the actions described in the plan file
- write the registry
- render the registry markdown
- write or refresh the global `AGENTS.md` guidance block during initialization
- sync the managed blocks in affected `AGENTS.md` files
- set `bootstrap_complete` to true

## Terminology

Use `agent` terminology in user-facing explanations.

Do not bind the initialization flow to Codex-specific wording.
