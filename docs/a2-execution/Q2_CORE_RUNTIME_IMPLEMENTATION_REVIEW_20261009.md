# 运行时前提与核心角色接线修复

范围 `LH-Q2-CORE-RUNTIME-CONTINUATION-v1`，RT1–RT3。准确 A、Owner B 和独立 C
见[基线](../governance/Q2_CORE_RUNTIME_CONTINUATION_BASELINE.md)。本实现继承 C，
不修改 A 的三份文档字节或历史 OPEN 标签。本记录不证明现场准备、维护或核心成功。

## 实现

原历史 locator 保持原义。维护输入和 approved-input 从准确原 plan、retry preparation
和 system plan 推导显式角色投影，分别绑定 system ordinary 与 retained user ordinary，
保留 32/64 tasks 差异和原四父域。投影摘要由 guest、host 和独立 dispatcher 校验。
离线 artifact/source 校验保持可移植，不加载 Linux 执行模块。

guest 在 pre/post 原身份准入后各执行一次限定准备。保留当前 unit、cgroup、进程和
持久数据检查；原配置必须匹配，最多补齐两个准确 `/run` 配置及必要目录，拒绝覆盖、
符号链接、错误权限、残留 job、失败状态和非空域。每阶段最多 12 控制命令/60 秒，
只对合格 inactive 对象执行一次 start。用户 helper 清空附加组并切换全部 UID/GID，
通过已绑定可执行文件 FD 和准确环境执行。完整 quiescence 及 poweroff/resize 前检查保留。

真实准备报告包含命令及 EOF、配置和工具身份、当前属性、角色关系、池预留和动作记录；
host 验证完整报告，transition 保存前后报告 pins 和关系摘要，核心重新核对当前事实。
新协议版本、十代旧失败记录、全部费用、两端消费者及发行摘要同步更新。
bundle 使用严格 UTF-8 后压缩，避免压缩前重复 base64；源码逐字节保留，所有旧上限不变。

## 离线核对

- 固定 17 项输入、十代 50 件维护原件、原核心 20 件、诊断及容量留存件核对通过；
  已采用 activation 的 30 件原始返回仍由准确归档和索引验证。没有 VM 查询或 SSH。
- 从准确历史源码抽取纯模板表达式，核对六个 slice 配置及 manager drop-in 的字节一致性。
  原角色投影 2052 B，未把历史 PID、boot 或 inode 当作当前身份。
- 工作树静态 pre descriptor 28470 B；消费标记形状 63813 B（最终 40 字符 D 增加 32 B），
  压缩/展开 bundle 33691/143770 B，实际 argv 编码 47224 B。
- 使用真实角色和明确合成的成功形状测量 post：准备报告 12754 B，descriptor 48655 B，
  压缩/展开 bundle 37116/165929 B，argv 51788 B。合成形状不作为维护成功原件或发行依据。
- 固定父目录占 9 个 FD；加原树遍历、新增持有和临时开销，保守 98/128 FD。
  十一代维护 14256 MiB/4070 inodes/1320 CPU 秒；加原核心捕获为 14320 MiB/4086 inodes。
  各相关 guest pool 每阶段另预留 8192 B/32 inodes，post 累计 16384 B/64 inodes，无退款。
  自动服务开销继续受原 VM、manager 和维护预算约束。
- 最终受影响回归 3221 passed/48 skipped；另有最终运行时专项 35 passed，覆盖复用、
  缺席创建、两阶段、冲突、凭据切换、报告篡改、预算和单次执行。新进程下禁止 Linux
  runtime 导入的 artifact/source 校验通过。准确 D CI、独立安装和 caller 冻结另行记录。

## 经 Owner 批准公开的旧 09a 最小索引

准确 D `54d32df2f82fe863e1535ddb8134617c2654e33d`。以下仅为 basename、bytes、SHA-256，
已与保留原件及原私有索引交叉核对。原失败、消费和 remote UNKNOWN 保留。

| basename | bytes | SHA-256 |
| --- | ---: | --- |
| `.lhqjgrow-20261009a.consumed.json` | 59556 | `777715c3cbf6d9c9ecef43a63ae1fe2dee6fa4c48170f0114aa883383f55c87d` |
| `.lhqjgrow-20261009a.events.jsonl` | 441 | `687cce89ef1ef88e44d482655d61e2a8e48d84bb4e2da36d154ccf98accfec60` |
| `.lhqjgrow-20261009a.pre.stderr` | 922 | `6c40a4e9d0882c80ffb89829be5c52cf9bc861a698d5bd498c1efa434539a88e` |
| `.lhqjgrow-20261009a.pre.stdout` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.lhqjgrow-20261009a.receipt.json` | 16482 | `1737c6c75c8dc97b80734e94b4d161f33b9893d7ad8e63658acc9514e190d096` |

原始证据、机器目标、activation 索引及新 09b 原件/索引保持私有。记录时 RT2 尚未发行，
RT3/H01/Q4/H11 NOT_RUN；完整维护原件验证是核心发行的必要条件。
