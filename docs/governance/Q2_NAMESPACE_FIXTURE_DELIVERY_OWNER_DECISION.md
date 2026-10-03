# Q2 namespace fixture 完整交付：Owner 决定

- Decision Authority / Owner：当前项目 Owner（本工作会话用户）。
- 决定记录时间：2026-10-03 09:32:57 +08:00（紧随准确用户回复取得的本机时间）。
- 本地可追溯事件：`LH-Q2-NAMESPACE-FIXTURE-DELIVERY-CLOSURE-20261003-01`；
  不是平台消息 ID。
- 稳定来源：本文件保留本次准确 Owner 回复，供 Owner 核验。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本次 executor 已直接读取
  private companion source 的该固定 commit，规则内容 SHA-256 为
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`，与本地采用记录匹配。
- Documentation A：`ad5abaee642cba02d997149badf75a08c219a35c`。
- Scope：`LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1`，**F0–F4 only**。

## Owner 准确回复 B

> 按原 R 10d2a5c827964989f41ca6e8eeac3d44de6d0f04，批准 A ad5abaee642cba02d997149badf75a08c219a35c 的 LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1，范围为 F0–F4 only；接受 A 中的唯一新事实前提、对象、预算及一次 carrier request、最多一次 BATCH_RELEASE、最多十二个 native case 的边界；继续建立独立 CLOSED C，并按 A 实施、验证和条件交付。

## 决定边界

本 B 明确绑定上述 R、准确 A 和 F0–F4。Owner 接受 A 中唯一新增的
`fixture endpoint execution integrity` 事实前提，以及 A 所定义的完整对象、费用、资源、时间、
状态、停止、EOF、收件和保留边界；该前提不接受 original-terminal provenance，也不替代任何
live identity、ABI、clock、cgroup、capacity、exit、EOF 或 accounting 证据。

本 B 授权在独立 C 后按 A 完成离线绑定、source/test 与 test-only fixture 实现、synthetic/native
条件验证、准确 D 与 bundle/plan 冻结、一次条件 carrier request、最多一次 `BATCH_RELEASE`、
同一 batch 内顺序执行最多十二个唯一 native case，以及 F4 收件、账目和脱敏发布。A 的硬门、
单调 issued 位、无重发规则、最多一次 batch 和全部失败保留语义不变；Owner 不需要为 A 内每个
文件、对象或 case 再作逐项批准。

只有 A 的全部 pre-request 与 live admission 条件实际成立时才能交付。缺少既有且准确资格化的
sealed native watchdog W、固定来源、预算、身份或其它静态输入时，状态保持 `NOT_ISSUED`；请求一旦
发出即永久消费唯一 delivery，任何拒绝、断线、BLOCKED 或 UNKNOWN 都不产生第二次 carrier request、
第二次 `BATCH_RELEASE` 或第二个 native batch。条件交付不是对当前 guest readiness、field readiness、
P4、consumer、normal chain、production、GX10、S1、S2 或 E4–E6 的事实断言或额外授权。

旧 `LH-Q2-NAMESPACE-REFERENCE-v1` proposed A 保持
`SUPERSEDED_PROPOSAL_NOT_APPROVED`；其原字节、只读 readiness 审计和未批准历史均不改变。
本文件与根 `AGENTS.md` 的 CLOSED 登记共同构成独立 bookkeeping-only C。A 的三份权威文档、
设计复核、历史 OPEN 标签及提案登记保持字节不变。后续 implementation D 必须以本 C 为祖先。
本 C 不包含 production/test source、可执行 prototype、dependency、runtime configuration、bundle、
private delivery 或现场动作，也不消费 carrier request、`BATCH_RELEASE` 或 native case。
