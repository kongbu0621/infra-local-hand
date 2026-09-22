# S1 捕获启动、任务身份与报告发布复核

日期：2026-09-22。输入主干 `7633e39fc7621352abaaf670839d5cc155f62960`；实际验证的产品候选 `bc678a6c23924dcb3963daec2f6670b4a2cfdbe2`，tree `a7ae98e4e8df0961711d329b25eb42283f30a51b`，直接 parent 为输入主干。发布说明是该候选的文档子提交，不改变已经验证的产品字节。

Owner 要求继续深入检查、有问题直接修复；既有“全部提交推送”和“可以全量测试”授权继续适用。本轮执行完整源码测试及独立 wheel 安装链路。授权范围仍为 S1；R、A、Owner 关闭决定与提交顺序不变，三份批准文档、依赖和工作流字节未改。

## 确认并修复的问题

| 边界 | 稳定复现的缺陷 | 修复与反向验证 |
| --- | --- | --- |
| 输出捕获启动 | 子进程启动后，第一或第二个读取线程启动失败，异常越过清理逻辑，真实子进程继续运行 | 两个入口共用捕获启动函数；失败时终止进程树，只等待确实启动的线程并关闭无读取线程持有的管道。确认终止后报告 capture_start_failed / indeterminate；无法确认终止则报告 termination_unconfirmed / indeterminate。真实子进程心跳停止、退出与管道关闭均验证，随后健康命令成功。 |
| Task UTF-8 身份 | JSON 转义可解析成孤立代理码点，但无法形成约定的 canonical UTF-8 摘要；原始异常会阻塞队列 | 摘要生成报告 task_digest_invalid，Worker 保留原提交字节、跳过无法表示的身份，继续后续合法 Task；不伪造摘要、Result、receipt 或 conflict。Controller 序列化返回 controller_json_invalid。合法中文与 emoji 摘要兼容，后续 CAS 成功，重复轮次不重新写入。 |
| 验收报告发布 | 最终路径直接写入会暴露半文件；写失败时可能删除并发发布者的文件；目录持久化结果未反馈 | 复用已验证的 create-only 原子发布函数：临时文件完整写入与同步后发布，不覆盖已有路径；失败清理保留并发胜者。发布后目录同步失败时完整报告仍保留，返回 acceptance_report_durability_unconfirmed / indeterminate。重复发布拒绝覆盖。 |

基线红测按正确收集范围分别为捕获启动 4 failed、Task 身份 3 failed / 1 passed、报告发布 3 failed。这些是复现旧缺陷的记录，不计入最终候选 PASS。新增 12 个测试全部纳入最终全量运行；另对进程生命周期、配置、现有验收报告执行定向回归。首次 Task 探针误收集了被导入的 6 个旧 fixture 测试，记录为 3 failed / 7 passed；修正收集后重新复现，没有将其计作额外覆盖或额外缺陷。

## 验证结果

| 项目 | 实际结果 | 命令耗时 | RSS 峰值 |
| --- | --- | --- | --- |
| 完整源码 pytest | 291 passed，0 skipped / 0 failed / 0 errors | 322.952 秒 | 119756 KiB |
| Python 编译 | PASS | 0.152 秒 | 18048 KiB |
| wheel 构建 | PASS | 0.882 秒 | 25524 KiB |
| 源码外全新 runtime 安装链路 | 89 checks / 280 commands，PASS | 263.433 秒 | 54484 KiB |
| runtime pip check、Linux shell 语法、源树 clean | PASS | 原始记录保留 | 原始记录保留 |

RSS 使用 Linux wait4 ru_maxrss，是回收子进程及其已等待后代的记录值，不是同时运行的进程树内存总和。全量源码测试不等于全平台 GitHub CI，本轮未运行完整 CI 矩阵。

wheel SHA-256：`67f88d7d28f3e12dcff277b082919647c32d2750d07db46dc23cc1d283e2c56f`。

三份独立审计将候选 Git 对象、实际安装字节、执行命令、stdout/stderr、报告 JSON、合成远端提交及持久业务文件交叉核对：87 个 tracked blob、23 个载荷文件、29 个 wheel 成员、wheel / 安装 RECORD 与 bytecode，以及 37 份普通业务收据均通过。既有合成 dangling symlink 单独按链接类型保留，不计为业务收据。原有 7 个内容读取失败恢复案例、5 份未提交文件归档和 2 份 Git 自动维护 trace 也核对通过。

本轮新增安装态链路为 4 个捕获启动失败案例、3 个报告发布案例及 1 条异常身份→合法 CAS→重复轮次链路，共增加 8 checks / 14 commands。审计读取保存的程序、真实命令及对应文件，不把已经恢复的历史现场描述为当前观测；特别是不会查询或操作历史 PID，以免 PID 复用造成误认。无法确认终止的反例另由源码测试覆盖，没有将 indeterminate 报成 succeeded。

CLI wait 取到合法 Result 时可能返回退出码 0，而 Result.status 仍是 rejected 或 indeterminate；命令退出码与业务状态分别核对。

## 环境与证据

使用本轮全新独立 checkout、build venv 和 runtime venv，保留既有环境。实际环境是云端 Linux x86_64 / overlay、Python 3.12.14、Git 2.51.1，不是 GX10 / aarch64 / ext4 实机。

源码来自 --no-hardlinks 的独立本地 clone，并通过已授权 GitHub 接口读取候选元数据、重建和核对完整 tree / commit SHA；工作树 clean，git fsck 通过。没有声称本轮完成了远端 Git 直连 clone 或 fetch。

录制器初始化时两次因 evidence 父目录未创建而失败，目标子命令尚未启动。修正后才开始正式记录；这两次准备失败另存元数据，耗时和 RSS 标为不可用，没有补造日志或成功记录。所有实际录制命令保存 argv、cwd、版本、退出码、日志摘要、耗时及 RSS；原始失败轮次以及已留存的探针脚本一并进入私有证据包。

公开仓库只包含修复、测试、验收程序及本摘要；不公开 SOP 历史、上游规则全文或 GX10 实机原始证据，不添加许可证。

## 结论范围

- canonical JSON 算法保持原样；本轮仅明确处理无法编码为 UTF-8 的身份，未改变遗留 NaN 或重复键策略。不能据此宣称已完成全局严格 JSON 协议迁移。
- 无法表示摘要的原 Task 仍保留在合成 mailbox；不会为其制造另一种摘要或伪造成功收据。
- 线程启动修复覆盖 RuntimeError / OSError 及两个读取线程位置；不能从本轮推断 Windows 原生进程树行为已经验证。
- 报告原子可见性和同步结果以本轮本地文件系统为限，不是任意网络文件系统或任意本地写入攻击者下的保证。
- Windows 继续 DEFERRED / UNVERIFIED；未切换现役服务，未执行 S2 或 artifact-ledger A2。
- 历史 pack 扫描失败与更早文件同步异常的根因仍未完全确认，本轮通过不关闭这些历史未决归因。
