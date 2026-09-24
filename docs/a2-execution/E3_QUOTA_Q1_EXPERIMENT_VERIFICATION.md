# Q1 单次管理实验入口：验证记录

被测源码 `e9b21b355a5dcb507d1b73d620b3307918d04533`，
tree `483ea3aa046a14e93f512cd86d31ddcbd78ae20f`，
父提交 `6c330356793f4633d3f8379be3c447bda761ba29`。
本记录和开发日志另作后续提交，不把报告提交当作被测源码。

范围仍为 `LH-E3-QUOTA-HARNESS-v1` 的 Q1 隔离开发。批准 A
`415327ebdcc251bb055da9931a7a88990f750b7a` 三份文档与生产封堵保持；
四个产品包、默认 wheel 与 Plugin 未改变。真实 fixture 仍 NOT_PREPARED；Q1 实机和 E3 仍 BLOCKED。

## 实现与准确边界

- 新增单次管理入口 `tools/run_q1_experiment.py` 及 `experiment.py`：外部摘要、准确来源、
  受保护输入、原安装与票据绑定；明确选择一次 `run` 或 `recover_original`，不生成新 ID 或延长原截止。
  输入文件也加入全部 slot、配置/程序与 journal 的路径交叠检查。
- 新增 `controller_guard.py`：在构造 journal 前，核验实际 boot/root/user namespace/PID/cgroup、
  两个独立匿名写管道、cgroup2 身份及实际 memory/pids/cpu 限制、进程 CPU rlimit，
  再用一次固定 systemctl 核对 MainPID/InvocationID、有限监督配置和无重启/额外钩子。
  固定管理观察双流共用 16 KiB，最多 2 秒观察；不派生替代管理查询。
- 实验入口在 journal 构造前标记进入不确定区。中断尽量保留已有输出和已知子进程，原请求不补投；
  journal 关闭失败单独记录并阻止成功出口。管道短写继续交付同一记录，断开/零写返回 74，不再查询。
- 新增纯编码 `experiment_evidence.py`：单条私有管理诊断最大 128 KiB，保留原输出字节、原绑定、
  原判定和独立错误；这不替代 Q2 的 32 KiB socket 响应。内部 Outcome 未携带的 EOF/完整性事实不补造，
  `evidence_complete` 及全部准入标志保持 false。永久意图/资源保留不因成功、关闭或恢复而释放。
- 核对固定 systemd 源码后修正空 Exec 数组的解析：即使 `--all`，空数组仍可能不输出属性行。
  仅规范化已知 Service Exec 数组，其他身份/限制属性缺失、重复/额外字段继续拒绝。
  非空 hook 保留原值并拒绝，未知系统版本格式不猜测。
- CI 的路径触发/分类加入新 CLI；源码编译检查覆盖管理侧模块和两项管理入口。

入口验证已存在的 supervisor，不创建它；自身读取、进程创建与输出仍可能阻塞，需要外层独立监督。
控制器停止不证明独立 query unit 停止，guard 拒绝也不证明其管理客户端已收口。
准确 InvocationID/cgroup inode 只在 unit 启动后成立；外层受信启动器须在同一受监督 unit 内
固定输入后 exec 入口，保留 MainPID、原监督计时、CPU 预算和票据期限。
**此外层启动装配、真实 fixture 与完整 Q1 验收尚未交付。**

## 本地验证

UTC 2026-09-24 执行：
`python3 -I -B -m unittest discover -s tests -p 'test_e3_quota_*.py' -v`。
最终 **194 项通过、0 跳过、退出码 0**；既有 130 项与新增 64 项一起运行。

| 新增验证组 | 方法数 | 证明范围 |
| --- | ---: | --- |
| controller guard | 27 | 严格配置、实际观察函数的替身输入、有限 manager 采集/清理及匿名管道；未调用真实 systemd |
| 实验输入与接线 | 15 | 准确原票据、guard 先于 journal、恢复不运行、失败/中断/二次关闭/编码错误；LOGIC_ONLY |
| CLI | 9 | 真实 Python 子进程与替身运行函数：平台/UID/解释器标志拒绝、退出码、短写/断管不重投 |
| 私有诊断编码 | 10 | 原字节保留、最大尺寸、原身份绑定、拒绝矛盾成功声明、恢复保持 UNKNOWN；纯逻辑 |
| runtime 属性解析 | 3 | 只补已知空 Exec 数组，非空 hook/其他属性缺失/重复或未知字段拒绝；LOGIC_ONLY |

编译检查、暂存差异检查、批准 A 和产品/分发代码不变检查通过。
独立复核覆盖入口顺序、错误收尾、原票据、外层 exec 装配可达性与边界，未发现未解决阻断。
真实 quota syscall 和真实 systemd query unit 启动均为 0，GX10 操作为 0。
既有 native 成功 quota 分支仍使用 test-only syscall shim；真实 seccomp 负例不调用 quota。
临时文件、管道、测试子进程不能作为实机 Q1 出口。

