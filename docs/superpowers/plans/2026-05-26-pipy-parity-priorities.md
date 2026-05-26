# piPy Parity Priorities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 `harness/pi` 与 [pi.dev/docs/latest](https://pi.dev/docs/latest) 完成 piPy 的下一阶段高优先级对齐，先补齐「登录鉴权 + 会话树 + 交互命令覆盖 + Provider 能力」四个缺口。

**Architecture:** 保持当前 `pi_ai -> pi_agent -> pi_coding_agent` 三层架构不变，优先在 `pi_coding_agent` 增加认证与会话体验能力，在 `pi_agent` 增强树状会话模型，在 `pi_ai` 扩展 provider API 覆盖。先做与官方 Start here 高关联能力，再进入 TUI/Theme/Keybindings。

**Tech Stack:** Python 3.12、uv workspace、pytest、httpx、jsonschema、ruff

---

## 当前实现盘点（截至 2026-05-26）

`uv run pytest` 已通过 115 个测试，说明以下能力已稳定可用：

- CLI 与模式：`text` / `json` / `rpc`，支持 `interactive`、`-p`、`-c`、`-r`、`--fork`、`--list-models`
- 工具链：`read`、`edit`、`write`、`grep`、`find`、`ls`、`bash`
- 会话与可靠性：JSONL 持久化、continue/resume/fork、compaction、auto-retry
- 资源系统：skills、prompt templates、Python extensions、`/reload`
- 交互队列：steer/follow-up（包含 RPC 命令）
- SDK/RPC：`create_agent_session`、RPC 命令集（`prompt/get_state/get_messages/...`）
- Provider 子集：`openai`、`anthropic`、`google`、`faux` + `models.json` 自定义模型

---

## 与官方文档的高优先级缺口

1. **`/login` / `/logout` 鉴权流缺失**（Quickstart/Providers 首屏能力）
2. **会话树导航能力缺失**（`/tree`、`/clone`、分支摘要）
3. **交互命令覆盖不足**（`/new`、`/name`、`/copy`、`/export`、`/share`、`/resume`）
4. **Provider 覆盖不足**（pi 参考实现约 20 个 provider，piPy 当前 4 个）
5. **TUI/Theme/Keybindings 缺失**（属于下一阶段，可在本计划后独立开新计划）

---

## 目标文件结构（本计划范围）

- Create: `packages/pi_coding_agent/src/pi_coding_agent/auth/oauth.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/auth/storage.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/interactive_mode.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/modes/rpc_mode.py`
- Create: `packages/pi_coding_agent/src/pi_coding_agent/session/tree.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/session/types.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/session/manager.py`
- Modify: `packages/pi_agent/src/pi_agent/types.py`
- Modify: `packages/pi_ai/src/pi_ai/providers/__init__.py`
- Create: `packages/pi_ai/src/pi_ai/providers/azure_openai_responses.py`
- Create: `packages/pi_ai/src/pi_ai/providers/amazon_bedrock.py`
- Create: `packages/pi_coding_agent/tests/test_auth_login_logout.py`
- Create: `packages/pi_coding_agent/tests/test_session_tree.py`
- Create: `packages/pi_coding_agent/tests/test_interactive_commands.py`
- Create: `packages/pi_ai/tests/test_provider_parity_p4.py`
- Modify: `README.md`
- Create: `docs/providers.md`
- Create: `docs/sessions.md`

---

### Task 1: 登录鉴权对齐（`/login` / `/logout`）

**Files:**
- Create: `packages/pi_coding_agent/src/pi_coding_agent/auth/oauth.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/auth/storage.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/interactive_mode.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/modes/rpc_mode.py`
- Test: `packages/pi_coding_agent/tests/test_auth_login_logout.py`

- [ ] **Step 1: 写失败测试（login/logout）**

```python
def test_login_logout_roundtrip(tmp_path):
    storage = AuthStorage(path=tmp_path / 'auth.json')
    storage.set_api_key('openai', 'sk-test')
    assert storage.get_api_key('openai') == 'sk-test'
    storage.logout('openai')
    assert storage.get_api_key('openai') is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest packages/pi_coding_agent/tests/test_auth_login_logout.py::test_login_logout_roundtrip -v`  
