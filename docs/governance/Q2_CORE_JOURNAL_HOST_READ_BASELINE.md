# Journal 宿主读取修订准确方案及待决请求

2026-10-06，Asia/Shanghai。状态 **OPEN / NOT APPROVED**。
本记录只是准确提案和待决请求，不是 Owner 决定或 CLOSED C。

原维护的 311 项本地测试及准确 D CI 已通过，但真实本地预检在 host boot open 返回 EPERM；
没有进入 VM/writer 检查，更没有停机或增长镜像。诊断修复 `9c63f25b43ef713f51930f8927e55456c9a0a9fb`
已完成本地 313 PASS、无 SKIP，未重跑现场，也未放宽读取条件。
详见[实测及诊断记录](../a2-execution/Q2_CORE_JOURNAL_GROWTH_LOCAL_PREFLIGHT_20261006.md)。

## 准确基线

R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，
[直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)
本轮完整读取；源 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
Owner authority、mandate、无例外、禁止自动升级/弱化及 material change 规则保持。

Scope：`LH-Q2-CORE-JOURNAL-HOST-READ-v1`，R1–R3 only。
准确 A：**`2b4448c7b89d1910840f7aee2ae2b781f970e179`**。
Tree：`4cd1048bed0dcada220b19d01fbe525b9065fd41`。
Parent：`9c63f25b43ef713f51930f8927e55456c9a0a9fb`。
A 只增加以下三文档，不包含新权限实现、配置、依赖、原始机器证据或现场操作。

| 文档 | SHA-256 |
| --- | --- |
| [需求](../a2-execution/q2-core-journal-host-read/REQUIREMENTS.md) | `0eabd193b89131f701bf53f25e2426fb36d58df8c03e48ba50ab0d0fe5982fd5` |
| [架构](../a2-execution/q2-core-journal-host-read/ARCHITECTURE.md) | `6fe0fe118bbdd070773e1d9af9be7aed0da9256cdb5b21126b6b4d0d87e85b0f` |
| [计划](../a2-execution/q2-core-journal-host-read/IMPLEMENTATION_PLAN.md) | `7d57fa9d5003e53672abd7ac273ab1dd0fc728cff8044639a14d49f269d01300` |

## 最小新增权限和不变边界

仅对固定 host boot/self mountinfo 采用已有严格资格读取，并为五个固定镜像的原 writer 检查点
增加最多八次串行、固定代码、只读 root observer；每次最多 15s，纳入原窗口和管理预算。
只使用既有非交互 sudo，不能新增授权、安装工具或修改权限；不可用就停止。
它是新增特权可信组件，包含 sudo/PAM/audit 副作用，不是零风险或强制只读沙箱。
完整 writer 可见性仍为必须通过的条件；不可读、漂移或未知仍拒绝。

仅替代本轮未创建 marker 的失败预检窗口一次，保留旧失败事实。固定维护 ID 不变，
新窗口仍为 900s/780s，预检与执行共享绑定。原一个 marker、两次维护 SSH、一次关机、
一次镜像增长、一次启动及一次 ext4 增长的累计上限不增加。
原全部存储/CPU/RSS/进程预算、历史 UNKNOWN、非排他容量、备份与逾期未闭合风险保持。
原维护 J1–J3 不重批；只对本文披露的改变请求决定，未授权前不实现或执行这些改变。

不把已有 311/313 PASS 当成新实现验证。准确 B 后先独立 C，再 R1 实现，R2 窄验证/冻结/相关 CI，
最后仅在全门通过后 R3 条件执行原未消费维护。
失败不重试、不重连、不补采、不强制关机、不自动回滚、不清理；不执行 H01/Q4/H11。
支线暂停，生产 E3 限制保持。后续核心验收及其新 boot 采用仍需独立准确授权。

## 可直接审阅的批准文本

下列文字只是请求，没有发生 Owner B：

> 按原 R，批准 A `2b4448c7b89d1910840f7aee2ae2b781f970e179` 的 `LH-Q2-CORE-JOURNAL-HOST-READ-v1`，接受固定内核普通读取、经既有非交互 sudo 的有界只读 root writer observer 及其管理副作用，并允许以同一 `lhqjgrow-20261006a` 替代本次未创建 marker 的失败预检窗口一次。关闭该范围 Gate，执行 R1–R3；先独立 C 再实现。原维护预算及累计单次 marker、两条 SSH、关机和增长次数不增加；失败不重试、不重连、不补采、不强制关机、不自动回滚、不清理，不修改系统权限或配置，不执行 H01/Q4/H11；支线暂停，生产 E3 限制保持。

本轮新增提交仅在本地，未把过去对指定两个提交的推送批准扩大为本次新提交的主干发布授权。
