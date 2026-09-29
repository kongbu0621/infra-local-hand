# Q2 普通操作者记录组件实现复核

2026-09-29 +08。**既有 H1/H2/H4 CLOSED 内新增显式普通身份 v2 组件；完整现场执行仍未准入。**
接续[有限 wrapper profile 修复](Q2_WRAPPER_PROFILE_IMPLEMENTATION_REVIEW.md)，
不重复采集固定来源，也不重放原主机诊断或 startup batch。

## 准确实现与授权边界

| 项目 | 固定值 |
| --- | --- |
| 实现 D | `c2373313eb78aa55373cb0318d08d5f60424dafd` |
| D tree | `78634f75004548aaa6f42549fae45d9b60172c0c` |
| Parent | `b777ec29d059cb87db66aed7aa3105ace52e798c` |

原 R 为 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接原规则 SHA-256
`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 已核对。
原 H A 为 `8402f0cc82d8a0ac0b9a56716bf276f41cafea37`，独立 C 为
`271c07cd16140aa5942dcf3fad468003c58b6b0e`。H 的可信操作者、固定父目录、
排他创建、身份与账单绑定及隔离验证已经批准；root-only 是原实现的窄支持范围。
独立范围复核确认这一组件修复在原 H1/H2/H4 内，不新造 Owner 决定或整体重批。

实现修改三个既有模块：`q2_host_window_record.py`、`q2_host_window_contract.py`、
`q2_reconciliation_bootstrap.py`；新增普通身份及其账单输入的两份独立测试。
没有新增运行时模块、依赖或工作流，也没有更改 H/K/L 的准确三层文档。
冻结 runtime `b49d3df3d1e76813faf08e59ab4975e25279c2fc` 与旧准确交付包保持。

## 新增组件的行为

| 边界 | 实现 |
| --- | --- |
| 版本选择 | 新 precheck/intent/consumption v2 使用显式普通身份 API；旧 v1 默认仍按 root 合同验证，跨版本混用拒绝 |
| 当前操作者 | 从本次真实进程取得 real/effective/saved UID、GID 与完整排序 supplementary groups，重复采样并持续核对；不接受调用者提供 UID 或身份字典 |
| 父目录与新对象 | parent 的 UID/GID 必须匹配当前操作者；保护链、ACL、名称与 fd 绑定保留；新目录 0700、新文件 0400，内容写入前核对实际类型、属主与名称绑定 |
| 原始时间与失败 | 保留同一 precheck 双钟起点；不刷新窗口；已创建的部分对象在失败后保留，不删除或自动重试 |
| 编码上界 | 写前按实际完整身份及最大 device/inode 编码检查原 12 KiB intent 限制；不截断 groups 或扩大预算 |
| 只读复核 | 历史 issuer 与当前 reader 分开；当前 reader 是同 UID 的稳定普通身份，历史 GID/groups 不变成永久的当前 reader 凭证要求；实际对象仍匹配历史 issuer |
| 跨账单绑定 | 新纯组合 API 核对准确 intent 原文、precheck 原账单摘要与复算值、marker 实物摘要/长度/身份、前后义务转移和 plan/机器关系 |

祖先 ACL 检查使用 fd 上的元数据操作，不在该 fd 上读取内容或枚举目录。
所有实际内容读取与目录枚举保留 `O_NOATIME`，没有弱化读取的回退路径。
原 `_special`、`_boot`、`_mount`、`_superblock`、`filesystem` 及
`require_field_readiness` 的函数 AST 与本轮 parent 完全相同。
固定内核普通读取的 local-only 例外没有接入消费入口。

进程 UID/GID/groups 不证明 fsuid/fsgid、capabilities 或 user namespace；
组件保留受信进程及身份不变前提，并在写入载荷前检查真实创建结果。
历史身份来自准确记录；静态 JSON 不会反序列化成实时准入凭证或消费权。
普通身份生产 precheck 仍先触发原 `HOST_WINDOW_FIELD_READINESS_UNPROVEN` 拒绝。

新 `validate_ordinary_host_window` 的成功结果仅为 `INPUT_CONSISTENT`，
`allow_run`、`field_ready`、`source_admission_proven`、`joint_admission_proven`、
`q2_accepted` 均为 false。旧生产 loader 未接入 v2；账单及联合账单 v1 格式未改变。
纯组合一致性不证明来源采用、实际 fsync 或原机事实。

## 验证与独立复核

本地 Python 3.12.14、pytest 8.4.2，使用已有独立环境及仓库固定依赖。

| 验证 | 准确结果 |
| --- | --- |
| 十二文件最终定向回归 | **306 PASS / 20 SKIP**，326 项不同用例；其中新增 99 项，79 个纯验证通过，20 个实际普通身份用例因云端 root 跳过 |
| 独立重报价/重摘要/跨绑定高风险子集 | **33 PASS**，属于上述用例，不重复累加 |
| 准确源、Python 3.10 语法、diff whitespace、冻结范围 | PASS；13 个准确文档/模块文件保持，H C 为 D 祖先 |
| 最终独立代码复核 | 两项发现均修复，must-fix 清零；五件审查字节与 D 完全匹配 |

18 项中间 SKIP 后新增两个祖先竞态反例，最终为 20 SKIP；不把中间计数当作最终计数。
真实普通身份 fixture 若显式提供而进程仍为 root，测试必须报错，不能改为跳过。
原生 CI [36531956523](https://github.com/kongbu0621/infra-local-hand/actions/runs/36531956523)
已在准确 D 完成，整体 **SUCCESS，3/3 jobs 成功**。

| 原生 CI | 准确结果 |
| --- | --- |
| Linux job `109287420962` | 源码 **2500 PASS / 51 SKIP**；独立强制 root collector **16 PASS / 0 SKIP**；wheel **94 checks / 292 commands PASS**；Plugin、启动 smoke、重复 smoke 与归档成功 |
| Windows job `109287420961` | 源码 **636 PASS / 918 SKIP**；wheel **10 checks / 10 commands PASS**；平台 smoke 与归档成功 |

Linux 源码比前一准确 D 增加 99 项通过，SKIP 数不变；完整 `-rs` 清单没有这两份新增测试。
准确源的 61 项普通身份测试中，20 项依赖真实普通身份 fixture，另有 38 项纯输入测试。
结合强制普通身份 fixture、全套成功及无对应 SKIP，确认 20 项真实普通身份测试已完成。
这是组合日志与明确 fixture 约束支持的结论，不伪称取得逐节点 JUnit 报告。
Windows 的新增跳过为普通身份整模块 1 项及 Linux 专用输入 38 项，按平台边界保留。

原生结果与日志摘要见 [native-ci.json](evidence/q2-ordinary-writer-20260929/native-ci.json)。
后继纯文档提交不改变 D 的源码/工作流，路径过滤不会另开这条 CI；不将 D 的测试移记为文档提交自身测试。
旧 SHA 的失败记录保留。

准确机器记录见 [verification.json](evidence/q2-ordinary-writer-20260929/verification.json)、
[independent-review.json](evidence/q2-ordinary-writer-20260929/independent-review.json) 和
[frozen-boundary-checks.json](evidence/q2-ordinary-writer-20260929/frozen-boundary-checks.json)。

独立代码复核发现新对象名称到 fd 的再次检查过晚：原路径直到 payload 写后才复核。
普通分支增加 intent 创建前、payload 写前的目录绑定核对，以及 ACL 检查后的文件名称核对。
另外补齐 ACL 全部检查后的完整祖先链名称复核，在 mkdir 前保留原 parent 元数据检查，
消费后只约束祖先身份/保护字段，允许已授权写入造成 parent 时间变化。
四个真实普通身份反例在 ACL 阶段实际换名并创建同名对象，分别要求 mkdir 或载荷写入前拒绝，
保留已产生的部分对象。旧 v1 默认路径未借此放宽。

成功 syscall 测试仅替代 readiness、固定 boot 与窄 ext4 资格三项先决条件；
实际身份、父链 ACL、`O_NOATIME`、创建、fsync、读回与竞争由真实系统调用执行。
这些是隔离组件验证，不能升级为原主机文件系统持久性、分配峰值或完整 Q2 证明。

## 剩余准入差额

当前原 host parent 的 indexed 12 KiB 事实仍不符合既有窄 filesystem profile。
本轮没有修改原机目录、权限、ACL、账号、挂载特性或 privilege，也未试写原机。
父目录正向分配增量仍由 writer 单列，尚未在 marker 子树账单中形成完整共同覆盖合同。
原 64 KiB / 4 inode 预留保持；不能据此宣称账单全部闭合或反向推定必然超限。

继续按[执行准入差额与顺序](Q2_POST_SOURCE_ADMISSION_PLAN.md)处理准确来源与工具环境绑定、
首次远端前独立截止与完整停止、账单历史/未来义务、FS 峰值/持久资格及原生审计。
涉及新增来源采用、内核用途或监督机制的实质变化，仍先形成准确受影响范围和三层 A。
共享依赖 UNKNOWN 及所有历史失败保持；原 startup batch 仍 NOT ISSUED。
本轮未连接 guest、未运行原 wrapper、未创建原机 marker、未派发 owner；完整 Q2 未验收。
