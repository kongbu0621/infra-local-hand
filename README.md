# infra-local-hand

受控本地执行器：提交任务、执行、取消、按原任务恢复查询、取回结果。

**当前只推进核心链 H01 → Q4 → H11，暂停外围开发。**

- 保留：任务提交和执行、状态查询、运行中取消、同任务恢复、结果及证据读取。
- 屏蔽：NAS 新作业不出现在可提交能力或 MCP 参数选项中；手工提交也会在计划生成、资源预留和执行前被拒绝。
- 暂停：NAS/A2 扩展、新插件和连接器功能、全宿主扫描、诊断平台及无关重构。

旧作业记录仍可查询、取消及核对，现有协议保留历史类型。
鉴权、任务身份、数据保护、资源上限和结果完整性属于核心保障。
MCP 与本地 CLI 共用同一个作业后端，入口限制一致。

## 核心实际状态（2026-10-11）

**核心代码和验收脚本已经存在；当前目标环境的 H01/Q4/H11 整链尚未验收。**

| 层次 | 已完成与当前边界 |
| --- | --- |
| 作业后端 | 已有提交、执行、状态查询、取消、同账本恢复观测和结果读取；CLI/MCP 共用后端。恢复不重放业务，证据不足时保留 UNKNOWN。 |
| 验收链 | 已有 H01 正常执行、Q4 运行中取消、H11 同任务恢复观测脚本及离线回归；原 `lhqcore-20261007a` 三案仍为 NOT_RUN。 |
| 原现场环境 | 曾完成原配置 VM 启动及[当前 guest 六命令核验](docs/a2-execution/Q2_CORE_RESUMED_VM_FIELD_20261010.md)。随后宿主机重启，旧运行身份不再适用于当前环境。 |
| 最新现场结果 | [HB1/HB2 已完成](docs/a2-execution/Q2_CORE_HOST_REBOOT_READ_FIELD_20261011.md)：旧 PID/pidfile 缺失、固定端口无监听；六镜像当前保护检查通过，但 device/inode 组合与旧记录不符。 |
| 当前代码验证 | 最新代码合入点 `9f2156d` 的 [CI 三项成功](https://github.com/kongbu0621/infra-local-hand/actions/runs/38140957241)，Linux/Windows 独立安装通过。后续状态与方案提交仅改文档。 |

此前 [RP2 维护预检](docs/a2-execution/Q2_CORE_RUNTIME_PREPARATION_FIELD_20261011.md)
因宿主 boot 与旧 activation 不一致而停止，SSH 为 0、消费标记未创建；它和其他旧返回
保持原样，不重放。HB2 固定读取成功不等于 VM、guest 或核心验收通过。

下一步已在 [PR #22](https://github.com/kongbu0621/infra-local-hand/pull/22) 准备为一个
[HR1–HR4 整批接续](docs/a2-execution/q2-core-host-rebind-continuation/IMPLEMENTATION_PLAN.md)：
明确采用 HB2 固定六镜像为本次新启动基线，再接原配置启动、现有 guest 核验、一次维护
及原 H01/Q4/H11。方案仍为 OPEN / NOT APPROVED，尚无新范围实现或现场执行；
历史文件系统及内容连续性仍 UNKNOWN，当前身份校验不放宽。复用已有后端、验收脚本
和安装，不重新实现核心功能；[本地 Codex 交接](docs/a2-execution/CORE_HOST_REBIND_TASK_20261011.txt)
已备好，NAS 和外围继续暂停。

## 使用与开发入口

| 入口 | 内容 |
| --- | --- |
| [使用说明](docs/USAGE.md) | 隔离安装、配置和既有任务接口 |
| [执行约束](AGENTS.md) | 当前核心范围及既有现场边界 |
| [需求](docs/REQUIREMENTS.md) | 执行器目标与验收条件 |
| [架构](docs/ARCHITECTURE.md) | 任务、权限和结果边界 |
| [作业接口](docs/a2-execution/ARCHITECTURE.md) | 受限作业后端、CLI 与 MCP 接口 |

历史方案和验证记录仍保存在 `docs/`；[旧首页完整记录](https://github.com/kongbu0621/infra-local-hand/blob/b0fffefd95335fd8835f0ac5a6b01c3d2ca51654/README.md)可追溯。
生产切换、真实客户端连接与 NAS 验收尚未完成。暂不添加许可证；任务、日志、凭据和原始证据保持私有。
