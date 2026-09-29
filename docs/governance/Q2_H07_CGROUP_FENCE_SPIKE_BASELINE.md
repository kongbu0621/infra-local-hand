# H07 cgroup 监督原语实验：准确方案基线

2026-09-29 +08。状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。

- Scope：`LH-Q2-H07-CGROUP-FENCE-SPIKE-v1`，仅 F1–F4。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 可读规则：engineering-sop 固定 R 的 `docs/workflow/program-repository-documentation-gate.md`；直接原件 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`，采用/Authority/例外/变更规则沿用根 AGENTS，未改变。
- 准确 A：`71c7e842c724650a0e949a63bb898699b41107be`。
- A tree：`25b8caa9af375562bb919a03b936b3cc45a4b39b`。
- A parent：`7392575c8d78899f8f7d31e64c5de145e0f24855`。
- Owner closure B：**尚无**；独立 CLOSED C：**尚无**；实验实现 D：**尚无**。

本记录只登记既有三文档提交，不是 C，也不允许开始实现。

| authoritative document | bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-h07-cgroup-fence-spike/REQUIREMENTS.md) | 7042 | `41706c5b07cfceea319f10dcab1fcc8b2606995b029566f3e13bb00e41affd51` |
| [架构](../a2-execution/q2-h07-cgroup-fence-spike/ARCHITECTURE.md) | 9254 | `6b7ef2487658e759df565084393e5de010db8f35de4966a4790320eea060116c` |
| [实施方案](../a2-execution/q2-h07-cgroup-fence-spike/IMPLEMENTATION_PLAN.md) | 9560 | `0bd3dab26e10e2fa9717ef218fa70846cf5ad3b5888ad2f17596c7b7b385e99d` |

## 准确新范围

新实验把固定合成任务的全部启动者置于可停止子树，通过 clone3 原子入组，
由独立 guardian 拒绝新请求、停止整树、核对原 pidfd/EOF；不会转发业务给外部 manager。
这改变执行机制与 fixture/setup 权限，属于独立 spike，不借旧 H4 关闭新增范围。

提案覆盖独立实验实现、有限离线验证、一个 manual-only GitHub workflow，
最多三轮 `ubuntu-24.04` x64 托管临时 runner 验证：首轮与至多两轮有明确源码
修复理由的复验；每轮六例各一次，job≤15min，总 job 执行额度≤45min。
executor 通过 GitHub 页面触发，绑定准确 D/run_id/attempt；不自动重试、不覆盖
历史。专属账户/cgroup/临时对象的 setup 和 cleanup 仅在该临时 runner 内。
UNSUPPORTED、未运行、身份缺证、控制者崩溃和清理未证均按准确事实保留。

原 PRO6000/guest/VM、固定 wrapper、冻结 runtime/wheel/Plugin、现有服务和原 Q2
唯一批次均不在实验动作范围内。lab 预算不是原 Q2 额度扩张；通过也不产生 H07
原链、FS、完整账单或生产资格。后续采用须有新的准确决定。

## 审查与追溯

已完成三路独立静态审查：原合同/Authority、控制机制/身份、预算/fixture。
实质意见已在 A 之前处理：

- H07 要求保留真实期限和停止事实，但没有要求共享 OS 任意故障下三秒必停；
  允许 UNKNOWN 的失败结果不能改成成功。H4 的“无 guest 运行”仍保留。
- 明确 T→G→S 的唯一创建链、空父节点与叶拓扑，以及仅在自有 B 中的必要
  `cgroup.procs` 写资格；held cgroup FD 不自动授予非 root 入组权限。
- pidfd 不移交亲子关系；原 wait status、poll 退出与树空分开。subreaper 仅用于
  已收养者的回收，不补原 seal。SCM_RIGHTS 排队 FD 必须有界处理。
- 补齐继承 FD、open/proc、外部 IPC 和 seccomp 入口边界；SO_PEERCRED 不能把
  预建 socketpair 的创建者误认成后来 S。S 固定可信代码的假设明确保留。
- C5 判据收敛到可观察的活生产者/真实后代，不承诺命中任意内核指令交错；
  缺前提即 INCONCLUSIVE。C3/C6 保留身份/控制缺证，cleanup 不改写历史。
- probe、辅助诊断输出、全部阶段限额、待上传证据保留、准确 D 和有限复验额度
  已固定。新 lab 的有限迭代没有套用原 Q2 单次消费，也没有改原批次。

| 需求 | 架构责任 | 阶段/病例 |
| --- | --- | --- |
| F01 | T 的 fixture/权限核对 | F1，UNSUPPORTED 不运行后续例 |
| F02–F03 | G→S→W 创建链及禁止外部转交 | F1/F2，C1/C2/C5 |
| F04–F05 | 不可逆关门、原 FD/身份与整树事实 | F2/F3，C2/C3/C4 |
| F06–F07 | 原双钟、有限收尾、T 独立收件 | F2/F3，C1/C4/C5/C6 |
| F08 | 分层报告、实验与现场采用分离 | F4，全部病例及未运行/未知结果 |

本轮验证仅为三文档链接、摘要、范围及源码机制的静态审查，没有编译新 helper、
运行新 workflow 或创建任何实验 fixture。因此没有新增测试 PASS、实际 fence
或已消费 lab 轮次；原 Q2 startup 仍 NOT ISSUED。

只有 Owner 对原 R、准确 A 与 F1–F4 明确关闭后，才另提交独立 bookkeeping C。
任何实现 D 必须以 C 为祖先；不得将 C 与实验 source/workflow 放在同一提交。