Expected: FAIL with `AttributeError` for missing `set_api_key`/`logout`.

- [ ] **Step 3: 实现最小鉴权接口**

```python
class AuthStorage:
    def set_api_key(self, provider: str, key: str) -> None:
        ...

    def logout(self, provider: str) -> None:
        ...
```

- [ ] **Step 4: Interactive 增加 `/login` 与 `/logout`**

```python
if line.startswith('/login'):
    # /login openai sk-xxx
    ...
if line.startswith('/logout'):
    ...
```

- [ ] **Step 5: RPC 增加 `login` / `logout` 命令**

```python
if cmd_type == 'login':
    ...
if cmd_type == 'logout':
    ...
```

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run pytest packages/pi_coding_agent/tests/test_auth_login_logout.py -v`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/pi_coding_agent/src/pi_coding_agent/auth/oauth.py \
  packages/pi_coding_agent/src/pi_coding_agent/auth/storage.py \
  packages/pi_coding_agent/src/pi_coding_agent/interactive_mode.py \
  packages/pi_coding_agent/src/pi_coding_agent/modes/rpc_mode.py \
  packages/pi_coding_agent/tests/test_auth_login_logout.py
git commit -m "feat: add login/logout auth flow for interactive and rpc parity"
```

---

### Task 2: 会话树与分支导航（`/tree` / `/clone`）

**Files:**
- Create: `packages/pi_coding_agent/src/pi_coding_agent/session/tree.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/session/types.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/session/manager.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/interactive_mode.py`
- Test: `packages/pi_coding_agent/tests/test_session_tree.py`

- [ ] **Step 1: 写失败测试（树节点构建）**

```python
def test_build_tree_from_entries():
    entries = [
        {'id': 'u1', 'type': 'message', 'role': 'user'},
        {'id': 'a1', 'type': 'message', 'role': 'assistant', 'parentId': 'u1'},
    ]
    tree = build_session_tree(entries)
    assert tree.root_ids == ['u1']
    assert tree.children['u1'] == ['a1']
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest packages/pi_coding_agent/tests/test_session_tree.py::test_build_tree_from_entries -v`  
Expected: FAIL with `NameError` for `build_session_tree`.

- [ ] **Step 3: 实现树构建与分支选择**

```python
def build_session_tree(entries: list[dict]) -> SessionTree:
    ...

def clone_branch(entries: list[dict], leaf_id: str) -> list[dict]:
    ...
```

- [ ] **Step 4: Interactive 增加 `/tree` 与 `/clone`**

```python
if line == '/tree':
    # print compact tree listing and active leaf
    ...
if line.startswith('/clone'):
    ...
```

- [ ] **Step 5: 新增测试覆盖 clone 与 leaf 切换**

```python
def test_clone_branch_preserves_path_order():
    ...
```

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run pytest packages/pi_coding_agent/tests/test_session_tree.py -v`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/pi_coding_agent/src/pi_coding_agent/session/tree.py \
  packages/pi_coding_agent/src/pi_coding_agent/session/types.py \
  packages/pi_coding_agent/src/pi_coding_agent/session/manager.py \
  packages/pi_coding_agent/src/pi_coding_agent/interactive_mode.py \
  packages/pi_coding_agent/tests/test_session_tree.py
git commit -m "feat: add session tree and branch clone commands"
```

---

### Task 3: 交互命令对齐（`/new` `/name` `/copy` `/export` `/resume`）

**Files:**
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/interactive_mode.py`
- Modify: `packages/pi_coding_agent/src/pi_coding_agent/agent_session.py`
- Test: `packages/pi_coding_agent/tests/test_interactive_commands.py`

- [ ] **Step 1: 写失败测试（命令解析与行为）**

```python
def test_new_command_resets_session(tmp_path):
    ...

def test_name_command_persists_label(tmp_path):
    ...
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest packages/pi_coding_agent/tests/test_interactive_commands.py -v`  
Expected: FAIL for unsupported command handlers.

- [ ] **Step 3: 实现 `/new` 与 `/name`**

```python
if line == '/new':
    await session.new_session()
if line.startswith('/name '):
    session.set_session_name(...)
```

- [ ] **Step 4: 实现 `/copy` 与 `/export`**

```python
if line == '/copy':
    # copy last assistant text via pyperclip fallback
    ...
