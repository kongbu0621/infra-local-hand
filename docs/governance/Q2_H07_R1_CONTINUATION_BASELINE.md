# H07 首轮历史异常限定续验：准确方案基线

2026-09-29 +08。状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。

- Scope：`LH-Q2-H07-R1-CONTINUATION-v1`，仅 U1–U4。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 直接规则：engineering-sop 固定 R 的 `docs/workflow/program-repository-documentation-gate.md`；SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；采用、Owner Authority、无例外和变更规则沿用 AGENTS。
- 准确新 A：`a08a5055c35009a896ad6c6059d709758cc78436`。
- A tree：`14e4384e07bf8c157975467de7e645a5c5c7496a`。
- A parent / 已验证修复：`9596c784932dc8990e0225e0f46bf292d7e7b3ea`。
- 旧 A：`71c7e842c724650a0e949a63bb898699b41107be`；旧 C：`8deeed492edeb7e5fa79cbe95c123a27e69f9f92`。
- 新 Owner closure B：**尚无**；新独立 CLOSED C：**尚无**；本变更实现 D：**尚无**。

本记录只固定既有 A，不是 C，不授权新实现或第二轮 dispatch。此前“按照建议继续”
用于完成方案与审查，不被记为对当时尚未生成 A 的 closure。

| authoritative document | bytes | SHA-256 |
| --- | ---: | --- |
| [需求](../a2-execution/q2-h07-r1-continuation/REQUIREMENTS.md) | 6341 | `74ad594f4446cdf49c4b8d72ff4e5ffb3bd411780e91eeee5a130e58d03eb7f2` |
| [架构](../a2-execution/q2-h07-r1-continuation/ARCHITECTURE.md) | 10409 | `18a248d9398f73405e8836a9586e9c98b8ed9aab2c71242ecdc1c8eaa3823e2b` |
| [实施方案](../a2-execution/q2-h07-r1-continuation/IMPLEMENTATION_PLAN.md) | 9233 | `9c5726f80f4cb779f658b4d075ee50568ff9818b9f49814e57de71c07aedbe2b` |

## 需要作出的具体决定

首轮 run `36577764454` / attempt 1 / round 1 / 源码
`6b085d9ceb536b9785ea683cd108e92cd8a4eec4` / artifact `11038133434`
保留 `UNKNOWN_RETAINED / cleanup=false`，probe/C1–C6 未运行，已消费 1/3。
[原件身份与摘要](../a2-execution/evidence/q2-h07-cgroup-fence-spike/round-1-verification.json)
不修改，不把参数修复或普通 CI 成功当作补齐清理。

拟接受的是：**该唯一首轮历史未知，在新准入条件成立时，不再单独阻断剩余最多
两轮；历史失败和未知不消除，任何后续新异常仍受原停止条件约束。**
不是接受所有账户残留或无限重复，也不重置实验额度。

准入依赖标准 GitHub-hosted ubuntu-24.04 x64 的新 VM 设施约定和逐轮实际身份检查；
新 boot 不足以单独证明新 VM，也没有原 VM 销毁证明。该设施信任和历史残留未知
是明示的剩余风险。NSS systemd 点查内部工作仍属可信托管 OS，未被宣称完整封闭。
这些依据不替代原轮次或本轮任务清理事实。

配套 U2 明确有界账户观察、observed/admitted 身份分离、未知身份不删除、
严格报告 schema 2 与旧原件兼容；U3/U4 保持原六例、限额、只手动派发及完整取证。
第3轮仍须有新的明确源码修复理由；第2轮资格满足即结束，不要求花完额度。

仅按新需求“唯一受影响的原合同”的 supersede 表调整旧实施方案两处清理未知的
跨轮适用；原 R、旧 A 原文、轮内清理、未来异常、生产和原 Q2 排除项全部保持。

## 审查与已完成验证

- 已完成独立治理/语义、技术/可实施性两路静态审查，具体修订见新实施方案末节。
- 已核对三层相对链接、摘要和纯文档提交边界；A 的8项变化均为文档/结果索引。
- 新观察逻辑、schema 2、workflow 准入尚未实现，也未在 cloud 创建账户或运行实验。
- 修复 `9596c784` 的[普通 CI 最终清单](../a2-execution/evidence/q2-h07-cgroup-fence-spike/round-1-repair-ci.json)
  记录3/3成功，不能转为新实现通过。
- 实验运行历史目前只有首轮一次；本 A 和本登记不消费实验额度。

## 待决定语句（不是已发生的 Owner 决定）

> 按原 R，批准 A a08a5055 的 H07 首轮限定续验方案，关闭 U1–U4 范围 Gate；接受首轮清理未知仅不阻断剩余最多两轮，保留原失败及后续停止条件，继续实施。

Owner 若作出准确决定，另记录 B 原文/身份/时间或事件，单独提交 bookkeeping C，
再从 C 实现和验证 D。不得把本 A、C 与实现合并或通过改写历史伪造先后。

