# GS1 准确冻结与 GS2 单次返回

**GS1 完成；GS2 已消费且失败；GS3 / H01 / Q4 / H11 未执行。journal 扩容未完成。**

范围 `LH-Q2-CORE-GUEST-STARTUP-CONTINUATION-v1`，原 R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，准确 A
`7ea9aed6a4f8be6d6fee0ee549e1e02378f32672`，独立 C
`001bd4f7baedf115ce67feba87a21d8e259c8d1d`。
[准确 Owner B](../governance/Q2_CORE_GUEST_STARTUP_CONTINUATION_OWNER_DECISION.md)
明确接受并确认 guest 管理前提及覆盖缩减，先于实现登记；C 仅含 B 和 CLOSED 记录。
A 三文档字节和历史 OPEN 标签保持。本记录不修改授权、源码或执行次数。

## 准确候选与首次失败保留

最终执行 D 为 `341796561a6aaa6f95779f438b57d958a1fd5954`，tree
`13055498cc1155817c29ef09462f19aed870b6cd`，经首个实现 `1086aa1` 承接独立 C，
已发布 main 并在 GS2 前冻结。dispatcher SHA-256 保持
`a8306815b71fef841d94d3ed8117a76644c9b262c631673d4c17242dbb2543cc`。

[实现审查](Q2_CORE_GUEST_STARTUP_CONTINUATION_REVIEW_20261008.md)保留两轮本地失败及
定向修正结果。首个候选 `1086aa15f2e74ee6012c6ee0d40876742ff90990` 的
[首次 CI 37731069584](https://github.com/kongbu0621/infra-local-hand/actions/runs/37731069584)
为 FAILURE：Linux 7132 passed / 89 skipped，Windows 1782 passed / 1352 skipped /
26 errors。纯投影和合成 fixture 误导入 Linux runtime，已修复为不依赖该 runtime 的
相同严格字段校验；没有放宽测试、重跑该次 CI，或执行该候选的现场窗口。

最终 D 的[首次 CI 37732198423](https://github.com/kongbu0621/infra-local-hand/actions/runs/37732198423)
head_sha 为上述 D，run_attempt=1，三个 job 全部 completed/success；两平台准确提交
身份、源码和安装验证步骤通过。Linux **7133 passed / 89 skipped**，CI 安装
**94 checks / 292 commands**；Windows **1809 passed / 1352 skipped**，平台安装
**10 checks / 10 commands**。没有重跑 CI。

本机从准确 detached D 构建，独立 venv 安装验证为 **PASS / 94 checks / 292 commands**，
构建元数据与报告均绑定 D。原现场安装、runtime/wheel/projection/loader 保持。

## 执行前静态核对与冻结

保护核对既有八输入、四旧核心批 20 件（36534 B）、诊断和容量各四件、六代失败维护
30 件及 24 个旧后续缺席名。原解析、同 FD 重读和来源检查通过；固定 user-data 按
原整文件 pin 核验，历史归档缺少该文件的事实保留。旧 08c 五件与原私有索引一致，
仅获准的[旧 08c 最小索引](Q2_CORE_EXEC_ORIGINALS_INDEX_20261008.md)公开。

静态包成员 859 件、17510303 B、100 目录；完整源码/归档/locator 及发布允许值关系通过。
两维护源 67956 / 61741 B，均低于各 98304 B；六代真实 pins、最大计量和 20 位时钟
的短预检样本 708 B，原 4096 B 限额不变。使用保留输入形状的 descriptor 为 26033 B，
bundle 压缩/展开分别 39115 / 134884 B，argv 54283 B，新 marker 静态形状 54783 B。
这些形状检查不声称已观察当前 VM，真实身份仍由唯一正式预检确认。

六代真实历史的合成 transition 为 11483 B，低于 65536 B；按静态成员及输入/manifest
各自最大值计算，核心包上界 19607470 B，低于原 33550320 B 包限额。未生成真实核心包。
七代维护义务 9072 MiB / 2590 inodes，加核心 9136 MiB / 2606；原每代 120 CPU-s、
全部单次预算、900/780s 维护期限和条件核心 900/800/750s 保持。

准确 D、自身 CI/安装、静态核对和两个 caller 在 GS2 前一并冻结。私有冻结记录
SHA-256 为 `6becd56dd4df54b3bb2b7dfd0b1db1411d50973e5576d849fac21c34286460d8`。
固定 guest_startup_assurance 明确 NOT_PERFORMED、管理前提确认和未证明连续排他；
该确认来自准确 Owner B，不由旧 host 前提或自动观察推导。

## 唯一现场返回及终态

`lhqjgrow-20261008d` 普通预检一次通过，同原点、nonce、manifest 和累计计量进入 execute。

- host 返回 `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，退出码 3；marker 已创建，SSH 请求 1。
- 已开始状态仅 `CONSUMED`、`GUEST_QUIET`，business_cases=0。
- 同次已有 guest stderr 为 `INCOMPLETE / PRE_QUIESCENCE / GROWTH_UNDECLARED_BUSINESS_UNIT`，
  报告 v2、`actions_started=[]`，固定覆盖声明保留。
- 诊断指向 system manager 的一个单元。对照准确 D，这条拒绝路径表示其已读属性命中
  受保护根引用，且单元不在已声明业务/域集合。报告没有提供具体命中属性或路径，
  不补采，也不将该拒绝表述为已经证明实际有任务写入数据。私有单元身份不公开。
- 原事件没有 `POWER_OFF_TOKEN`；本次没有关机、备份、镜像/文件系统增长或 VM 重启。
  journal 扩容未完成，remote_exit 保持 UNKNOWN。

仅沿原保护读取保留本次已经产生的五件原件，核对 caller 返回、marker/manifest、receipt、
事件和流摘要关系。没有新现场查询、重连、重试、补采、清理、恢复或扩展支线。本次 08d
原文及五件索引保持私有；只有获准旧 08c 五件最小索引发布。

GS2 为 **CONSUMED / FAILED**；六旧窗口和本次消费、完整义务及 UNKNOWN 保留。GS3 条件
未成立，原 `lhqcore-20261007a` 与 H01→Q4→H11 均 **NOT_RUN**，没有生成或发送真实核心包。
私有 gate 已终止为 `GS2_CONSUMED_FAILED_GS3_NOT_RUN`，执行前冻结记录及 caller 原样保留。
不得重放本次或旧 caller，也不能单独发行条件核心批；本轮不自动申请另一窗口。
