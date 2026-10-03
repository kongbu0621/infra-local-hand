# Q2 namespace fixture delivery：部分实现与条件交付复核

2026-10-03 +08:00。本轮按 Owner 对
`LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1` 的准确决定先建立独立 CLOSED C，再形成
一个 fail-closed 的部分 implementation D。D 实现离线合同/shape 验证器、纯状态模型、standalone
reference protocol/synthetic harness 和 native bridge 的一组低层边界；它没有完成 A 的
完整 F0–F4 执行体，也不是可发行 bundle 或 field-ready 候选。

实际 F0 缺少私有 plan、sealed manifest、已安装 W 及其现场来源，结论为
**NOT_ISSUED**。本轮没有连接 guest、没有 SSH、没有 carrier request、没有
`BATCH_RELEASE`、没有 native batch/case，也没有收集或公开 raw machine evidence。

## 批准链与实现身份

| 层级 | 准确记录 |
| --- | --- |
| R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮直接读取固定 private source，规则 SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` |
| A | `ad5abaee642cba02d997149badf75a08c219a35c`；三份权威文档和设计复核保持 byte-identical |
| B | `LH-Q2-NAMESPACE-FIXTURE-DELIVERY-CLOSURE-20261003-01`；[Owner 决定](../governance/Q2_NAMESPACE_FIXTURE_DELIVERY_OWNER_DECISION.md) |
| C | `f5d60351c95c0276a95c7843215e02b0a69fdc3f`，独立 bookkeeping-only CLOSED 记录 |
| D | `5926dbe369e221775e32ae8164a571d1128e211f`，部分实现 |
| D tree | `1fd06ecfa7486a597844acce08e4b4b50b5c7453` |

Git 核验确认 D 的直接父提交就是 C。A 的四份文件 SHA-256 仍分别为：

- requirements：`e05a3f6e6d2717fddbb74412fecdb1c99b61624a2be4c896ce5f6b3f594c664c`；
- architecture：`6c297bc507495c875d9e0a62a1c1b3156b75e487027268fa8444c34132d34fa9`；
- implementation plan：`e6d7baedb61fca1726d3e37df9d3060dee052b61038c20cfe842aaa2553914d1`；
- design review：`4b2978866c0f7861d9604198e594c8aa7f425832b2e0d9875456fa4e9d421386`。

## D 中已实现的边界

### 离线 delivery contract

[`q2_namespace_delivery.py`](../../tools/q2_namespace_delivery.py) 对准确 R/A/C/B、固定
plan/manifest schema、身份对象、预算、W/bridge manifest、remote command、bundle/stage、
initial state、handoff、cleanup-final 和 224-byte native receipt 做 canonical/bounded
校验。它没有 filesystem、process、SSH、socket、cgroup 或 guest I/O，并拒绝：

- 在缺少私有输入时发行 carrier、release 或 native batch；
- 制造 durable capture ACK、success cleanup、success-looking handoff 或 success receipt；
- 推进任何 field state；
- 把外部 frame/handoff/cleanup/receipt 的结构匹配升级为 durability、native 或 live 证明。

无输入实跑的准确摘要是 `status=NOT_ISSUED`，blocker 为
`F0_PRIVATE_PLAN_ABSENT` 和 `F0_SEALED_MANIFEST_ABSENT`；所有三个 can-issue 位、
三个 issued 位均为 false，`batch_release_outcome=NOT_SENT`，
`fixture_qualification=NOT_RUN`。

### 纯模型与 standalone reference

[`q2_namespace_fixture.py`](../../tests/e3_host/q2_namespace_fixture.py) 实现固定计数、预算、
case/action/CPU/cgroup tree 状态模型。其 state/ledger 均固定
`modeled_only=true`、`durability_proven=false`、`live_proven=false`，并以 exact enum/bool
类型门禁止直接构造 `FIXTURE_LIVE_REFERENCE_MATCHED` 或 native PASS。模型中的 issued
位只表示模型动作，不是现场 durable issued 位，且没有流入 delivery field state 的入口。

[`q2_namespace_reference.py`](../../tests/e3_host/q2_namespace_reference.py) 实现 bounded parser、
固定 15-frame nonce/credential/SCM_RIGHTS 协议和匿名本机 synthetic harness。所有 socket、
child wait 和 fault path 都有固定 timeout；synthetic 正常链仍固定报告 `NOT_RUN`，不能证明真实
procfs/nsfs、cgroup membership、outer stop/EOF/seal 或 namespace qualification。

### native bridge primitive

[`q2_namespace_clone_bridge.c`](../../tests/e3_host/q2_namespace_clone_bridge.c) 提供固定
`clone3(CLONE_INTO_CGROUP|CLONE_PIDFD)`、credential/drop/exec、setup/arm 和 non-returning
224-byte receipt tail 的低层 primitive。测试绑定 flat 39-key ABI manifest、固定 receipt layout
和 SHA-256、signal/fdinfo/mask/rlimit 门、错误 FD 替换拒绝，以及 post-sample 无 allocation/loop/
`memcmp`/`memset` 的本地 call graph。

这不等于完整 L/S/owner 执行体。仍需外部 F2 source proof 证明 at-fork registry，无独立源码证据时
main-thread 条件仍依赖 caller proof；POSIX timer clock identity 仍是 caller-sealed；相同 mask 的新
signalfd 无法只靠 `fstat`/fdinfo 证明原 OFD 连续性，仍依赖 sealed single-thread caller 不变性。
真实 isolated cgroup 中的 clone 路径没有运行。

## F0–F4 准确状态

| 阶段 | 本轮准确状态 |
| --- | --- |
| F0 | **NOT_ISSUED**。只有合成 contract shape；没有真实 private plan/manifest、target、W、capacity、clock 或 capture 来源。 |
| F1 | **PARTIAL**。已有离线 validator、纯模型、standalone reference/synthetic 和 native primitive；缺 RAM bootstrap/guardian L、root S、owner durable capture/fsync ACK、HELLO/release、journals、真实 cgroup lifecycle、stop/三层 EOF、cleanup continuation 及整体编排。 |
| F2 | **NOT_READY / PARTIAL**。已有 D/source tests/build/ABI/schema checks；没有真实 bundle/context/runtime freeze、W/source-to-binary relation、完整 fault matrix、installed-chain 或 live harness qualification。 |
| F3 | **NOT_RUN**。carrier request 0，`BATCH_RELEASE` 0，native batch 0，native case 0；真实 `CLONE_INTO_CGROUP` sentinel 保持 skip。 |
| F4 | **NOT_RUN**。只有 H/cleanup/receipt 的 bounded shape 和本机 tail 验证；没有现场 wait/exit、空树、三层 EOF、final counters/peaks、费用、capture seal 或 Public acceptance result。 |

因此 D 不能称为 F0–F4 完成、可条件交付、artifact/field ready、真实 native PASS 或
`FIXTURE_LIVE_REFERENCE_MATCHED`。A 中的一次 carrier request、最多一次
`BATCH_RELEASE` 和最多十二个 native case 的授权仍全部未消费。

## 验证结果

| 验证 | 准确结果 |
| --- | --- |
| 四个 namespace 模块，`-W error` | **119 PASS / 8 SKIP** |
| 加 workflow hardening 回归，`-W error` | **148 PASS / 8 SKIP** |
| 沙箱外仅本机 AF_UNIX/SCM reference 回归 | **22 PASS** |
| native bridge 子集 | **12 PASS / 1 SKIP** |
| 精确文件 `compileall` | PASS |
| `git diff --check` / staged check | PASS |
| 已实现 primitive/native bridge 边界的两次独立只读代码审计 | 未发现剩余可复现 HIGH/MEDIUM；总体 coverage audit 同时确认上表实施缺口，不构成 F2/live qualification |

这些是本轮本机命令结果和 source review 结论，不是 field evidence，也没有作为 raw machine
evidence 发布。

八项 skip 被准确保留：五项 sandbox credential transport、一项 sandbox `SO_PASSCRED`、
一项未提供 explicit native fixture、一项未提供 isolated root cgroup fixture。沙箱外 reference
回归消除了前六项环境 skip，但仍只验证匿名本机 synthetic transport，qualification 继续为
`NOT_RUN`。

D 形成前的首轮全库诊断结果为 **3449 PASS / 110 SKIP / 264 FAIL / 127 ERROR**
（407.41s）；其中观察到当前环境缺少既有 protected ancestry、ordinary/systemd fixture 等
前置条件及级联现象，但本轮没有逐项归因全部 391 个 FAIL/ERROR。该非零结果被保留为 FAIL，
没有改写为 PASS，也不能作为准确 D 的全库证明；最终 D 只主张上表中的定向结果。

九项 D 文件的 SHA-256 为：

| 文件 | SHA-256 |
| --- | --- |
| `tests/e3_host/q2_namespace_clone_bridge.c` | `70066e5832e9b37dbb30be30defdf2fc914e090a462646b543b1736fe01ffaf1` |
| `tests/e3_host/q2_namespace_fixture.py` | `be515cfd5291f245f41a16026027503c6b3b945146d360c1275146c5a4ba5221` |
| `tests/e3_host/q2_namespace_reference.py` | `409457aeb7336ac15ad94e137d44a53f0fd70d1540339aa3e238bd31989d24bb` |
| `tools/q2_namespace_delivery.py` | `7f28cef1012fb8522565176486f59e6127940bce455b35e62250682b04001fbd` |
| `tests/test_e3_q2_namespace_clone_bridge.py` | `4cdad9a2c15b3e00ea08708035d13d9abea40656bad2afbb3fd3622b5cd39d0d` |
| `tests/test_e3_q2_namespace_delivery.py` | `c2d61f3f494df7815bae6cc461ee346a25cfd091f57c075ed7ed0a98df1230e2` |
| `tests/test_e3_q2_namespace_fixture.py` | `9f6c710b0f1b54096b321be96b3322b4a2d584f2cd919fbb5aa4f34be941aeef` |
| `tests/test_e3_q2_namespace_reference.py` | `1c82bdc24f3f94b4f0888431168e1d7c90768921e223f4997870502f16ec535d` |
| `.github/workflows/local-hand-v0-1-validation.yml` | `d38cfd5904853c9100f228e5a1096ad4d1ea3d2105545086eb5a2b591a806de8` |

## 条件交付结论

当前没有可安全发行的 bundle，也没有 A 所需的真实 pre-request inputs；因此条件交付在首次
carrier request 之前停止，状态为 **NOT_ISSUED / NOT_RUN**。后续继续实施必须仍以 D/C/A/R 为
祖先和边界，补齐完整执行体、真实 private bindings、全 fault/source/native qualification 和
bundle freeze 后重新执行 F0。只有当 A 的全部门实际成立时，才可消费同一授权的一次 request；
当前文档、D、synthetic PASS、native local PASS 或 Owner B 均不能替代这些现场证据。

用户工作区中既有未跟踪 `.codex` 未修改、未暂存，也不属于 D 或本复核。
