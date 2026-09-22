# 本轮设计补齐与复审记录

日期：2026-09-22；范围：文档；结论：三层设计形成可审查候选，**Gate 仍 OPEN**。
本记录不是三层规范的替代，不是 Owner closure、实现验证或 GX10/NAS 验收报告。

## 变更和依据

从主干 `9d6a91a63ff04dd83f16ddc7b716798ff4ff5d5c` 新建隔离工作树完成文档。
按 Owner“补齐一下”“Connector／MCP／Plugin 能用上就都设计进去”的要求：

- 新建 [需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、[实施验收](IMPLEMENTATION_PLAN.md)。
- 复用 GitHub Connector 和旧 mailbox；新增独立 job 契约、唯一 broker、MCP 与 Plugin 的拟议设计。
- 明确首批仅 `LH-A2-EXEC-MCP-v1` E1–E3 隔离实现；真实客户端、GX10/S2、NAS A2 分阶段验收。
- 同步 S2 三文档及能力/准备记录，最终部署改为新作业的准确受测候选，避免重复切换。
- S1 三层文档与既有 closure 保留，Ledger 本体 A2 CLOSED 不重复申请。

直接核对根 AGENTS 所指固定规则 R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，不复制 Private SOP。
核对 Ledger 固定 `6bd6acfbe5c35d581891eb87275e1173e17848fc` 的运行手册和验收脚本：
运行手册 blob `53b90d2f503e6772ee244ee60003f00627639177`；NAS 脚本 blob
`3dc8642cb3034db0e5451b5bf6dc6f4137f27f73`。
OpenAI 官方接口与接入依据集中列在架构文末；产品能力与当前账户可用性分别对待。

## 三路独立文档复审

| 复审方向 | 发现并修订的实质问题 | 定点复核结果 |
| --- | --- | --- |
| A2 作业契约与固定源码 | 资源 suite 准确名称/启动方式；TMPDIR/TMP/TEMP 归属；PENDING 状态；未 spawn 与无副作用的区别；NAS 阶段/删除承诺过强 | 原六项已闭环，无该范围内剩余阻塞 |
| 执行、并发、恢复与证据 | 固定 NAS 工具无全阶段初始挂载 fence；seal 缺 writer 静止/事件边界；不同根及资源别名缺公共权威锚点 | 原三项已闭环，验收 V05/V06/V07 同步 |
| MCP/Plugin 与当前客户端 | 仅验 token 不足以触发首次 OAuth；补 metadata、securitySchemes、401/challenge 和再授权测试 | 原发现已闭环，E2/E4 边界一致 |

交叉重合的问题没有按不同审查人重复当作独立代码缺陷。
本轮修复的是设计和范围表述；尚未生成新后端、协议测试源码、插件包或部署配置。
固定工具能力不足所带来的 E6 挂载保护门槛保留为 BLOCKED，不把文档修正写成代码已补强。

## 文档验证和交付限制

核对新增需求 AX-R01–R12、架构 AX-A01–A09、验收 AX-V01–V12 的对应关系，
检查本轮 Markdown 相对链接、差异空白、准确来源及公共披露模式。
逐字节比较 S1 三层权威文档与变更前 HEAD，保持不变。
变更仅限 Markdown 文档，不改变源码、测试、依赖、配置或运行状态；因此未声称编译或新实现测试通过。
本轮没有投递新 GX10 任务，没有安装 Plugin/MCP、操作 NAS 或切换服务。

文档提交 A 与随后登记其完整 SHA 的主干提交分别保留，登记提交仍 OPEN。
未来 Owner 准确批准后才产生独立 closure 提交 C，再实施 E1–E3；本记录不提前生成批准。
