# H07 第二轮：原件复核与停止记录

2026-09-30。第二轮已完成并保留失败，**H07 未取得实验资格**。总额度已用
**2/3**，第三轮为 **BLOCKED / NOT_DISPATCHED**。本记录落实既有 U4 证据登记，
不改变原 A、新 A、Owner 决定或停止规则，不签发原 Q2 startup。

## 准确来源与普通 CI

本轮准确执行提交是 `9d8328cf742fa130c265de23b1b9085b9e8a0581`，tree
`69f378cf28b0a4364e3ee1615a5dbcb2a3c9e0aa`。它沿新 CLOSED C
`7d33c698ff6c1bf34733ee2429d0404ace2abd55` 下降；相对已经验证的 D
`d4dd8c6e` 只更新文档和证据登记，实验源码和 workflow 字节未改变。

派发前对该准确 HEAD 完成普通 CI
[36655111148](https://github.com/kongbu0621/infra-local-hand/actions/runs/36655111148)，
`workflow_dispatch` / attempt 1，三个 job 全部 SUCCESS。Linux 源码
3063 PASS / 51 SKIP，真实 root collector 16 PASS，installed 94 checks /
292 commands；Windows 源码 996 PASS / 996 SKIP，installed 10 checks /
10 commands。见[准确 CI 登记](evidence/q2-h07-cgroup-fence-spike/round-2-ordinary-ci.json)。
普通 CI 不消费实验额度，也不证明内核现场资格。

## 本轮结果

[实验 run 36662298613](https://github.com/kongbu0621/infra-local-hand/actions/runs/36662298613)
为 round 2 / attempt 1，准确提交同上。2026-09-30 10:58:44–10:58:52 +08
执行 `bounded-experiment`。源码准入 SUCCESS，fixture 退出 3，原件上传 SUCCESS。
实际环境记录为标准 hosted Ubuntu 24.04 x64，kernel `6.17.0-1022-azure`。

| 层次 | 保留结果 |
| --- | --- |
| 账户 | 创建退出 0，四次观察完整；独立账户校验无错误，删除退出 0 |
| 能力探针 | 原件存在；准确收件器派生 `supported=true`，无错误 |
| C1 | 实际执行，但预期未满足；派生 `UNKNOWN_RETAINED`、`fence_observed=false` |
| C2–C6 | NOT_RUN；在 C1 非预期缺证后停止，未补造回执 |
| 本轮登记对象清理 | 7 项移除有据，`cleanup.verified=true`，`residuals=[]` |
| 原始报告 | schema 2，`UNKNOWN_RETAINED` |
| 整份报告收件 | CLI 退出 2，派生 `REJECTED`，存在身份绑定校验错误 |

原报告 reason 保持为 `final report verification: C1: launcher/account binding missing`。
C1 单独派生还报告 `guardian summary contradicts retained independent facts`。
原件虽存在 `fenced` 事件，不能越过独立判据认定 fence 通过。整份收件器的
`REJECTED` 是拒绝不完整报告，**不是第三轮准入所要求的无错误 REJECTED**，也不改写
原报告 `UNKNOWN_RETAINED`。清理有据仅覆盖本轮登记对象，不代表整个 OS 回滚，
更不补齐首轮的历史清理未知。

## 失败位置与根因置信边界

C1 原事件先记录 `s_created`，约 2.075 ms 后记录原启动器 S 的
`s_exit=-9`（SIGKILL）；随后才有 `close_requested` 和已登记的 `b_kill`。
没有 `s_armed`、`s_credentials`、`request_sent` 或 worker 事件。
因此账户创建成功并没有转化为启动器身份验收成功，固定工作负载尚未得到完整证据。
`run_fixture.py` 的最终报告校验将早先 C1 预期未满足的说明替换为上述绑定错误；
原件与本记录分别保留观察事实和派生结论。

源码对照发现一个高度吻合的上游已确认缺陷：Linux 官方修复
[`8e359920216689b3b79e0fe8961a77fe312a511f`](https://github.com/torvalds/linux/commit/8e359920216689b3b79e0fe8961a77fe312a511f)
修正 `CLONE_INTO_CGROUP` 在父组和目标组 `kill_seq` 不同时错误终止新子进程的问题。
本 fixture 的 probe 对 B 子树执行 `cgroup.kill`，随后复用该树，从 G 向 B/S
克隆 C1 启动器；这一顺序与该缺陷描述相符。

这仍是**源码和事件吻合的根因候选**。目前没有取得本 runner 准确 Azure 内核
构建的完整补丁集合，也没有原内核发信来源记录，不能仅凭版本名断言该构建缺少修复。
不将普通 CI 通过、探针单独通过或某个补丁发布日期转换成该内核修复状态的证明。
后续只读核对准确内核修复状态、非特权离线推演或保持原合同的局部修复均不得
改写本轮原件或解除实际实验停止。

另已反查 guardian 内未单独留事件的 K_ARMED 拒绝分支：该分支会不可逆设置
`closed=true`、`close_reason=91`，而本轮随后保留的 `close_requested` 仅由
`!closed` 分支产生，且最终 `fenced=1` / G 退出 0。因此在准确源码和完整保留事件
成立的前提下，该分支不能解释本轮完整轨迹。不能仅凭时间先后排除任意发信来源。

后续方案应同时处理：准确内核修复状态或逐例有界 cgroup 生命周期；启动器提前
退出及拒绝路径的明确诊断事件；首个失败原因与后续收件错误分列。仅在 probe 后
重建一次仍不能覆盖各 case 杀树后的复用。生命周期调整须连同来源/对象绑定、
资源观测、清理账本和原预算一并论证，不能退回先启动再迁移或放宽身份校验。
本轮只记录这些方向，未更改 helper、fixture、判据或执行环境。

## 原件与独立核验

原 artifact `11074538056`，ZIP 13,719 bytes，SHA-256：

```text
21c2c19d081adb1a89d8b9f2ad62297d86761f88947842705554db70e3c66373
```

原 report 36,612 bytes，SHA-256：

```text
99d6def38ae46a417a1cfc25b0e6588028813bc0d3b27cee60b083929ad99a54
```

五个 ZIP 成员的 CRC 和原件字节核对通过；manifest 四个所列成员的长度与 SHA-256
全部匹配。report/manifest 的 source/run 一致，22 项来源摘要逐一与准确执行提交的
Git blob 匹配，probe/C1 文件与报告内嵌对象一致。独立使用该准确提交的真实收件器，
同时分开核验 capability、C1、账户、预算及清理。复核未执行 live fixture，未改变原件。

公开仓库只登记[脱敏复核和各原件摘要](evidence/q2-h07-cgroup-fence-spike/round-2-verification.json)，
完整 ZIP 另行原样保留，不把原机器产物或原 job 日志复制到公开仓库。
GitHub artifact 原到期时间为 2026-10-30T02:58:49Z，已单独保留原包。

## 停止依据与后续边界

实时读取全部 75/75 条 Actions 记录，H07 仅首轮 `36577764454` 和第二轮
`36662298613`，两者均 attempt 1。失败同样消费轮次，剩余 1/3 不是派发许可。

- 原[实施计划](q2-h07-cgroup-fence-spike/IMPLEMENTATION_PLAN.md)规定非预期
  UNKNOWN 或清理未证阻断后续轮次；仅固定 C3/C6 预期缺证且清理已证例外。本轮 C1 不属例外。
- 新[续验要求](q2-h07-r1-continuation/REQUIREMENTS.md)仅接受首轮
  `36577764454` 的指定历史未知，不抵消第二轮新增 UNKNOWN。
- 新[续验计划](q2-h07-r1-continuation/IMPLEMENTATION_PLAN.md)要求第二轮无新增
  阻断、另有明确源码缺陷及准确修复验证，才能讨论第三轮；当前不满足。

因此不 Re-run、不再次派发 round 2、不启动 round 3、不更换通道或借剩余额度试探。
现有只读诊断和原合同内离线工作可继续；若要新增历史未知接受、改变身份/收件判据
或恢复实际派发，须先形成准确受影响方案 A、取得 Owner 明确 B，再独立记录 C。
普通修复和 CI 成功不能替代这一过程。本记录不请求新的授权，也不预设其结论。

首轮原 `UNKNOWN_RETAINED / cleanup=false` 永久保留；本轮按停止条件完成留证，
不把 U4 留证完成称作 H07 资格完成。原 Q2 startup 仍 **NOT_ISSUED**，完整 Q2/E3、
真实远程链、FS 和完整计费均未因此验收。
