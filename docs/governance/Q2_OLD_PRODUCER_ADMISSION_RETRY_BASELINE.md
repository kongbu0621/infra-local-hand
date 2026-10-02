# Q2 旧生产者准入解析失败后的单次替代批次：待确认基线

- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 规则来源及 SHA-256：继承根 `AGENTS.md` 的直接固定来源与
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；
  本次 executor 已从 private companion source 的固定 commit 直接完整读取规则，commit 与
  内容 SHA-256 均匹配。本范围因尚无 Owner B 而继续保持 OPEN。
- Documentation A：`68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`。
- A tree：`2cc3158e3269db5fbdd01ab16185a2f34db29144`。
- Scope：`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1`，P1–P4。
- Gate：**PROPOSED / OPEN**。Owner 尚未针对这个准确 A 作出 B；没有本范围 C 或 D。
- 当前产品 source implementation：仍为
  `1a900e4a38e9567655f21cbf3c3f17941de1a8d5`。

| A 中的文件 | SHA-256 |
|---|---|
| `docs/a2-execution/q2-old-producer-admission-retry/REQUIREMENTS.md` | `99cda6cece535d8cff49721f9daf117d69dbf373f82c8f89f3b6dc33725085d1` |
| `docs/a2-execution/q2-old-producer-admission-retry/ARCHITECTURE.md` | `c1ebab031fe52403fe005b3848c80981ef06243af1cc51aca7602d0d9b36268e` |
| `docs/a2-execution/q2-old-producer-admission-retry/IMPLEMENTATION_PLAN.md` | `f295cf6b165134e92bc41400820897b93342fb7c9bb23d147e591307fb3e284d` |

上表须以 A 的 Git 字节核验；本登记不修改 A 的三份文档，也不是 CLOSED C。
已消费的 `20261001e` M4 保持 `FAILED_RETAINED`：它在
`old_producer_admission` 因私有 helper 读取被 systemd 省略的 `ExecStartPre`
触发 `KeyError`，`normal_chain_executions=0`，没有进入 provision。该事实不退款、
不恢复旧批次，也不证明准入或 Q2 通过。

准确 A 提议一个独立 `20261002a` create-only 批次：只为四个可省略的空 Exec 数组
字段补空字符串默认值，并把已 CLOSED K 链的专用 reader 窄接入新 consumer，且只在
固定普通身份 guard 后读取 boot_id 与自身 mountinfo。旧 K 授权本身只覆盖 local
preflight；本集成仍须本范围自己的 B → 独立 bookkeeping-only C → D，不继承旧包、
marker、批次或现场权。产品 commit/tree、旧现场和预算保持；新 project ID 固定为
`12061..12067`。

当前 H07 的全运行期 rate/pause 与独立 remote-stop 证明，以及消费/evidence 双 parent
的文件系统、峰值和持久资格均未闭合。因此当前只允许 `field_ready=false`、
`allow_run=false`、无 `TASK.txt` 的非执行材料；不得生成可现场执行 ZIP、创建 host
消费对象或连接 guest。若闭合这些硬门需新增机制、来源或权限，须另走准确受影响
A/B/C/D。未来即使包和资格完成，现场 P4 仍需 Owner 另发独立稳定 event/ref，准确绑定
scope、batch、A/C/D、ZIP basename/bytes/SHA-256、固定 evidence basename、四个独立
`evidence_*` 限制、仅一次及失败不重试。

本 A 还明确披露 replay 拒绝所依赖的 trusted-storage/no-same-UID-tamper 外部治理前提；
它不是 0700/0400 提供的技术性防回滚证明。Owner 只有在 B 中绑定准确 A 并明确接受该
前提，才可关闭本范围 Gate。裸“继续/授权继续”、CI/READY、产品 commit、ZIP 或
`TASK.txt` 均不能替代 B 或独立 P4 event。

若 Owner 决定批准这个方案，可准确回复：

> 按原 R，批准 A 68424df2ddbf812b9479ffa7a64dcaa59a2a9f76 的旧生产者准入单次替代批次方案（LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1），接受该 A 披露的 trusted-storage/no-same-UID-tamper 治理前提，批准四字段解析修复及两项固定内核视图 reader 的 consumer 窄集成，关闭该范围 Gate，并授权 P1–P3 实施以及 P4 合同/资格验证；不发行 20261002a 现场运行，不授权生成或执行可现场 ZIP。

上句是待决定文本，**不是已经发生的 Owner B**。必须先保留准确 B，再独立提交只含
关闭登记的 C，之后才可形成实现 D；现场 P4 仍按上述独立事件与硬门处理。
