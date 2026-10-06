# journal 保留数据扩容 Owner 决定 B

本记录逐字保留 Owner 对准确 A 的批准，仅关闭 `LH-Q2-CORE-JOURNAL-GROWTH-v1` 的 J1–J3。
本 C 只登记批准，不证明维护工具完成、J2 通过或现场扩容成功。

- Decision Authority：Owner（当前本地 Codex 对话的本仓库 Owner）。
- Event：`LH-Q2-CORE-JOURNAL-GROWTH-CLOSURE-20261006-01`。
- 登记日期：2026-10-06，Asia/Shanghai；使用事件 ID，不补造平台消息时间。
- 稳定来源：当前对话中紧接 journal 扩容方案交付、准确 A 及待批准文本之后的 Owner 回复。此 committed record 保存可核实副本。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮执行者完整读取直接固定规则，原 source SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`，Owner mandate/authority、无例外与 change control 保持。
- A：`59948ec4fedb807a31cdbff77acc134e84414160`，tree `57b57cc151c711f630bb047ac63fed35c74285dc`。
- Scope：J1–J3 only；三文档及摘要见[历史 OPEN 登记](Q2_CORE_JOURNAL_GROWTH_BASELINE.md)，其原字节不变。

## 准确决定

> 按原 R，批准 A `59948ec4fedb807a31cdbff77acc134e84414160` 的 `LH-Q2-CORE-JOURNAL-GROWTH-v1`，关闭该范围 Gate，执行 J1–J3；先独立 C 再实现。接受文档中的停机启动、两条维护连接、新 pidfile/serial null、boot 变化、备份及非原子恢复、历史 UNKNOWN、非排他容量和修改操作可能逾期未闭合的边界。按 A 预算执行一次固定维护，不重试、不补采、不强制关机、不自动回滚、不清理，不执行 H01/Q4/H11；支线暂停，生产 E3 限制保持。

## 独立 C 和实施边界

C 仅更新 AGENTS CLOSED 声明并保存本 B，不包含实现、测试、原型、配置或发行摘要。
C 与 A、首个 D 独立，D 必须从 C 后继，不 squash。

J1 实现窄维护工具；J2 在隔离合成 fixture 验证并冻结准确 D/tool/argv/inputs，相关 CI 通过；
所有必要前置门满足后才执行一次 `lhqjgrow-20261006a`。
最多一次永久 marker、两次预定维护 SSH、一次正常关机和一次启动；只有验证过的离线备份后才能增长原 journal。
固定目标 512 MiB，结果目标普通可用至少 400 MiB/32768 inode；没有临时追加容量或换路线权。
原四核心和两诊断保留全额承诺、原失败及 UNKNOWN。

新维护 host 条件 1296 MiB/370 inode，备份池 320 MiB，目标镜像池 576 MiB，控制/证据 8 MiB/32 inode，
维护余量 128 MiB；900s 观察窗口，780s 后不发新修改。完整控制/计量和保证边界以 A 为准。
不强杀正在修改数据的工具来制造硬时限成功；逾期保留 INCOMPLETE/UNKNOWN，不重试、补采、清理或自动回滚。
不执行 H01/Q4/H11，不修改原核心 boot 校验或生产 E3，不将维护重启记为 H11。
下一次核心及新 boot/管理关系采用仍需独立准确 authority。所有支线保持暂停。
登记 C 时，维护机会为 NOT_ISSUED。
