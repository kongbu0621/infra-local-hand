# 核心容量单次观察：准确 A 与待决记录

状态 **OPEN / NOT APPROVED / NOT ISSUED**。本文件是提案登记，不是 Owner B 或 CLOSED C。
2026-10-06 +08:00；scope `LH-Q2-CORE-CAPACITY-OBSERVATION-v1`，仅 O1–O3。

## 固定规则和准确提案

- Authority：Owner；Owner-mandated；adoption exceptions：none；无自动升级、弱化或例外。
- 原 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- [直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)，SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Documentation A：[1ba20d196facc82cf74aea88e7df3d4fe31e0584](https://github.com/kongbu0621/infra-local-hand/commit/1ba20d196facc82cf74aea88e7df3d4fe31e0584)。
- A tree：`2da72e01961f7ac1bf32edd521090dafe34b780a`；parent `128f72d0864dd631df4941c1a453ef436221f3db`。
- A 只新增下列三份文档，无实现、测试、配置、原始现场数据或发行摘要。

| 文档 | bytes | SHA-256 |
| --- | ---: | --- |
| [ARCHITECTURE.md](../a2-execution/q2-core-capacity-observation/ARCHITECTURE.md) | 7965 | 887b5b7328c3337d2b706c335728ff79199842e524e9ff20fea24ceff9f227e8 |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-capacity-observation/IMPLEMENTATION_PLAN.md) | 4891 | 609cf344a35299a40842b41cfc911a9baf61a4ce35cbd793c61e7cd164e4eb36 |
| [REQUIREMENTS.md](../a2-execution/q2-core-capacity-observation/REQUIREMENTS.md) | 6950 | d51bd38855359560bc4704645a07eb60c8efeebe3e6b8be847231976bd6b8d80 |

未受影响的旧 CLOSED 范围不变。本范围收到准确 Owner B 后，须先作独立 bookkeeping-only CLOSED C，
再实施 D；不能把本 OPEN 登记当作 C，也不能将 B/C 与实现混成一笔或 squash。

## 具体待批准动作

仅一次固定 `lhqcap-20261006a`：复用已有 SSH、管理 anchor 和安装，观察原计划五个 parent 的
当前设备和可用 bytes/inodes，作原 05c 合同的条件缺口比较。原计划准确摘要与已发五条映射固定路径，
不依赖重新生成完整旧 package。原始结果仅在受保护本地；公开角色/身份摘要与容量数字。

O1 实现专用 reader/runner 与窄回归；O2 验证并冻结准确 D；O3 通过原窗口本地检查后条件单次采集。
新 capture 完整承诺 4 MiB/8 inodes；当前 host 条件 264 MiB/80，保留四旧核心和旧诊断的全额承诺。
60s 本地原窗口/55s 停止点，初始化 reader 20s/5 CPU-s/128 MiB；一次 marker、一次 SSH，无重试或补采。
具体源、输入、路径、限额、SSH 参数与失败规则以准确 A 为准。

本提案显式保留 endpoint/sudo/Python 的诊断信任、管理日志副作用、共享空间竞争、更早 host UNKNOWN、
未证明远端祖先退出等边界。五目录采样不是原子快照；历史 placement、当前配额和旧进程闭合未复验。
计算只能叫条件比较，不能以当前足额认定核心准入或业务通过。失败保留原件，不换名再试。

不重装、不改 SSH/配额/资源合同、不清理、不退款，不运行 H01/Q4/H11 或第五次核心批次。
生产 E3 未启用；支线保持暂停。具体缺口尚未知，当前仍不能声称容量问题已解决。

## 审阅与本地 Codex 交接

本轮核对准确 main 的容量核算/诊断源码和 37336643512 的三个成功 job，并对照实际已发 657b1bc 的路径映射。
两份独立文档审阅均未发现发布阻断；已明确逐条重开路径链的 fd 上限，以及本诊断祖先 root-only 比 core 更严格。
只作文档一致性/空白检查，未为纯提案再跑源码矩阵；未创建新 reader、marker、SSH 或现场文件。

本地 Codex 拉取 main 后读取本记录和三文件。OPEN 时只审阅；准确 B 与独立 C 后直接完成 O1→O2→条件 O3，
同一范围内不逐项重新请求批准。最后交付实际容量/缺口表及针对性建议，不回到支线或再次盲跑整条业务链。

待 Owner 确认的准确决定为：按原 R，批准 A `1ba20d196facc82cf74aea88e7df3d4fe31e0584` 的
`LH-Q2-CORE-CAPACITY-OBSERVATION-v1`，关闭该范围 Gate，执行 O1–O3。
本句是待决文本，**不是已发生的 Owner 决定**。
