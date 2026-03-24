# Initialization Mode

Load this file only when:

- `registry/skill-registry.yaml` does not exist, or
- `bootstrap_complete` is false

Do not load this file during normal daily skill management.

## Goal

Initialize a scoped agent skill layout for a user who has not yet set up a registry.

The initialization flow must:

- use user-provided current skill storage directories
- ask the user to provide an explicit global root
- ask the user to provide explicit local scope roots
- generate a preview plan before making changes
- apply only the exact previewed plan

## Required interaction order

1. Run `python scripts/skill_scope_init.py init-status`
2. Ask the user for:
   - one explicit global root
   - one or more current skill storage directories
3. Run `python scripts/skill_scope_init.py init-discover --skill-dir ...`
4. Show discovered skills with classification suggestions:
   - `global`
   - `local`
   - `multi-scope copy`
5. Ask the user to confirm a placement decision for every discovered skill
6. For every `local` or `multi-scope copy` decision, require explicit `scope_root` paths
7. Write a decision file
8. Run `init-preview`
9. Show the preview to the user
10. Apply only after explicit confirmation with `init-apply`

## Decision file

The decision file must contain:

- `global_root`
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
- sync the managed blocks in affected `AGENTS.md` files
- set `bootstrap_complete` to true

## Terminology

Use `agent` terminology in user-facing explanations.

Do not bind the initialization flow to Codex-specific wording.
