# Skill Scope Manager

Manage skill scope, initialization, migration preview, and one-time cross-scope skill borrowing for agent workspaces.

| [中文文档](#readme-zh)

## Why this skill exists

As skills accumulate, a new session has to consider more skill metadata during routing. That creates two practical problems:

- More globally visible skills means more prompt budget spent on skill discovery.
- The agent has a harder time picking the right skill when many skills overlap or sound similar.

This becomes especially noticeable once a personal workspace grows into many domain-specific skills such as writing, research, obsidian, social media, or automation workflows.

In practice, a good operating range for **globally visible** skills is usually around **20-40**. Below that range, routing is usually simple. Beyond that range, selection noise and context overhead often rise faster than utility. Total installed skills can be higher than 40, but the extra skills should usually be **scoped locally**, not left globally visible.

Another advantage of storing skills inside working directories is portability across agents. A workspace-local skill can be discovered and used by different agents that enter the same project, instead of being installed into and tied to only one specific agent environment.

`skill-scope-manager` exists to solve that problem:

- keep the globally visible skill set smaller
- move specialized skills into local scopes
- make scope state inspectable and auditable
- still allow one-time borrowing of an out-of-scope skill when needed
- make project-local skills easier to share across different agents without reinstalling them for each agent

## What this skill does

`skill-scope-manager` is a management layer for scoped skills. It helps an agent:

- initialize a scoped skill layout on a new machine
- maintain a registry of scopes and skill instances
- keep a lightweight global enable/disable switch for managed skills
- query which skills are installed and where they live
- determine which skills are active in the current path
- detect drift between disk, registry, and `AGENTS.md`
- move, register, remove, and sync scoped skills
- temporarily invoke an out-of-scope skill with explicit user approval

## Features

- Scope-aware registry with one skill record and multiple instances
- Separate initialization mode and daily management mode
- Preview-first migration flow for first-run setup
- Lightweight global enable/disable via registry state
- Automatic creation of minimal scope structure:
  - `skills/`
  - `AGENTS.md`
  - managed block
- Initialization writes a stable guidance block into the global `AGENTS.md`
- Managed `AGENTS.md` syncing without overwriting non-managed content
- One-time cross-scope borrowing without persisting approvals
- Distributable template registry with `bootstrap_complete: false`

## Installation

This repository is the skill folder itself. We recommend installing it in a **centralized directory** and symlinking it to your agents so that multiple agents (e.g. Codex, OpenCode) can share the same registry.

1. Clone the repository into a fixed, central location:

```bash
git clone <repo-url> ~/Vscode/SKILL/skill-scope-manager
```

2. Create symlinks from your various agent global skill directories to this central manager:

```bash
# Example for Codex
ln -s ~/Vscode/SKILL/skill-scope-manager ~/.codex/skills/skill-scope-manager

# Example for OpenCode
ln -s ~/Vscode/SKILL/skill-scope-manager ~/.config/opencode/skills/skill-scope-manager
```

3. Declare the skill in the skill manifest used by your agent, such as `AGENTS.md` if your agent supports it.
4. Run the initialization flow (see below) to create isolated global scopes for each agent while maintaining a single, shared registry file.
5. Restart or reload your agent runtime so the new skill metadata is loaded.

Notes:

- The distributed registry is intentionally empty and uninitialized.
- New users should run the initialization flow on their own machine instead of reusing someone else's registry state.

## Usage

### First-run initialization

For most users, the simplest way to initialize this skill is:

1. invoke `skill-scope-manager`
2. tell the agent to initialize skill scope management for the current environment

The agent should then guide the user through discovery, scope decisions, preview, and apply.

The commands below are the manual interface behind that guided flow, and are useful if you want to run initialization step by step yourself:

```bash
python scripts/skill_scope_init.py init-status
python scripts/skill_scope_init.py init-discover --skill-dir <path> [--skill-dir <path> ...]
python scripts/skill_scope_init.py init-preview --decision-file <file> [--plan-out <file>]
python scripts/skill_scope_init.py init-apply --plan-file <file>
```

Initialization is based on:

- user-provided current skill storage directories
- an explicit global root
- explicit local scope roots
- a preview plan that must be approved before apply

### Daily management

Use the registry script:

```bash
python scripts/skill_scope_registry.py list
python scripts/skill_scope_registry.py where <skill-name>
python scripts/skill_scope_registry.py here --cwd "$PWD"
python scripts/skill_scope_registry.py audit
python scripts/skill_scope_registry.py discover --unregistered-only
python scripts/skill_scope_registry.py register --skill-dir <path> --scope-root <scope>
python scripts/skill_scope_registry.py disable --skill-name <name>
python scripts/skill_scope_registry.py enable --skill-name <name>
python scripts/skill_scope_registry.py move --skill-name <name> --from-scope-root <src> --to-scope-root <dst>
python scripts/skill_scope_registry.py remove --skill-name <name> --scope-root <scope>
python scripts/skill_scope_registry.py sync-agents
```

Notes:

- newly installed or newly created skill folders are not scope-managed until `register --apply`
- for global skills, full disable/enable also requires the corresponding change in Codex system settings

### One-time out-of-scope borrowing

```bash
python scripts/skill_scope_registry.py borrow-preview --query <text> --cwd "$PWD"
python scripts/skill_scope_registry.py borrow-resolve --skill-name <name> --cwd "$PWD"
```

Borrowing is intentionally strict:

- every out-of-scope use requires fresh user confirmation
- no session cache is kept
- no scope assignments are modified
- the borrowed skill is not added into the current scope

## How it works

The implementation has four main parts:

### 1. Registry

- `registry/skill-registry.yaml` is the machine-readable source of truth
- `registry/skill-registry.md` is the human-readable view

The registry stores:

- scope definitions
- skill records
- global skill availability state
- multi-instance mappings for same-name skills
- bootstrap completion state

### 2. Shared helpers

`scripts/_scope_lib.py` provides shared logic for:

- path normalization
- metadata parsing
- registry load/save
- scope creation
- managed block syncing
- borrow candidate resolution
- audit helpers

### 3. Initialization engine

`scripts/skill_scope_init.py` handles first-run setup:

- discovers skills from user-provided source directories
- suggests `global / local / multi-scope copy`
- generates a machine-readable plan file
- applies exactly that plan

This is intentionally separate from daily management so the initialization guide does not have to load into context every time.

### 4. Daily management engine

`scripts/skill_scope_registry.py` handles routine operations:

- list / where / here / audit
- discover / register / move / remove
- disable / enable
- borrow-preview / borrow-resolve
- sync-agents

It treats scope management as an ongoing maintenance workflow after initialization is complete.

---

<a id="readme-zh"></a>

# Skill Scope Manager（中文）

用于管理 agent 工作区中的 skill 作用域、首次初始化、迁移预览，以及一次性的跨作用域 skill 借用。

## 为什么要写这个 skill

当 skill 越装越多时，新 session 在启动时会面对越来越多的 skill metadata，这会带来两个实际问题：

- 全局可见 skill 越多，skill 发现本身就越占上下文。
- 当很多 skill 的功能开始重叠时，agent 更难选对当前真正该用的那个。

这个问题在个人工作区里会越来越明显，尤其是当你同时维护写作、研究、Obsidian、社交媒体、自动化等多个方向的 skill 时。

实践上，一个比较健康的 **全局可见 skill 数量** 区间通常是 **20-40**。
低于这个区间时，路由通常还比较简单；高于这个区间后，选择噪声和上下文负担往往增长得比收益更快。总安装 skill 数当然可以超过 40，但额外的 skill 更适合被**放到局部作用域里**，而不是一直保持全局可见。

把 skill 存放在工作目录下还有一个优势：它更方便被不同的 agent 共同使用。只要不同 agent 进入同一个工作区并读取对应的 `AGENTS.md`，就可以复用同一套本地 skill，而不是把 skill 只安装并绑定到某一个特定 agent 的环境里。

这个 skill 的目的，就是解决这个问题：

- 让全局可见的 skill 集保持更小、更干净
- 把专用 skill 放到局部 scope
- 让 scope 状态变得可查询、可审计
- 在必要时，仍然允许一次性借用 scope 外的 skill
- 让项目本地 skill 更容易被不同 agent 共享，而不必为每个 agent 单独重复安装

## 这个 skill 是干嘛的

`skill-scope-manager` 是一个管理 scoped skill 的基础设施层。它可以帮助 agent：

- 在新机器上初始化 scoped skill 布局
- 维护 scope 与 skill instance 的注册表
- 维护一个轻量的全局启用/禁用开关
- 查询当前安装了哪些 skill、它们在哪
- 查询当前路径下哪些 skill 处于激活状态
- 检测磁盘、registry、`AGENTS.md` 之间的漂移
- 移动、注册、删除、同步 scoped skill
- 在用户显式批准后，一次性调用 scope 外的 skill

## 特性

- 支持“一个 skill 记录，对应多个 instance”的 scope registry
- 初始化模式与日常管理模式分离
- first-run 初始化采用 preview-first 迁移流程
- 支持通过 registry 做轻量的全局启用/禁用
- 自动创建最小 scope 结构：
  - `skills/`
  - `AGENTS.md`
  - managed block
- 初始化时会把一段稳定的 guidance block 写进全局 `AGENTS.md`
- 同步 `AGENTS.md` 时不会覆盖非受管内容
- 支持一次性的跨 scope 借用，不持久化授权
- 分发版本自带未初始化模板 registry

## 如何安装

这个仓库本身就是 skill 目录。我们强烈建议将它安装在**集中的固定目录**，然后通过软链接（symlink）的方式分发给不同的 agent，这样不同的 agent（如 Codex, OpenCode）就能共享同一个 registry。

1. 将仓库克隆到一个集中的固定位置：

```bash
git clone <repo-url> ~/Vscode/SKILL/skill-scope-manager
```

2. 为你需要使用的各种 agent 的全局 skill 目录创建指向该集中管理器的软链接：

```bash
# 以 Codex 为例
ln -s ~/Vscode/SKILL/skill-scope-manager ~/.codex/skills/skill-scope-manager

# 以 OpenCode 为例
ln -s ~/Vscode/SKILL/skill-scope-manager ~/.config/opencode/skills/skill-scope-manager
```

3. 在你的 agent 使用的 skill manifest 中声明这个 skill；如果该 agent 支持 `AGENTS.md`，就写入对应的 `AGENTS.md`
4. 运行初始化流程（见下文），为每个 agent 隔离出独立的 global scope，同时又能共享同一个本地 registry 文件。
5. 重启或重新加载 agent runtime，让新的 skill metadata 生效

说明：

- 分发版 registry 是空模板，不包含任何用户机器上的实际 scope 信息
- 新用户应该在自己的机器上运行初始化流程，而不是复用别人的 registry

## 如何使用

### 首次初始化

对大多数用户来说，最简单的初始化方式是：

1. 直接调用 `skill-scope-manager`
2. 告诉 agent：为当前环境执行 skill scope 管理初始化

之后 agent 应该引导用户完成 discovery、scope 分类、preview 和 apply。

下面这些命令，是这套引导流程背后的手动接口；如果你希望自己逐步执行初始化，也可以直接使用它们：

```bash
python scripts/skill_scope_init.py init-status
python scripts/skill_scope_init.py init-discover --skill-dir <path> [--skill-dir <path> ...]
python scripts/skill_scope_init.py init-preview --decision-file <file> [--plan-out <file>]
python scripts/skill_scope_init.py init-apply --plan-file <file>
```

初始化建立在这几个前提上：

- 用户明确提供当前 skill 存放目录
- 用户明确提供 global root
- 用户明确提供 local scope root
- 必须先生成 preview plan，再确认 apply

### 日常管理

使用 registry 脚本：

```bash
python scripts/skill_scope_registry.py list
python scripts/skill_scope_registry.py where <skill-name>
python scripts/skill_scope_registry.py here --cwd "$PWD"
python scripts/skill_scope_registry.py audit
python scripts/skill_scope_registry.py discover --unregistered-only
python scripts/skill_scope_registry.py register --skill-dir <path> --scope-root <scope>
python scripts/skill_scope_registry.py disable --skill-name <name>
python scripts/skill_scope_registry.py enable --skill-name <name>
python scripts/skill_scope_registry.py move --skill-name <name> --from-scope-root <src> --to-scope-root <dst>
python scripts/skill_scope_registry.py remove --skill-name <name> --scope-root <scope>
python scripts/skill_scope_registry.py sync-agents
```

说明：

- 新安装或新创建的 skill 文件夹，在 `register --apply` 前都不算 scope-managed
- 对全局 skill 来说，完整的禁用/恢复还需要在 Codex 系统设置里做对应操作

### 一次性借用 scope 外 skill

```bash
python scripts/skill_scope_registry.py borrow-preview --query <text> --cwd "$PWD"
python scripts/skill_scope_registry.py borrow-resolve --skill-name <name> --cwd "$PWD"
```

借用规则是刻意从严的：

- 每次域外调用都要重新获得用户确认
- 不保留 session 缓存
- 不修改 scope 归属
- 不会把借用的 skill 加入当前 scope

## 这个 skill 是如何实现的

实现主要分成四层：

### 1. Registry

- `registry/skill-registry.yaml` 是机器可读的真实来源
- `registry/skill-registry.md` 是给人看的表格视图

registry 里保存的是：

- scope 定义
- skill 记录
- 全局 skill 的可用状态
- 同名 skill 的多实例映射
- bootstrap 完成状态

### 2. 公共辅助层

`scripts/_scope_lib.py` 提供共用逻辑，包括：

- 路径归一化
- metadata 解析
- registry 读写
- scope 创建
- managed block 同步
- borrow 候选解析
- 审计辅助函数

### 3. 初始化引擎

`scripts/skill_scope_init.py` 负责首次初始化：

- 从用户提供的 source directories 发现 skill
- 给出 `global / local / multi-scope copy` 建议
- 生成 machine-readable plan 文件
- 严格按这份 plan 执行 apply

它和日常管理分离，是为了避免每次调用都把初始化说明重新加载进上下文。

### 4. 日常管理引擎

`scripts/skill_scope_registry.py` 负责日常操作：

- `list / where / here / audit`
- `discover / register / move / remove`
- `disable / enable`
- `borrow-preview / borrow-resolve`
- `sync-agents`

也就是说，它把 scope 管理视作“初始化完成后的持续维护流程”。

## License

MIT
