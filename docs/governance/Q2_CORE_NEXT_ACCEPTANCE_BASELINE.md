# 核心下一次验收提案 baseline

Status: **OPEN / NOT APPROVED**. Authority: Owner.
Scope: `LH-Q2-CORE-NEXT-ACCEPTANCE-v1`, N1–N3 only.

R 保持 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接源为
`kongbu0621/engineering-sop/docs/workflow/program-repository-documentation-gate.md`；
原规则 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
Owner mandate、Authority、no exceptions 与原 change control 全部保持。

准确三文档 A：**`0b0f445a36232f6bcd32c395b642f9a6b259d2db`**。
Tree：`c2ee02917768f4f8b6ef905b7fec0159dffd224f`。
审阅的既有源码修复：`40f0f989cc1d76f35a17bb1551ea6a1c68da0441`；不是本新范围 D。

| docs/a2-execution/q2-core-next-acceptance 下的权威文件 | SHA-256 |
| --- | --- |
| REQUIREMENTS.md | `a07ab93db9c73f777cc4d39a26c25c59f633c915cd7f53f0549580e6f059fa1e` |
| ARCHITECTURE.md | `43967dac7e640b4d6d46f802cb56001b1cf53d2aea724fc28d1bd98383518685` |
| IMPLEMENTATION_PLAN.md | `58b0935ab8c6fe42fc76c2d023f2b26a207796d18429df17c98b03a7dd410bfd` |

参见[需求](../a2-execution/q2-core-next-acceptance/REQUIREMENTS.md)、
[架构](../a2-execution/q2-core-next-acceptance/ARCHITECTURE.md)和
[实施方案](../a2-execution/q2-core-next-acceptance/IMPLEMENTATION_PLAN.md)。
独立复核重算四个 UUID，核对新旧 scope、一次消费、保留承诺及 UNKNOWN 的有限边界；
根复核五原件 pins 与已提交 F1 记录相符，总 9318 B。此类离线审阅不是现场通过。

## 请求决定的准确差异

原 F1 已消费且不会复活。提案只新增一次固定 `lhqcore-20261005a` 请求，推进 H01 → Q4 → H11。
N1 实现准确旧原件绑定、新身份、保留承诺与准入；N2 在消费前完成真实私有输入及发布校验；
N3 由本地 Codex 复用既有管理配置，仅执行一次新 carrier 并收回实际结果。
云端不以测试样本代替本地原件/现场观察；原轮证据及所有历史安装原样保留。

Owner 拟接受的有限边界为：旧准确失败批次的历史退出/EOF/时限闭合/usage 继续 UNKNOWN，
当前旧固定 scope 在同一新 carrier 的有界只读准入内证明不活跃，且旧全额承诺不退后，
该历史 UNKNOWN 不单独阻断新批次。新批次自身未知/超时/身份或容量缺项仍停止。
两批 core 同设备逻辑承诺合 552 MiB/33024、CPU 4180 s，host capture 合 128 MiB/32，
再加全部更早历史义务；逐设备规则及每批限额不放宽。仅 create-only 新批次安装，不重装旧安装。
固定 candidate/wheel、credential/权限/whole-file 校验不变；不开放通用重试、清理或生产切换。

## 准确决定建议，尚未收到

> 按原 R，批准 A `0b0f445a36232f6bcd32c395b642f9a6b259d2db` 的 `LH-Q2-CORE-NEXT-ACCEPTANCE-v1`，接受旧批次历史退出/使用量仍 UNKNOWN、当前旧 scope 核对通过且全额保留旧承诺后进行新批次的边界，关闭该范围 Gate，执行 N1–N3；先独立 C 再实现。仅新增一次固定请求，失败不重试、不重连、不清理；支线暂停，生产 E3 限制保持。

本登记不是 Owner B，也不是 CLOSED C；不得据此实施新批次代码、发请求或改动现场。
收到准确决定后须保留逐字 B 及稳定事件来源，再作独立 bookkeeping-only CLOSED C，后续 D 才能实施。
不能以“继续”、原修复 CI 或源码通过来重置旧单次消费。原未受影响 CLOSED 开发范围继续有效。

