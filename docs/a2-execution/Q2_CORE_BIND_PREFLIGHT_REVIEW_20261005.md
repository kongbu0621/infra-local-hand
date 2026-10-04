# 核心 BIND 交接的发行前修复

2026-10-05 +08:00。基于 main `3902ce51d33c736a44a26013d239e6f5cbe996bc`，
只修正既有 CLOSED 核心实现；原 F1 已消费，新现场执行尚未授权。

## 已核实状态

本地修复 D `a6638424c5de2ea59f39cf6e24f07b06040d0884` 的
[CI 37220038272](https://github.com/kongbu0621/infra-local-hand/actions/runs/37220038272)
已三项全部 completed/success。它修复真实 F1 在 BIND 前遗漏 writer 的接线错误。
该 CI 不改变 [原单次失败记录](Q2_CORE_SINGLE_F1_RESULT_20261005.md)：
真实 HELLO 有效、BIND/package 发送为零，旧远端退出和完整资源使用量仍 UNKNOWN。

## 本轮确定缺陷与修复

原需求要求单一 package basename。host 的 `build_bind`/`deliver_once` 却允许
`sub/frozen.lhfp`，standalone bootstrap 的原校验只接受
`[A-Za-z0-9._-]+\.lhfp`。纯函数复现为 host 接受、guest 拒绝
`CORE_BOOTSTRAP_BIND_PACKAGE`；这不是已经观察到的另一次现场失败。

host contract 现在复用统一的 basename 校验，匹配 guest 既有要求。
`deliver_once` 在读取管理入口、创建 marker 和发 carrier 之前拒绝不兼容名称。
field 三份源码、wire 版本/字段、冻结 runtime candidate/wheel、身份校验、预算和时限均不变。
release allowlist 仍为空；没有新 marker、连接或现场执行。

新回归以真实 package builder/parser 产生的 entry 贯穿 host BIND、guest BIND 及
marker 规范字节回构，不再手写一个可能漏字段的 entry。
私有源内容和 HELLO 仍是明确测试样本，不代表实际 guest 观察。
另外覆盖九类不兼容名称，在 host 先拒绝且不进入管理/消费/请求动作。

新回归与 entry/bootstrap/writer transport 首轮 **159 passed**；
补入 contract/freezer 后六组 **232 passed / 7.99s**。未重复完整源码测试，
完整 CI 由准确发布提交触发。当前未发现第二个明确的 writer 字段遗漏，
不据此宣称整个实机链已通过。

## 后续核心动作

继续验收须保留旧五文件与消费状态、未知退出/资源义务；不能以此次修复消除旧 marker。
依据原 R 与 AGENTS 的已消费 F1 声明，先形成新准确批次的三层文档，
明确一次请求、新旧身份隔离、旧进程当前状态核对和未释放容量，再请求 Owner 对准确 A 决定。
不重复批准既有代码修复，不另开 namespace/watchdog、NAS 或 production 工作。
