# 核心下一次验收 Owner 决定 B

本记录保留 Owner 对一次固定新批次及必要实现的准确批准。原批次已消费及 UNKNOWN 不被改写；
新批次仅在准确 A 的全部条件成立后执行，不因治理关闭而立即发行。

- Decision Authority：Owner（本仓库 Owner 的当前对话用户）。
- Event：`LH-Q2-CORE-NEXT-ACCEPTANCE-CLOSURE-20261005-01`。
- 登记日期：2026-10-05，Asia/Shanghai；事件 ID 定位决定，不补造平台消息时间。
- 稳定来源：本仓库本地 Codex 对话中，紧接下列准确请求的 Owner 文字回复。
  原文保存在此 committed record，可由 Owner 核实；截图中的建议不作为批准。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮直接读取固定原文，采用关系与完整性保持。
- A：`0b0f445a36232f6bcd32c395b642f9a6b259d2db`；tree `c2ee02917768f4f8b6ef905b7fec0159dffd224f`。
- Scope：`LH-Q2-CORE-NEXT-ACCEPTANCE-v1`，N1–N3 only；三文档摘要见
  [原 OPEN baseline](Q2_CORE_NEXT_ACCEPTANCE_BASELINE.md)。

## 紧邻的准确请求

前一回复核对远端 main `1d1d15d`、修复 `40f0f98` 的三项 CI 成功；指出真实链只到有效 HELLO，
BIND 前停止，未收回业务结果，取消和恢复未验收。原单次机会已消费，新方案仍 OPEN。
请求原文为：

> 按原 R，批准 A `0b0f445a36232f6bcd32c395b642f9a6b259d2db` 的 `LH-Q2-CORE-NEXT-ACCEPTANCE-v1`，接受旧批次历史退出／使用量仍 UNKNOWN、当前旧 scope 核对通过且全额保留旧承诺后进行新批次的边界，关闭该范围 Gate，执行 N1–N3；先独立 C 再实现。仅新增一次固定请求，失败不重试、不重连、不清理；支线暂停，生产 E3 限制保持。

## Owner 回复原文

> 按原 R，批准 A `0b0f445a36232f6bcd32c395b642f9a6b259d2db` 的 `LH-Q2-CORE-NEXT-ACCEPTANCE-v1`，接受旧批次历史退出／使用量仍 UNKNOWN、当前旧 scope 核对通过且全额保留旧承诺后进行新批次的边界，关闭该范围 Gate，执行 N1–N3；先独立 C 再实现。仅新增一次固定请求，失败不重试、不重连、不清理；支线暂停，生产 E3 限制保持。

## 独立关闭与执行边界

本 C 仅更新根 Gate declaration 并保留本 B，不修改 A 三文档、历史 OPEN baseline 或已消费 F1 记录，
不包含实现、测试、配置、包或现场动作。后续 D 必须以本独立 C 及全部既有 C 为祖先。

新 session 固定 `lhqcore-20261005a`，对象、UUID、project IDs、candidate/wheel、每批预算和时限按 A。
旧五个原件及所有旧资源承诺全额保留，无退款、清理、旧安装重装、旧 deadline 刷新或 UNKNOWN 提升。
仅在同一新 carrier 的准入中证明当前旧固定 scope 不活跃后，旧历史 UNKNOWN 才不单独阻断新批次；
新批次任何缺项、漂移、超时、容量不足或未知仍停止。此批准不是通用重试授权。

N1 实施新旧身份、旧原件绑定、全额承诺及当前核对；N2 验证准确 D、真实私有输入及完整 package；
N3 仅在全部门通过后创建最多一次新 marker、发出最多一次 carrier，按 H01→Q4→H11 条件顺序执行。
H11 保留自身原 ledger/unit/grant/deadline，不重启业务、不延时、不读取业务结果补统计。
失败不重试、不重连、不另开退出检查连接，不以改名取得第三次机会。

namespace/watchdog 与其他支线保持暂停；production `E3_SUPERVISION_UNVERIFIED` 保持。
无系统配置变更、生产启用、E4–E6 或 NAS 授权。准确原件、当前现场和完整验收结果尚待实施验证。
