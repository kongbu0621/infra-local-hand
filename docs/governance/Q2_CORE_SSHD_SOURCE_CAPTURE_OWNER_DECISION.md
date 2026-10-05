# sshd 单次只读取证 Owner 决定 B

本记录保存 Owner 的准确批准，仅关闭 `LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1` 的 P1–P3。
三次旧核心机会保持已消费。本次只授权固定诊断采集，不授权业务验收。

- Decision Authority：Owner（本仓库 Owner 的当前对话用户）。
- Event：`LH-Q2-CORE-SSHD-SOURCE-CAPTURE-CLOSURE-20261005-01`。
- 登记日期：2026-10-05，Asia/Shanghai；以事件 ID 定位，不补造平台消息时间。
- 稳定来源：本地 Codex 对话中，紧接“已准备并推送最小取证方案，main 为 50dfc33”的回复之后，Owner 发出的下列完整批准。
  本 committed record 保留可由 Owner 核实的逐字副本；截图和此前建议文字不是该决定。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮执行者已直接读取固定原文，原完整性
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 与采用关系保持。
- A：`f2eb31deb3c52d69ccd2079fb7d88608d1a25a62`；tree `dec4cf6e6cd32010d203e8bde2dfde4d53a02104`。
- Scope：P1–P3 only；三文档 SHA-256 逐项匹配[原 OPEN baseline](Q2_CORE_SSHD_SOURCE_CAPTURE_BASELINE.md)。

## 紧邻请求与 Owner 回复

前一回复说明只有三份提案及 OPEN 登记，未创建 marker、未发 SSH、未执行业务；请求批准固定配置快照，
最多 65 文件/1 MiB、60 秒本地窗口及 4 MiB 私有 capture，并披露远端退出可能 UNKNOWN。
所请求的决定文字与下列 Owner 回复逐字相同：

> 按原 R，批准 A `f2eb31deb3c52d69ccd2079fb7d88608d1a25a62` 的 `LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1`，接受文档中的只读诊断信任、三旧 UNKNOWN 与完整承诺、非排他容量、管理副作用及远端退出可能 UNKNOWN 的边界，关闭该范围 Gate，执行 P1–P3；先独立 C 再实现。仅新增一次固定 `lhqsshd-20261005a` 配置采集，最多一次 marker 和一次 SSH 请求，失败不重试、不重连、不补采、不清理；原文只留本地，不执行业务，不改变 SSH 配置；支线暂停，生产 E3 限制保持。

## 独立 C 与实施边界

本独立 bookkeeping-only C 仅加入本决定副本和根 AGENTS 的准确 CLOSED 登记；不改 A 三文档及历史 OPEN 标签，
不含源码、测试、scaffold、运行时配置、发行摘要或现场动作。新 D 必须以 C 为祖先，不 squash。

P1 实现固定采集器与窄回归；P2 离线验证、冻结准确 D/参数并核验本地私料；P3 全部门通过后最多一次固定采集和本地双解析对照。
对象、来源、60s caller、初始化后 20s/5 CPU-s/128 MiB reader、65 文件/1 MiB、2 MiB stdout、64 KiB stderr、
4 MiB/8 inode 新 capture 和 196 MiB/56 当前 host 条件均按 A。不将应用限额、非排他可用量或 reader 限制冒充全机硬保证。
原 SSH/sudo/PAM、运行时读取、日志/审计及访问时间副作用按 A 披露；超时或断连仍可留下未知远端退出，不补连确认。
只读取固定配置数据，原文受保护留本地；不运行 sshd -T，不修改 SSH 配置，不启动任何业务或 systemd unit。

一旦 marker 创建，即使未发送也消费；任何部分文件、失败或 UNKNOWN 都保留，不重试、重连、补采、清理、退款或换名。
旧三批 UNKNOWN、完整承诺及原件不变。本登记本身不消费新机会，也不证明取证或 H01/Q4/H11 通过。
namespace/watchdog 等支线保持暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。实质变更仍依原 R 重新处理。
