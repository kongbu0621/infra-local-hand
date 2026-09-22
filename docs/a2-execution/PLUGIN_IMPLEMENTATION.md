# Plugin 与客户端工作流实现记录

本记录对应 `LH-A2-EXEC-MCP-v1` 已批准的 E1–E3，实现以独立 CLOSED 登记提交
`3676321` 为祖先；准确 R/A/B/C 见根 `AGENTS.md`。这不是新的设计基线或 E4–E6 准入。

`plugins/local-hand-a2/` 提供 portable `plugin.json`、`mcp.json`、完整七工具
`contract.json`、四个中文工作流及 `scripts/workflow.py`。根 manifest 使用 Agent Plugins
1.0.0，OpenAI 展示属性位于 `extensions.com.openai`。公共 `mcpServers` 为空，状态是
`UNCONFIGURED_E4_REQUIRED`；没有技术连接 ID、真实端点、凭据、自动 hooks 或服务启动命令。
E4 才为准确私有连接形成配置副本并另记摘要；公共模板不能宣称已连接当前 Work。

官方格式核对（2026-09-22）：

- [OpenAI 插件打包](https://developers.openai.com/plugins/build/plugins)
- [Agent Plugins manifest schema](https://agent-plugins.org/schemas/1.0.0/plugin.schema.json)
- [Agent Plugins MCP schema](https://agent-plugins.org/schemas/1.0.0/mcp.schema.json)

技能内容按 skill-creator 的 frontmatter、命名、流程和实际验证要求编制。
这是本仓库的分发资产，没有安装到个人技能目录；技能随该仓库正常 Git 发布保持来源。

## 客户端实际行为

| 接口 | 结果与边界 |
| --- | --- |
| `Workflow(callback, journal, admission)` | 宿主提供已认证且单次有超时上限的工具回调；journal 必须为私有自有目录，admission 固定 authority 与每个 profile 的六项 expected |
| `preflight()` | 校验本地及远端 schema digest、可信 authority、准确目标、分页版本；保留 execution_support，UNSUPPORTED/BLOCKED 类型禁止新提交；目录最多 32 页 |
| `reserve_job(key, ...)` / `submit(key)` | 先 create-only 持久保存完整请求和 operation_id，再调用工具；重试沿用同一 key，不重写旧请求 |
| `reserve_reconcile(key, job_key)` / `reconcile(key)` | 独立 reconcile_id 持久防重；同 key 不更换父作业，明确新 key 才表示新观察 |
| `cancel_job(key)` / `cancel_reconcile(key)` | 构造严格目标对象，不把旧业务取消指向新核对 |
| `observe(...)` | 精确查询业务或核对，最多 12 次、60 秒；返回最后事实，不将观察超时转成业务失败或新投递 |
| `prepared_reference(status)` | 核对成功/封存、版本化 outputs、固定 Ledger commit、原 operation、五项绑定摘要及 seal 引用；后续仍由 broker 验证真实 bytes |

客户端代码只消费工具回调，不读 token、不自行登录、不执行主机命令，也不替代 broker 的授权和幂等账本。
意图 key 是客户端明确选择的业务/观察标识，不来自日志内容；真实新作业与原请求重试必须区分。
客户端身份文件落盘或重试持久化确认失败时停止调用；不能把暂时可读的文件当持久保存成功。
回调的单次请求预算由宿主保障，E2 合成回调不证明真实 Work 传输的超时语义。

证据由同版 `local_hand_jobs.evidence_client` 执行分块重组与 ZIP/seal 校验；插件没有重复下载器。
宿主必须将原始 chunk 直接交给该组件和有界 writer。E4 缺该桥接时保持 BLOCKED，不能改用公开 URL。
本轮未安装真实插件、连接实际客户端、切换 GX10 服务或运行真实 NAS。

## 验证范围

`tests/test_local_hand_plugin.py` 覆盖公开包结构、准确契约、四技能内容边界、回执丢失与重启后的身份复用、
持久化和损坏记录、authority/expected/schema 漂移、分页版本、双取消目标、有限观察和封存引用。
四个技能目录均通过 skill-creator 的 `quick_validate.py`。
首次在基础解释器尝试独立 `jsonschema` 校验，因缺该模块以 `ModuleNotFoundError` 退出。
随后使用本轮完整 hash 锁定的构建 venv，直接读取官方 schema，两个 manifest 均通过
`jsonschema.Draft202012Validator`。所用 schema SHA-256 分别为
`0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883`（plugin）和
`6539175bfcdf43085855183e86da40ea94b166547a72b47ae9a0a390516d3acb`（MCP）。
首个失败未计为 PASS；未因校验单独引入产品依赖。
准确命令结果与计数随本轮总验证记录封存；这些客户端测试不替代 E3 真实 cgroup 或 E4 实际文件交付。

另由 `tests/test_local_hand_jobs_integration.py` 组合真实 contract/Policy/Registry/Broker/StateStore、
Runner、EvidenceStore、EvidenceClient 和 Plugin 客户端；仅以明确的 SyntheticManager 代替 OS 管理器及其
固定程序执行。该链经七接口完成发现、准备引用、源码/四专项/安装态计划和实际 ZIP 文件交付，
ZIP 包含 MANIFEST、BROKER_EVENTS 与 STOP_PROOF；合成程序输出均标记 `SYNTHETIC_MANAGER`。
测试还覆盖账本重启后的 prepared 目录恢复、原请求重取不再执行、跨主体拒绝及当前撤权。
它暴露并推动修复了重启时 Registry 与 Policy 的准备引用目录未同步问题。
真实维护 Unix socket 的跨入口试验独立记账，当前宿主创建该 socket 返回 EPERM，列为 UNSUPPORTED/SKIP；
不能把直接回调的通过替代真实维护 socket 或实际 MCP 网络验收。
