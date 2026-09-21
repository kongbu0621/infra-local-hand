# 程序仓库三层文档开工门禁：公开摘录候选

**已批准公开披露；等价性与采用尚未批准。** 见 [Owner 公开决定](PUBLICATION_OWNER_DECISION.md)。当前有效采用仍是 AGENTS.md 指向的固定 Private companion source。公开本文件不自动替换采用来源或关闭编码 Gate；以下规范摘录正文保持原候选内容。

- Source repository: `kongbu0621/engineering-sop`。
- Source commit: `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- Source path: `docs/workflow/program-repository-documentation-gate.md`。
- Status: **Provisional**；Adoption: **Owner-mandated for all program repositories**。强制采用不提升成熟度。
- Decision authority: **Owner**。
- 完整性与转换说明: [GATE_SNAPSHOT_MANIFEST.json](GATE_SNAPSHOT_MANIFEST.json)。

## 1. 范围与三层权威文档

新建及演化的 application、service、CLI、library、plugin 和可复用程序模块在实质编码前，必须分别存在、可定位并获 Owner 确认的需求、架构、当前阶段技术方案。三者须能指导实现、Review 和验收。README、聊天、Issue、TODO 或已有代码不能替代。纯非程序资产仓库不因使用 Git 而受此开工条件约束；引入程序前即适用。可以采用职责等价的现有文档，但要声明对应层次、Authority、状态和范围。

需求回答问题、consumer、目标、场景、范围/非目标、行为、依赖、风险、成功/失败条件和待决事项。架构回答职责、依赖方向、边界、接口/数据与控制流、状态/持久化/并发/恢复、质量属性、选择/取舍、扩展/迁移和未证假设。实施方案明确本阶段基线/范围、模块、API/schema/配置/存储/依赖、步骤/阻塞、兼容/部署/回滚、风险匹配的验证证据、完成定义与后续入口。

三层应具备需求→架构→步骤/证据→可观察结果映射。不能用设想的复用制造模块或仓库边界；遵守适用的仓库边界规则。冲突须显式报告给 Owner 或已声明 Authority，不能由 executor 任选。源码/实机事实可以推翻假设并触发修订，不能自动改变目标或 Authority。文档深度以足够指导工作为准，不以模板篇幅替代证据。

## 2. 本地采用与保密

所有程序仓库必须在 AGENTS.md 或等价权威入口记录：source repository、完整 source SHA、可读且一致的规则位置与完整性证据、Owner decision authority、exceptions 和禁止自动升级/弱化/撤销/新增例外的约束。不必因此采用全部 SOP，但不得跳过本 Gate。无法证明本地采用或无法读取规则时按 OPEN。

直接读取固定 SHA 的规则不要求额外 snapshot manifest。使用转换/摘录时，manifest 必须含 source repo/full SHA、每个 source path/content SHA-256、每个 snapshot path/content SHA-256、等价模式、Owner approval reference、转换范围、适用强制语义覆盖和后续同步 Authority/责任。缺项、digest 错误或等价性无法证明时 OPEN。

规则可读要求不赋予披露 Private source 的权限。Public 下游仅可采用 Owner 批准的最小完整公开摘录或 Private companion source；公开摘录保留 Status、mandate、source repo/full SHA 和全部适用义务。可访问性、完整性、等价性和保密无法同时满足时请求 Owner 决定。

项目例外只可调整保留核心语义的表示、位置或 bookkeeping；记录准确范围、受影响非核心要求、Owner 依据、风险及到期/修订条件。不得用例外弱化三层文档、固定完整规则/可读来源、Owner-only closure、OPEN 禁止编码、R/A/B/C/D 次序、reopen/change control 或禁止自动改变采用。改变核心义务须在源规则及采用决定中显式修订；mandate 不等于 Established。

## 3. 状态、闭合与证据顺序

本地 Gate 声明至少记录：规则 repo/full SHA、可读来源/完整性、mandate、Owner、exceptions/change rule、OPEN/CLOSED、三文档路径、既有文档 commit A、授权范围、Owner closure 的原文/身份/时间或 event ID/稳定引用及 reopen 条件。R 与 A 不得混淆，不预写尚不存在的自引用 commit SHA。

默认 OPEN。关闭前须确认：采用和来源有效；三文档存在、状态/Authority/基线清楚且无未解决冲突；阻塞问题已解决或明确不阻塞并有验证方法；Owner 对准确 R、A、scope 作出明确 closure；证据可核实；本地后续声明准确记录 CLOSED。文档批准、PR merge、agent/reviewer 判断、测试/CI PASS 和“继续”不能替代准确 closure。

顺序必须是 **R（已有上游规则）→ A（已有三文档提交）→ B（Owner 明确决定）→ C（单独 CLOSED 记录提交）→ D（以 C 为祖先的实现）**。B 保留准确原文、Owner 身份、时间或 event ID、稳定来源；可变来源由 C 或 committed decision record 保留 Owner 可核实副本。来源失效、身份不明或内容无法核实时按 OPEN；executor 不得补造决定。

C 只作 closure 和非语义 bookkeeping，不含实现、测试、可执行 prototype、依赖、schema migration 或 runtime config；也不能实质改动 A 的三层文档。A/C/D 必须分别存在；权威历史和交付策略保留引用与顺序，不能 squash C 和 D。squash-only 工作流先独立合并 C，再开实现 PR。

## 4. OPEN 状态与独立 spike

OPEN 允许文档、只读调查、既有代码的隔离 build/compile/test/lint/static diagnostics 及非实现性证据收集；不能修改 source/持久外部状态来前向实现，也不能把生成物纳入新实现。不允许新 production/test source、实现骨架、可执行探针、集成依赖或 runtime 配置。既有代码/小改动不构成例外。

迫近安全或数据损失风险下，Owner，或在 Owner 不能响应时已有且可定位的 operational/safety authority，可以进行最小可逆 containment：停止、禁用、撤销暴露或恢复已知良好版本；记录事件、动作、Authority、证据和回滚。它不得引入新行为/schema/实现，Gate 仍 OPEN。没有安全 containment 就停止并升级处理，executor 不自授权限。

可执行 feasibility spike 仍是实现，须单独以三层文档说明问题、隔离、非目标、废弃/停止条件与证据，先完成自己的 R/A/B/C/D。spike closure 不关闭 production；其实现、schema、依赖不能静默转入 production。

## 5. 演化和边界

需求、架构、阶段方案、scope、R/A、可读规则、完整性/等价模式/Owner approval、mandate、authority、exceptions 或 change rule 的实质变化自动重开受影响范围。先更新文档/映射/声明，再由 Owner 针对新基线确认；旧 closure 不自动转移。确能证明未受影响且仍在已闭合范围内的工作才可继续，否则 OPEN。

替代历史文档须保留 supersede 关系、理由及基线；架构保留稳定边界，阶段方案按阶段演化。验证证据要求、模块边界和已适用 SOP 规则继续有效，本摘录不 supersede 它们；冲突记录准确情境并由 Owner 决定。三层完成不等于实现验证，短反馈不能省略三层。

成熟度保持 Provisional。调整规则须有具体规模、作用、缺陷/返工和决策证据；提升 Established 须跨项目实践及 Owner 决定。弱化核心要求必须显式改源规则/采用并记录影响、风险和证据，不能由本项目自动解释。
