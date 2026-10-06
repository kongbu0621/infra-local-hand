# 核心容量单次观察 Owner 决定 B

本记录逐字保存 Owner 对准确 A 的批准，仅关闭 `LH-Q2-CORE-CAPACITY-OBSERVATION-v1` 的 O1–O3。
它不是核心业务验收授权，也不复用任何已消费的现场机会。

- Decision Authority：Owner（本仓库 Owner 的当前对话用户）。
- Event：`LH-Q2-CORE-CAPACITY-OBSERVATION-CLOSURE-20261006-01`。
- 登记日期：2026-10-06，Asia/Shanghai；使用事件 ID，不补造平台消息时间。
- 稳定来源：当前本地 Codex 对话中，Owner 提供容量观察方案交接截图、仓库执行指导后发出的下列准确批准。本 committed record 保存可由 Owner 核实的决定副本。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；执行者本轮完整读取直接固定规则。原 source SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`、Owner mandate/authority、无例外和 change control 不变。
- A：`1ba20d196facc82cf74aea88e7df3d4fe31e0584`；tree `2da72e01961f7ac1bf32edd521090dafe34b780a`。
- Scope：O1–O3 only；三文档及准确摘要见原[OPEN 基线登记](Q2_CORE_CAPACITY_OBSERVATION_BASELINE.md)。该历史登记及 A 三文件保持原字节。

## 准确决定

> 按原 R，批准 A `1ba20d196facc82cf74aea88e7df3d4fe31e0584` 的 `LH-Q2-CORE-CAPACITY-OBSERVATION-v1`，接受文档中的诊断信任、历史 UNKNOWN、全额承诺、非排他容量及远端退出边界，关闭该范围 Gate，执行 O1–O3；先独立 C 再实现。仅一次固定 `lhqcap-20261006a` 容量观察，最多一次 marker 和一次 SSH，按 A 的预算及时限执行；失败不重试、不重连、不补采、不清理，不执行 H01/Q4/H11。支线暂停，生产 E3 限制保持。

## 独立 CLOSED 记录和实施边界

本 C 仅新增本决定副本并更新根 AGENTS 的准确 CLOSED 声明，不包含实现、测试、可执行原型、配置或发行摘要。
C 与 A、首个 D 分别独立提交；D 必须以 C 为祖先，不 squash C 与实现。

O1 实现固定五目录 reader、一次性 runner 和窄回归；O2 冻结准确 D，完成窄验证、准确相关 CI、
既有私有输入及管理入口的本地检查；仅全部满足后，O3 才在原 60s 窗口内进行一次固定容量观察。
marker 创建即消费，最多一个 marker 和一次 SSH；失败保留原件，不重试、不重连、不补采、不清理、不退款。
完整结果最多进行一次不超过 5s 的纯本地条件比较，不能据此声称完整准入或业务 PASS。

四旧核心及旧诊断的历史 UNKNOWN、全额承诺、现有安装和空发行 allowlist 保持。
本次 capture 完整承诺 4 MiB/8 inodes，当前 host 检查 264 MiB/80，非排他预留。
诊断信任、管理副作用、远端未独立监督、历史 placement/配额未复验的边界按 A 保留。
不执行 H01/Q4/H11，不改 SSH、配额、资源合同或生产限制；所有支线暂停。
本 C 不证明 O1/O2 完成或现场观察成功；新请求当前为 NOT_ISSUED。
