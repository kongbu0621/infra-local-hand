# QI1 准确冻结及 QI2 单次现场返回

`LH-Q2-CORE-Q1-BINDING-CONTINUATION-v1` 的 QI1 已完成；唯一 QI2 窗口
`lhqjgrow-20261008e` 已消费并停止。journal 尚未完成扩容，QI3 的
H01→Q4→H11 均为 NOT_RUN，没有发行真实核心包。

## 授权链与准确候选

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，本轮读取固定直接来源原字节，
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`e66b1b5524f22d60c810dffac59ca418c5ad4236`，三份文档字节保持不变。
- [准确 Owner 决定 B](../governance/Q2_CORE_Q1_BINDING_CONTINUATION_OWNER_DECISION.md)，
  event `LH-Q2-CORE-Q1-BINDING-CONTINUATION-CLOSURE-20261008-01`。
- 独立 C：`61fae1da528105605a023f260130c4e0d9c1bc02`，仅关闭记账。
- 实现 D：`fa30146b0a49744b25df0f23969bf96b17eaacad`，直接承接 C；tree
  `1d40608ae0f43d63608a80163cb667d595267c06`。D 已发布至 main，本记录是后续证据，
  不更换实际冻结或现场执行的 D。

来源采用及实现范围见 [QI1 实现记录](Q2_CORE_Q1_BINDING_IMPLEMENTATION_REVIEW_20261008.md)。
固定原件和此前私有索引关系重新核对后冻结；没有执行 exporter、单元补查或全宿主扫描。
当前 Q1 捕获、声明细节及新 08e 原件/索引仍私有；仅原先获准的
[旧08d五件最小索引](Q2_CORE_GUEST_STARTUP_ORIGINALS_INDEX_20261008.md)公开。

## 验证与冻结

[准确 D 的首次 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37798495015)
三项全部成功，没有重试：Linux 7250 通过、89 跳过；Windows 1809 通过、1354 跳过。
Linux CI 独立安装 94 检查、292 命令通过；Windows 平台安装 10 检查、10 命令通过。
本地另从准确 D 的独立 worktree 构建并安装，94 检查、292 命令通过；现场已有安装未改。
跳过项目不计为通过。早期本地失败与针对性复核保留在实现记录及私有日志中。

准确 D 的真实保留输入核对通过：16 输入角色、20 件历史核心原件、4 件诊断、
4 件容量原件、35 件旧维护原件。所有七个旧窗口继续消耗，不释放八代累计维护费用。

| 冻结前离线量值 | 字节 | 原上限 |
| --- | ---: | ---: |
| host / guest 维护源码 | 80810 / 63103 | 各 98304 |
| 压缩 / 展开 bundle | 39890 / 137104 | 49152 / 393216 |
| 保留形状 pre descriptor | 26337 | 65536 |
| 静态 marker 形状 | 61113 | 65536 |
| 最大计量与 20 位钟的短预检 | 708 | 4096 |
| 完整合成成功的 transition | 12573 | 65536 |
| 七旧历史与合成成功的核心输入 | 387985 | 1048576 |
| 静态成员加原输入/manifest 预算的包上界 | 19608501 | 33550320 |

最后三项使用真实静态来源和历史、合成的维护成功投影；没有在维护前构造真实核心包，
也不把合成成功视为现场通过。维护 caller、条件核心 caller、静态来源 reader 及
成功原件校验程序均在现场前固定。冻结记录 SHA-256：
`daae7c46214e4404abe2b2d60d9c4120639264ac04119957ef07d59a65610b13`。

## 单次返回及保留边界

普通本地预检为 LOCAL_PREFLIGHT_PASSED；同一原点、nonce、manifest 和原计量下
执行一次。实际 manifest 含获准的 Q1 服务及父域，清单数量为 19/7/7。
原身份、启动边、静止、cgroup、数据和容量检查保留。

实际结果为 STOP_AND_RETAIN / `GROWTH_REPORT_MISSING`，退出码 3，marker 已创建，
SSH 请求 1 次。原 guest stderr 给出 PRE_QUIESCENCE / INCOMPLETE /
`GROWTH_UNDECLARED_BUSINESS_UNIT`：另一服务的 ExecStart 命中受保护路径检查，
与本次固定采用的 Q1 服务不同。该错误说明本次静止准入失败；现有返回不证明该另一
服务的完整身份、应采用来源或应有的声明范围，不能直接追加到本次批准的唯一增量中。

原事件没有 POWER_OFF_TOKEN，guest actions_started 为 []，状态只启动了 CONSUMED
与 GUEST_QUIET。没有开始关机、备份、扩容、重启或核心任务；remote_exit 仍为 UNKNOWN。
这不把进程退出码或已返回的诊断提升为远端完整收尾证明。

仅保护读取并私有保留此次已产生的 consumed、events、pre stdout、pre stderr 和 receipt
五件原件；核对 manifest、两流长度/摘要及 receipt 与调用者返回一致。原冻结记录保留，
另记录 release gate 为 STOP_AND_RETAIN / CONSUMED_FAILED，QI3 为 NOT_RUN。
没有重试、补采、清理、恢复、回滚或支线开发；不得重放 08e 或条件核心 caller。
