# SY1 准确冻结与 SY2 单次返回

**SY1 完成；SY2 已消费且失败；SY3/H01/Q4/H11 未执行。**

范围 `LH-Q2-CORE-SYSTEMCTL-CONTINUATION-v1`，原 R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，准确 A
`62666eeec9f2f28833876df3d68ce6e8b8e0af54`，独立 C
`7b342ced547639f93797e849b34ed3da4915c8d3`。准确 Owner B 与三文档原字节保持。
本记录仅登记事实，不授权另一窗口，不改冻结源码。

## 准确候选与验证

最终执行 D `b2bc054d0c06526b454cd320f167cc1a40242ab8`，tree
`3a32904736b844564bff5639eb98e3622bb32525`，已发布 main 并在执行前冻结。
实现和保留的开发验证情况见 [SY1 审查](Q2_CORE_SYSTEMCTL_CONTINUATION_REVIEW_20261007.md)。
冻结 dispatcher SHA-256为
`5a824dd169e73d3b35eb7307a6ae16920075c63c72338c8af09ecf5ea8608dc2`。

[准确 D 首次 CI 37644250925](https://github.com/kongbu0621/infra-local-hand/actions/runs/37644250925)
三 job 全部 success，run_attempt=1，没有重跑。Linux 源码 **6334 passed / 89 skipped**；
隔离 root 文件检查 **16 passed**；CI 独立安装 **PASS / 94 checks / 292 commands**。
本机准确 detached 源码构建的新独立 venv 同样 **PASS / 94 checks / 292 commands**，
安装报告及 wheel 来源均为上述 D。

本地受影响组的环境失败和修正记录保留；原路径保护未减弱。最后预检顶层R/A/C修正组
300 passed。既有八输入、四个旧核心批、诊断与容量原件、两代维护十件原件完成保护
读取及关系核对。静态源码成员和历史来源检查通过；固定runtime/wheel/projection/loader
不变。静态归档不含的cloud-config由已有固定本机user-data按原pin核验；不合成或补采。
SY1未观察VM、发起SSH、执行维护预检或构建真实核心包。
私有冻结、准确CI回执、构建/安装报告、离线检查和两段caller均已保留。

## 唯一现场结果

`lhqjgrow-20261007b` 普通预检一次通过；以相同原点、nonce、manifest、累计用量
交接execute。实际结果为：

- `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，退出码3；marker已创建，SSH请求1。
- 开始的状态仅 `CONSUMED` 和 `GUEST_QUIET`；business_cases=0。
- 本次已有guest stderr记录 `INCOMPLETE / PRE_QUIESCENCE / GROWTH_SYSTEMCTL_STDERR`，
  `actions_started=[]`。同次命令上下文确认systemctl show退出1、双流EOF完整且stderr非空；
  保留的错误说明它拒绝了一个未实例化模板单元操作数。没有为定位发起第二次查询。
- 原事件没有 `POWER_OFF_TOKEN`。本次未发关机、备份、镜像/文件系统增长或VM重启动作。
  journal扩容未完成。
- receipt的remote_exit仍为UNKNOWN。systemctl子命令退出1不等同于完整远端监督退出证明。

只保护读取并私有保留本次已经产生的五件原件，与既有调用方输出、manifest和流摘要
交叉核对。本次新原件及其最小索引继续私有；仅旧07a索引已获明确公开许可。
没有补采、重连、清理、恢复或重试。这个结果不证明systemctl问题已经全部修复。

SY2窗口保持 **CONSUMED / FAILED**，旧06a和07a消费、原件、完整费用及UNKNOWN全部保留。
SY3条件未成立，原 `lhqcore-20261007a` 与 H01→Q4→H11 全部 **NOT_RUN**；没有生成或发送
真实核心包。调用方gate已终止为 `SY2_CONSUMED_FAILED_SY3_NOT_RUN`，冻结原件保持不变。
不得重放本次任一caller或用尚未执行的条件核心批绕过失败维护。
