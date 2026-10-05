# locale 修复后单次核心验收提案基线

- Authority：Owner；状态 **OPEN / NOT APPROVED**。本记录不是 Owner B，也不是 CLOSED C。
- Scope：`LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1`，仅 L1–L3。
- 准确 A：`a243362d473891469b012a0ab8c3bd221794aa50`；tree `179045d0c3bcf9bf6c154c191068c96c379fe13e`。
- 修复源码基线：`d0c8749e47647264c14c406cd85c8c68006689a0`；不是尚未形成的新批实现或最终发行 D。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮已完整读取[直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)。
- 原 source SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`、Owner mandate/authority、无例外及 change control 保持。

| 准确 A 的权威文档 | SHA-256 |
| --- | --- |
| [REQUIREMENTS.md](../a2-execution/q2-core-post-locale-acceptance/REQUIREMENTS.md) | `35292af3218df0666b8c37251d802b0b3d68616ad07c4b36899d9c02d1169389` |
| [ARCHITECTURE.md](../a2-execution/q2-core-post-locale-acceptance/ARCHITECTURE.md) | `ae4aa9731e797ee79982e03f62489ec5a02d439b12de488279ba5c960ef16bcc` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-post-locale-acceptance/IMPLEMENTATION_PLAN.md) | `868d173d855e80be3d81218cf882febb5e00576e1d0505d539bade8fef99e870` |

## 已有证据和这次新增范围

已完成的 locale 修复及完整保存快照的一次离线验证不需要重新批准或重跑。
准备时远端 main 与本地均为 `3f5775fb0a70b9c8394590eeda455225268b2c27`，已只读核对准确修复 D 的 CI 37305140260 completed/success。
三次旧核心请求及一次诊断均已消费；离线通过不等于当前 guest 或 H01/Q4/H11 通过。

本 A 仅提出一次固定 `lhqcore-20261005c`：L1 接三旧 profile、诊断保留与新身份；L2 冻结验证准确 D 和真实双构包；L3 条件单次 H01→Q4→H11。
候选、原 wheel/89 文件 harness、原每批 180 MiB/13440、276 MiB/16512、2090 CPU-s、2624 MiB/1160、32/60/64 MiB 和 900/800/750s 保持。
三旧每项不退款，同设备四核心逻辑基准 1104 MiB/66048，另加更早 guest 义务；原 CPU 承诺合 8360 CPU-s，诊断初始化 reader 的原 5 CPU-s 另保留，不能据此宣称管理整树总上界。

必须由 Owner 明确决定的增量：

- 三旧核心历史 UNKNOWN 保持，以同一新请求中六次有界 SHOW/当前静止校验和全额保留为条件，不自动继承旧批批准。
- 诊断四原件的固定来源及 4 MiB/8 承诺保留；reader 报告完成不证明独立监督或管理祖先退出/用量。接受该特定缺口不单独阻断新请求，但不减免当前核心校验或忽视观察到的活动残留。
- 当前 host 检查四核心加诊断共 **260 MiB/72 inode**，不是排他预留；更早 host 覆盖/金额/共享池仍 UNKNOWN，空间竞争可能导致任务或证据失败。
- 三旧核对完成前，四核心 carrier 配置上界 **4096 MiB/512 pids**，明确不覆盖诊断残留、管理祖先或整机其它负载；原新批峰值不能冒充这段跨批保证。

需求、架构和计划分别固定成功/失败边界、严格输入/返回合同、实施验证顺序；没有把治理接受写成技术证明。
本轮核对了旧发行源码调用顺序和摘要、源文件尺寸、UUID 派生与资源加总，以及三文档交叉一致性。
没有读取或重放配置原文，没有新增现场 probe、私料搜索、测试全量重跑、源码/测试/fixture、发行 digest、marker 或请求。
当前代码仍是双旧 profile 和旧身份；新三旧/诊断绑定尚未实施，不能只替换名字就执行。最终发行 D 和真实包必须在 B/C 后形成并通过 L2。

## 建议决定文字 尚未收到

> 按原 R，批准 A `a243362d473891469b012a0ab8c3bd221794aa50` 的 `LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1`，接受三旧核心历史 UNKNOWN、诊断未独立监督的保留边界、全额承诺及文档中的非排他 host 容量和四核心 carrier 前置并发边界，关闭该范围 Gate，执行 L1–L3；先独立 C 再实现，仅新增一次固定 `lhqcore-20261005c` 请求，失败不重试、不重连、不补采、不清理；原每批预算及时限不变，支线暂停，生产 E3 限制保持。

收到真实准确决定后保留逐字 B 及稳定来源，先独立 bookkeeping-only C，再实施；本提案发布、截图交接或 CI 都不是该决定。
一般“继续”不能扩大成新现场权限。任何失败结束本单次范围，不生成自动下一批；生产启用始终不在其中。