开发中保留的失败说明见[开发修正记录](validation/q1-experiment-20260924/development-notes.md)。
首次整组集成因测试还读取旧 `code` 字段出现 8 个子用例错误；改为实际 `failure_code` 后，
CLI 9 项及最终 194 项通过。没有将首次失败改写为成功。

## 入库证据和下一步

本轮不生成 ZIP，公开安全开发证据直接入库：

- [原始定向测试日志](validation/q1-experiment-20260924/unittest.log)
- [准确命令、时间、退出码与边界检查](validation/q1-experiment-20260924/commands.json)
- [开发环境版本](validation/q1-experiment-20260924/environment.json)
- [源码/tree 及逐文件 SHA-256](validation/q1-experiment-20260924/source-map.json)
- [准确输入、失败处理与实测交接](E3_QUOTA_Q1_EXPERIMENT_HANDOFF.md)

下一步补外层受信启动与有限采集装配，再在明确交付的隔离 fixture 完成权限对照、真实绑定、
限额强制和独立退出验收。Q1 出口通过后才进入 Q2 → Q3 → Q4；不重复 GX10 库存或改现役服务。

本地没有重复执行整个产品源码/安装套件；准确发布提交的 CI 如下分别记录，不沿用上一候选结果。

## 首轮 CI 与测试可移植性修正

首轮准确 head `6e1a25be40b5a4364a425301049c55b3e1eaabae` 的
[run 35936686250](https://github.com/kongbu0621/infra-local-hand/actions/runs/35936686250)
中，Windows job `107435202820` 的源码步骤失败：**3 failed、252 passed、308 skipped**。
安装验证因前序失败未执行，不记 PASS。失败均位于新诊断编码测试：合成 Linux native 成功报告
经 `match_report` 检查时，真实 Windows `os` 没有 `O_PATH`，故正确拒绝 `FD_MODE`。
同一首轮的 Linux job `107435202806` 完成 success：源码 **1081 passed、1 skipped**，
安装 **94 checks、292 commands PASS**。整个首轮 workflow 仍为 failure。

测试修复提交 `273eb0a77538a4617f157fa79f9b32cac4a3fa2f`，
tree `41393c4dda141a4ed435487ff5550447dfb7f7a0`，仅修改
`tests/test_e3_quota_experiment_evidence.py`：在每个测试内替换该模块使用的 os 引用，
明确模拟 Linux `O_PATH=0x200000` 与 `O_ACCMODE=3`，测试结束即恢复。
不修改全局 os、不放宽产品校验、不增加 skip。独立复核认可此限定修复。
本地只重跑受影响的 10 项纯编码测试，全部通过；此结果不冒充实际 Windows 运行。

- [首轮 Windows 原始失败摘录与日志摘要](validation/q1-experiment-20260924/windows-first-failure.log)
- [修复后定向原始日志](validation/q1-experiment-20260924/windows-portability-targeted.log)
- [修复后准确命令、退出码及测试文件摘要](validation/q1-experiment-20260924/windows-portability-targeted.json)

## 修复后准确候选 CI

修复报告 head `4dcf46cd586f7af5642fb49326da79fc6f2fc768`，
tree `2bc7b81ffd829475cd3fb249f9d9583af40a045f`，
[run 35937512985](https://github.com/kongbu0621/infra-local-hand/actions/runs/35937512985)，attempt 1。
该候选的全部运行代码仍与源码检查点 `e9b21b3` 相同，仅有上述测试修复及后续证据文档。

整个修复后 workflow 已完成 **success**，准确结果为：

| 平台与 job | 源码 passed | 源码 skipped | 独立安装 |
| --- | ---: | ---: | --- |
| Linux `107437804862` | 1081 | 1 | 94 checks、292 commands PASS |
| Windows `107437804901` | 255 | 308 | 10 checks、10 commands PASS |

运行/作业身份、步骤结论和完整抓取日志摘要见
[CI 元数据](validation/q1-experiment-20260924/ci-runs.json)；准确计数、跳过原因和安装输出见
[CI 原日志摘录](validation/q1-experiment-20260924/ci-excerpts.log)。
首轮与修复轮分开记账；后续本提交仅补验证记录，没有再改变源码或测试。
Windows 的跳过项仍按平台记录，不能解释为 Linux systemd/quota 已实测；生产封堵不因 CI success 解除。

## 固定来源

systemd `70bae7648f2c18010187c9cf20093155eaa26029` 的
[systemctl-show.c](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/src/systemctl/systemctl-show.c)
`print_property` Exec 数组逐成员打印分支（空数组零行）已直接核对。
源码核对用于解析修正，不代表目标 systemd 版本或真实监督已通过。
