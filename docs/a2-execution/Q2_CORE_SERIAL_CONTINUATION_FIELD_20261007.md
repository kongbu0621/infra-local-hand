# SC1 准确冻结与 SC2 首次返回

**SC1 完成；SC2 单次窗口已消耗且失败；SC3/H01/Q4/H11 未执行。**

范围 `LH-Q2-CORE-SERIAL-CONTINUATION-v1`，R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，准确 A
`7869bbcaeb1dad3a1736131a3ff2e225ddf5e7cc`，独立 C
`91c706b52dbc70498d5d872f59874c002cef23db`。准确 Owner B 及三文档原字节保持。
本记录只登记事实，不批准另一窗口、不改变冻结源码或原授权边界。

## 准确候选与验证

最终执行 D `a20bf2a4575df7578341af744630ceaac131a6a7`，tree
`74665885ddee8a50abf2ad545081820221b67084`，已发布 main 并在执行前冻结。
初始实现及 held-FD 修正见[SC1 审查](Q2_CORE_SERIAL_CONTINUATION_REVIEW_20261007.md)。
准确 dispatcher SHA-256
`bfa38a11b5b277c41c3ef0091e86a9a01462bed748baf0321ce7679cd63047af`。

[准确 D 的首次 CI 37630854001](https://github.com/kongbu0621/infra-local-hand/actions/runs/37630854001)
三 job 全部 success，无重跑。Linux 源码 **6213 passed / 89 skipped**；隔离 root-only
collector **16 passed**；CI 独立安装 **PASS / 94 checks / 292 commands**。
本机准确 detached 源码副本构建的新独立 venv 也为 **PASS / 94 checks / 292 commands**。
受影响开发树 2179 passed / 35 skipped，加 held-FD 修正组123 passed 的来源和范围见审查。

既有八输入、四旧核心批、诊断原件以及旧维护五原件完成保护读取和来源核对。
静态成员和历史来源检查通过，原 runtime/wheel/projection/loader 保持固定。
SC1 未观察 VM、发起 SSH 或执行维护预检；未生成可现场执行的核心包。
私有冻结、准确 CI 回执、构建/安装报告、离线检查与两段调用方留在本机。

## 唯一现场结果

新维护 session `lhqjgrow-20261007a` 仅执行一次普通预检；预检通过后，以相同
原点、nonce、manifest、累计用量交接进入 execute。实际返回：

- `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，退出码3；新 marker 已创建。
- 固定 SSH 请求1，business_cases 0；开始的状态仅 `CONSUMED`、`GUEST_QUIET`。
- 本次已捕获 guest stderr：`INCOMPLETE / PRE_QUIESCENCE / GROWTH_SYSTEMCTL_STDERR`，
  `actions_started=[]`。按准确源码阶段顺序，本次已经通过序列号检查。
- 事件原件没有 `POWER_OFF_TOKEN`。没有发起关机、备份、镜像增长、VM重启或ext4增长。
  journal 扩容未完成。
- receipt 的 remote exit 仍是 `UNKNOWN`；不推断独立退出证明。

该错误门同时要求 systemctl 返回码0、双流 EOF 和空 stderr。已捕获失败记录未保存
具体哪个条件失败或对应命令，因此这里只登记准确错误门，不声称已查明更底层原因。
只读取和保留本次已经捕获的五件原件；没有补采、重连或额外现场查询。
新原件的长度、摘要及绑定保存在私有索引中，不在此公开原文或新派生机器元数据。

SC2 窗口维持 **CONSUMED / FAILED**；旧06a消费及原件继续保留，不退款或重置计量。
SC3 条件不成立，`lhqcore-20261007a` 及 H01→Q4→H11 全部 **NOT_RUN**。
未生成或发送真实核心包，未清理、恢复、重试或执行支线。
调用方状态已登记为终止；两段旧交接均不能在本次已消费授权下重放。