if line.startswith('/export'):
    ...
```

- [ ] **Step 5: 扩展 `/resume` 与选择逻辑**

```python
if line == '/resume':
    # reuse existing picker flow in cli/session manager
    ...
```

- [ ] **Step 6: 运行测试确认通过**

Run: `uv run pytest packages/pi_coding_agent/tests/test_interactive_commands.py -v`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/pi_coding_agent/src/pi_coding_agent/interactive_mode.py \
  packages/pi_coding_agent/src/pi_coding_agent/agent_session.py \
  packages/pi_coding_agent/tests/test_interactive_commands.py
git commit -m "feat: expand interactive slash commands toward docs parity"
```

---

### Task 4: Provider 覆盖扩展（先补 Azure + Bedrock）

**Files:**
- Create: `packages/pi_ai/src/pi_ai/providers/azure_openai_responses.py`
- Create: `packages/pi_ai/src/pi_ai/providers/amazon_bedrock.py`
- Modify: `packages/pi_ai/src/pi_ai/providers/__init__.py`
- Modify: `packages/pi_ai/src/pi_ai/model_registry.py`
- Test: `packages/pi_ai/tests/test_provider_parity_p4.py`

- [ ] **Step 1: 写失败测试（provider 可注册与鉴权解析）**

```python
def test_registry_includes_azure_and_bedrock():
    registry = get_registry()
    providers = {m.provider for m in registry.get_all()}
    assert 'azure-openai-responses' in providers
    assert 'amazon-bedrock' in providers
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run pytest packages/pi_ai/tests/test_provider_parity_p4.py::test_registry_includes_azure_and_bedrock -v`  
Expected: FAIL with missing providers.

- [ ] **Step 3: 实现 provider 适配层（最小可用）**

```python
async def stream_azure_openai_responses(...):
    ...

async def stream_amazon_bedrock(...):
    ...
```

- [ ] **Step 4: 注册 provider 到 model registry**

```python
register_provider('azure-openai-responses', ...)
register_provider('amazon-bedrock', ...)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run pytest packages/pi_ai/tests/test_provider_parity_p4.py -v`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/pi_ai/src/pi_ai/providers/azure_openai_responses.py \
  packages/pi_ai/src/pi_ai/providers/amazon_bedrock.py \
  packages/pi_ai/src/pi_ai/providers/__init__.py \
  packages/pi_ai/src/pi_ai/model_registry.py \
  packages/pi_ai/tests/test_provider_parity_p4.py
git commit -m "feat: add azure and bedrock provider parity subset"
```

---

### Task 5: 文档对齐（Providers + Sessions）

**Files:**
- Modify: `README.md`
- Create: `docs/providers.md`
- Create: `docs/sessions.md`

- [ ] **Step 1: 写文档测试清单（手工检查项）**

```bash
# 1) README 中列出已支持与未支持能力
# 2) docs/providers.md 说明 /login /logout 与 auth.json
# 3) docs/sessions.md 说明 /tree /clone /resume
```

- [ ] **Step 2: 更新 README 与新增文档**

```markdown
## Parity status
- Implemented: ...
- In progress: ...
- Planned next: ...
```

- [ ] **Step 3: 运行全量测试回归**

Run: `uv run pytest`  
Expected: PASS, 无回归。

- [ ] **Step 4: Commit**

```bash
git add README.md docs/providers.md docs/sessions.md
git commit -m "docs: add parity status and provider/session guides"
```

---

## 自检（Spec coverage）

- 官方 Start here 核心闭环（Providers + Sessions）由 Task 1/2/5 覆盖。
- 交互高频命令差距由 Task 3 覆盖。
- Provider 覆盖扩展由 Task 4 覆盖。
- 本计划避免一次性引入 TUI 重构，保持 DRY/YAGNI，先完成功能闭环。

---

## 非本计划范围（下一阶段）

- TUI 组件、Themes、Keybindings 全量对齐
- `/share`（GitHub gist）与平台相关集成
- OpenAI Responses/OpenRouter/Cloudflare/Groq 等更多 provider 全覆盖
- `pi install/remove/update/list/config` 包管理命令

---

Plan complete and saved to `docs/superpowers/plans/2026-05-26-pipy-parity-priorities.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
