# Q1 离线配置与全部 slot 路径校验：验证记录

被测源码 `c0b817b2b97be26d13053a4ce74d29c6dcaeac05`，
tree `3915e7a1e783a97451cf4c97ea16b9b1f3b06c8f`，
父提交 `076e4c64c1580862ecedfa41101a77040587203f`。
本记录和日志另作后续提交，不把报告提交当作被测源码。

范围仍为 `LH-E3-QUOTA-HARNESS-v1` 的 Q1 隔离开发。批准 A
`415327ebdcc251bb055da9931a7a88990f750b7a` 与三份权威文档不变；
生产封堵、四包与 Plugin 均未改变。实际 fixture 尚未交付，Q1 实机和 E3 仍 BLOCKED。

## 本次实现

- 新增 `fixture_inputs.py`：严格解析两份原始字节快照，核对各自外部摘要、完整 source commit、
  manifest 与 installation 绑定；不读取声明的宿主路径、不生成 ticket、意图或资源保留。
- 提取共用 `validate_geometry`，同时用于离线检查和实际运行装配。此前运行装配只核对本次选中
  slot；现在拒绝**任意 slot**与全部固定输入或 journal 交叠，也拒绝固定普通文件路径的别名/祖先关系。
  词法检查不能发现 mount/symlink 造成的实际别名，仍需现场身份与保护权限验证。
- 新增 Linux CLI `tools/validate_q1_fixture.py`，要求 `python -I -B`，逐路径 NOFOLLOW、NONBLOCK，
  确认为普通文件后有限读取；manifest/runtime 分别限 32/16 KiB，并比较前后元数据。
  只读取显式快照，不导入 worker、journal 或 systemd runtime，不执行宿主操作。
  快照存储读取没有 wall-time 保证，本入口不提供 Q2 服务响应承诺。
- 输出 `CONFIG_CONSISTENT/OFFLINE_ONLY`，宿主状态固定 NOT_VERIFIED；三个 admission/E3/production
  标志均 false。容量按 FS UUID/project 域去重，仅报告声明额度，不把它当作已预留资源。
- [实测交接清单](E3_QUOTA_Q1_FIXTURE_HANDOFF.md)明确输入字段、摘要装配顺序、CLI 退出码、
  独立监督/系统基准与有限存储要求、永久占用和 Q1 → Q2 → Q3 → Q4 出口。
  CI 触发与变更分类加入新 CLI，后续仅修改入口也触发验证。

## 本地验证

命令：`python3 -I -B -m unittest discover -s tests -p 'test_e3_quota_*.py' -v`。
结果 **130 项测试通过，0 跳过，退出码 0**。包括既有 106 项 Q1 回归及新增 24 项：

| 新增组 | 方法数 | 证明范围 |
| --- | ---: | --- |
| 配置/路径 | 11 | 精确字节与来源/安装绑定、全部 slot、固定文件别名、共享计费域去重、不可变结果；纯逻辑，无宿主准入 |
| CLI | 13 | 真实子进程读取临时快照；拒绝摘要漂移、缺参数/文件、FIFO、符号链接、目录、超量及读取期间元数据变化；核验隔离参数和无写入/无声明路径访问/无宿主执行 |

源码编译检查、暂存差异检查、批准 A 与生产/分发代码不变检查均通过。
独立复核未发现阻断，检查了 Windows 测试收集的静态可移植性、路径检查和交接一致性；
此静态复核不冒充真实 Windows 运行。真实平台 CI 以发布后准确提交另记。

既有 native 成功 quota 使用 test-only syscall shim；实际 seccomp 负例不调用 quota。
runtime 的 manager/clock 等事实仍是 LOGIC_ONLY；真实临时文件/匿名管道/测试子进程不代表真实 query unit。
本地未重复运行完整产品源码/安装套件，不沿用前一候选的全量计数。

## 仓库内证据与下一步

本轮不生成 ZIP。可公开开发证据直接提交：

- [原始定向测试日志](validation/q1-fixture-20260923/unittest.log)。
- [命令、时间、退出码与边界检查](validation/q1-fixture-20260923/commands.json)。
- [Python、架构和编译器版本](validation/q1-fixture-20260923/environment.json)。
- [准确 source/tree 与逐文件 SHA-256](validation/q1-fixture-20260923/source-map.json)。

没有真实主机原件、新的安装产物或 private fixture 被提交到 Public。
**真实 quota syscall 0，systemd 查询单元启动 0，GX10 操作 0。**

下一步必须按交接清单取得预先准备的独立测试环境和准确管理输入，先做离线一致性检查，
再固定实际 Q1 运行与停止入口，验证原普通身份结果和管理侧结果。
当前仍没有完整一键 Q1 实机验收入口；Q1 的真实 ABI/权限/根绑定/enforcement/停止出口通过前，
不推进 Q2 接口整合或 Q3/Q4 真实三单元验收，不解除 `E3_SUPERVISION_UNVERIFIED`。

## 发布后准确 main CI

准确被测提交 `fbae9133bf924edee71ac71c61d35eda75900b46`，
[运行 35920369590](https://github.com/kongbu0621/infra-local-hand/actions/runs/35920369590)
已 completed / success。该提交与上面的源码检查点之间仅有报告/证据文档变更。
本节及 CI 摘要另作后续纯文档提交，不改被测源码或测试。

| 平台 | 源码通过 | 源码跳过 | 独立安装检查 | 命令数 |
| --- | ---: | ---: | ---: | ---: |
| Linux | 1017 | 1 | 94 / PASS | 292 |
| Windows | 222 | 277 | 10 / PASS | 10 |

Linux 唯一跳过项是实际 systemd/cgroup integration，原文明确包含
`E3_SUPERVISION_UNVERIFIED` 和专用身份/manager 准入未交付。
Windows 的 277 个跳过中包括本轮 13 个 Linux 专用 CLI 用例；新增 11 个纯配置方法已执行通过。
CI 成功不代表 Windows quota 支持或 E3 完成。安装验证针对默认 wheel，
**不覆盖管理侧 observer 的实际安装、权限或 quota 单元**。

- [准确 run/job/step 状态、时间与计数](validation/q1-fixture-20260923/ci-final.json)。
- [Linux 原文结果与跳过原因摘录](validation/q1-fixture-20260923/ci-linux-summary.log)。
- [Windows 原文结果与跳过原因摘录](validation/q1-fixture-20260923/ci-windows-summary.log)。

以上日志文件是原始完成 job 日志的逐字摘录，不是完整日志；完整日志由准确 GitHub run 提供。
