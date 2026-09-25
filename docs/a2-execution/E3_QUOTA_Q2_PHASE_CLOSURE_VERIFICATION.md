# Q2 第四批验证与接续记录

日期：2026-09-25。固定干净源码上的两组相关回归共 **802 项：787 通过、15 环境跳过、0 失败、0 错误**。
本批实现六单元关闭、原普通客户端双流采集、独立管理监督组件、broker 阶段关闭检查和固定输入预检。
Q2 整体仍待受信桥接及整链 fixture 驱动，Q3/Q4 未运行；生产封堵保留。
实现、接口和准确 fixture 字段见 [第四批交接](E3_QUOTA_Q2_PHASE_CLOSURE.md)。

## 准确源码与发布

| 检查点 | 本地提交 | GitHub main 提交 | 相同 Git tree |
| --- | --- | --- | --- |
| 第三批验证记录 | `a0e2ac45d791cad536ab49570de1e70bb41003e8` | `53b70f6bc14ea39d6a66cdd4a2a504c89827d046` | `8f93109ee0aef7a35f124eed11851d83030b4e50` |
| 本批准确源码 | `59a72ddbac0703486123873f4ee1b03cff8c522a` | `ae63052cdf9d67534bcd35347cbf2596651c3246` | `8d2dfa5d3a5c45f510737c6d5896e798d5020898` |

本地源码提交后工作树干净，再运行下面的最终回归；运行完成后再次核验干净状态。
19 个变更文件通过已授权的 GitHub Connector 生成相同 tree；先核对原 main，非 force 更新，再读回
确认准确 main 为 `ae63052cdf9d67534bcd35347cbf2596651c3246`。提交元数据不同导致两个 commit ID，
不把同树发布解释为跨平台重测。本验证报告和日志在后续独立提交中保存。
R/A/C 及三份批准文档字节未修改，未安装目标宿主或重放任何 Q1 实验。

## 固定源码回归

Python 3.12.14，Linux 6.18.44。两组独立子进程并行运行，区间为
`2026-09-25T10:36:49.171813+00:00` 至 `2026-09-25T10:36:56.667805+00:00`。

```sh
PYTHONPATH=tools:tests PYTHONDONTWRITEBYTECODE=1 python -B -W error -m unittest discover -s tests -p 'test_local_hand_jobs*.py' -v
PYTHONPATH=tools:tests PYTHONDONTWRITEBYTECODE=1 python -B -W error -m unittest discover -s tests -p 'test_e3_quota*.py' -v
```

| 组 | 收集 | 通过 | 跳过 | 退出码 | 原始日志 / 准确命令 |
| --- | ---: | ---: | ---: | ---: | --- |
| jobs | 516 | 502 | 14 | 0 | [日志](validation/q2-phase-closure-20260925/jobs.log) / [命令](validation/q2-phase-closure-20260925/jobs-command.json) |
| quota | 286 | 285 | 1 | 0 | [日志](validation/q2-phase-closure-20260925/quota.log) / [命令](validation/q2-phase-closure-20260925/quota-command.json) |

日志 SHA256：jobs `f7dad289fab23af5d2bb9b9f62dd9f1099e004249885463f20232068eebd9989`；
quota `918affdcbcccd25c89f4e942e2ae12dd2ebd0349093f6d5a780a8c146f7b82d3`。

本批新增四个测试文件、22 个测试方法，包含在上表内。覆盖六阶段八项退出事实、原 identity 与
receipt/普通退出摘要、管理等待原交付、客户端被杀/缺 EOF/输出越界/关闭失败、原期限、
启动钩子与身份变化、真实文件锁与 fsync 失败、账本损坏/重启不重投，以及 broker 阶段推进。
最终提交前的 42 项定向验证为 41 通过、1 环境跳过；最终准确结果以上表为准，不重复累计。

| 层次 | 实际证据与限制 |
| --- | --- |
| 持久文件与 SQLite | 真实临时文件、fsync、flock、SQLite 事务及不可变事件；跨进程重启/消耗语义已有相关回归。临时文件所有权在部分测试中明确建模。 |
| 匿名进程管道 | 真实子进程和 OS 非阻塞 stdout/stderr，EOF 来自零字节读取；人为保留写端验证缺 EOF。systemd 状态与 cgroup 原身份明确建模。 |
| 命名 Unix socket | 14 项因执行器 AF_UNIX 限制跳过，包括既有 jobs 13 项和管理 listener 1 项；匿名 socketpair/FD 测试不替代命名或跨 PrivateUsers 验收。 |
| systemd 整链 | 1 项因 PID 1 非 systemd、无既有专用委派及固定非 root 账户跳过；没有实际启动完整普通/管理链或执行真实 quota syscall。 |
| fixture 入口 | 无参数实际子进程返回 exit 3 / `BLOCKED` / `EXPLICIT_PRIVATE_FIXTURE_REQUIRED`；`q2_accepted=false`、`q3_status=NOT_RUN`、`production_supported=false`。不是 fixture 就绪或 Q3 PASS。 |

默认预检的 [stdout](validation/q2-phase-closure-20260925/preflight.stdout)、
[stderr](validation/q2-phase-closure-20260925/preflight.stderr) 和
[准确命令/摘要](validation/q2-phase-closure-20260925/preflight-command.json) 已保存。
这是相关文件族完整回归，不是全仓库本地运行或新的 guest 实验证明。

## CI

第三批准确源码 `007cbdf49ca61005c91f092a982a6c9b9240e6f0` 的
[run 36119356829](https://github.com/kongbu0621/infra-local-hand/actions/runs/36119356829)
已在本轮读回核实：classify-change、Windows、Ubuntu 均 completed/success。
这是对第三批报告当时 pending 的补充，不改写当时记录。

本批准确源码已触发 [run 36125012802](https://github.com/kongbu0621/infra-local-hand/actions/runs/36125012802)，
head SHA 为 `ae63052cdf9d67534bcd35347cbf2596651c3246`。当前已核实 classify-change success；
Windows、Ubuntu 尚在运行。待其完成后按准确 head SHA 补充结果，当前不记为 PASS。
两轮准确 job 身份与本次状态快照保存在 [CI 状态记录](validation/q2-phase-closure-20260925/ci-status.json)。

## 保留的开发中间失败

以下为实际工具观察摘要，不声称拥有这些早期失败的完整原始日志：

1. 新普通管道属性路径在第二次删除 StandardOutput 时发生 KeyError；改为仅删除存在的属性，
   三个 Q2 单元统一保留原管道；最终回归覆盖旧运行器属性路径。
2. 新 journal 测试在 fixture 尚未 `open()` 前读取不存在的 journal 属性；修正测试初始化，
   保持实际文件/锁/fsync。导入 TestCase 曾造成重复收集，改为模块引用后再统计最终 802 项。
3. 代码复核补齐启动交付尚未出现时的等待、CLOSED 前原管道关闭错误、持久记录顺序和损坏快照
   防重检查；相应反例验证失败证据保持不确定，不补造当前成功。

## 直接接续

下一批集中补受信双向桥接、固定 fixture 整链协调及独立外层采集，再在已提供的准确隔离环境中
组合运行正常链与故障/恢复场景。具体调用责任、固定字段和缺口均在第四批交接中。
不再重复 Q1 只读盘点；旧 UNKNOWN/INCOMPLETE、原 reservation 与已消耗容量继续保留。
当前源码缺口与实机 fixture 缺口是两件独立待完成事项，不能仅凭换到 systemd 主机宣告验收。
