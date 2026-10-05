# sudo 修复后单次核心验收 Owner 决定 B

本记录保留 Owner 对准确 A 的逐字批准，仅关闭 S1–S3。两次旧失败及其 UNKNOWN 和完整承诺
不变；仅新增固定 `lhqcore-20261005b` 的一次条件请求。本 C 不包含实现或现场动作。

- Decision Authority：Owner（本仓库 Owner 的当前对话用户）。
- Event：`LH-Q2-CORE-POST-SUDO-ACCEPTANCE-CLOSURE-20261005-01`。
- 登记日期：2026-10-05，Asia/Shanghai；事件 ID 定位决定，不补造平台消息时间。
- 稳定来源：本仓库本地 Codex 对话中，紧接下列准确请求的 Owner 文字回复。
  本 committed record 保留可由 Owner 核实的副本；此前截图中的建议回复不是批准。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；执行者已直接读取固定原文，完整性
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`，采用关系不变。
- A：`f9ba6fbc2fa983c46322a00f3385af172fed7cb4`；tree `45b9d9dff11e87a8c83453bdab5d93c0b1ab5734`。
- Scope：`LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，S1–S3 only；三文档摘要见
  [原 OPEN baseline](Q2_CORE_POST_SUDO_ACCEPTANCE_BASELINE.md)。

## 紧邻的准确请求

前一回复核对新 A 三份文档摘要、固定身份和预算，说明只新增一次 05b 请求，host 条件为
192 MiB／48 inode，核验前三个 carrier 上界为 3 GiB／384 pids，旧失败和承诺保留。
当时 Gate 仍 OPEN，未实施或发请求；所请求的决定原文为：

> 按原 R，批准 A `f9ba6fbc2fa983c46322a00f3385af172fed7cb4` 的 `LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，接受双旧历史 UNKNOWN、全额保留承诺及文档中的 host 容量和前置并发边界，关闭该范围 Gate，执行 S1–S3；先独立 C 再实现，仅新增一次固定 05b 请求，失败不重试、不重连、不清理，支线暂停，生产 E3 限制保持。

## Owner 回复原文

> 按原 R，批准 A `f9ba6fbc2fa983c46322a00f3385af172fed7cb4` 的 `LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，接受双旧历史 UNKNOWN、全额保留承诺及文档中的 host 容量和前置并发边界，关闭该范围 Gate，执行 S1–S3；先独立 C 再实现，仅新增一次固定 05b 请求，失败不重试、不重连、不清理，支线暂停，生产 E3 限制保持。

## 独立关闭与执行边界

本独立 bookkeeping-only C 只加入本 B 和根 Gate 登记；不改 A 三文档、历史 OPEN 标签或任何旧
决定，不加入源码、测试、执行程序、配置、包或 release 摘要。D 必须以本 C 为祖先，不 squash。

S1 仅接齐双旧固定原件、05b 身份、双旧静止核验、逐设备全额承诺及返回消费。两旧各保留
276 MiB／16512 inodes、2090 CPU-s、64 MiB／16 host capture；同设备三批 guest 逻辑基准
828 MiB／49536，CPU 累计 6270，另计更早 guest 义务。host 当前条件为 192 MiB／48，
更早 host 覆盖、金额与共享池仍 UNKNOWN/null；完整历史准入和排他预留均 false，释放均零。
空间竞争仍可使任务或证据回收失败，不保证完整 receipt。

两旧静止核验前固定三 carrier 上界为 3 GiB／384 pids，不是整机可用量或预留保证；通过后才进入
新批原 2624 MiB／1160 pids 界。两旧各 A/B 四次 SHOW 合计最多 20 秒／8 CPU-s／131072 B，
全部计入新原预算，不新增连接或 unit。新批每项预算、900／800／750 秒、六文件与全部来源保护保持。

S2 必须核验准确 D 的完整 source、独立 installed、准确 SHA CI 和真实私料双构包；通过后仅登记
已审 dispatcher，再验证最终发行 D。在新的同一原 900 秒 caller 内重新核验来源、身份、十原件、
容量和 absence，全部通过才消费 05b 的唯一 O_EXCL marker 和 carrier request。
S3 严格 H01 PASS → Q4 PASS → H11；H11 使用自身原 ledger/unit/deadline，不重启业务或延期。

任一失败、断开或 UNKNOWN 即停止保留，不重试、重连、补采、清理、退款、换名或转为第四批。
当前 C 不证明实机成功，也不消费 05b；namespace/watchdog 等支线暂停，production
`E3_SUPERVISION_UNVERIFIED` 保持。新增范围或合同实质变化仍按原 R 重新处理。
