# Q1 单元内启动与外部采集：验证记录

源码提交 `c1c37dd31763726eeca3084c0db690836b0d43fa`，
tree `88a7c4fe373ce7a8775e674c760af914d8440782`，
父提交 `d6f5e5a907eea722919e526c1313cce870f67ddb`。
本报告与开发证据另作后续提交；测试完成后未修改被测源码。

**当前为本地检查点，尚未发布 GitHub；准确候选 CI 未运行。**
推送 main 被自动审批拒绝，理由是未识别到向公开共享分支发布的明确授权。
远端核对仍为上述父提交，不把本地 commit 或旧候选 CI 记为本轮发布成功。
该状态记录于 [发布状态](validation/q1-launch-20260924/publication-status.json)。

## 范围与交付

沿用 `LH-E3-QUOTA-HARNESS-v1` 已批准的隔离开发范围、A
`415327ebdcc251bb055da9931a7a88990f750b7a` 和独立 CLOSED C
`5a4ea852091db06549a876e42bbd5f95d5869d3b`。逐字节核对三份权威文档未变；
四个产品包、默认 wheel/Plugin 配置和生产 `E3_SUPERVISION_UNVERIFIED` 封堵未改变。
真实 fixture 仍 NOT_PREPARED，真实 Q1/E3 仍 BLOCKED。

- `launch_q1_experiment.py` 与管理侧 `launcher.py`：严格外部摘要和源码清单，
  当前单元身份绑定、安装/保护输入核对、create-only/fsync 实验输入交付、同 PID exec。
  恢复保留原票据，失败保留创建的字节，不覆盖、不重试、不触碰 journal。
  外层须在 Python 启动前固定安装与宿主信任；已执行代码不能靠自查建立自身信任。
- `experiment_capture.py`：接管已有管理进程的原始未缓冲匿名管道，在事先固定的
  有限管理窗口内保留原字节、部分输出、双流 EOF、客户端退出和关闭错误。总量 128 KiB，
  stderr 还受 16 KiB 上限。不会发起进程、解析输出授予身份、发停止命令或补投查询。
- 独立 controller 观察可缺省，以便保留启动器早期失败；如已提供则核对原 boot/管道。
  已知原 query 身份可交回既有恢复路径，未知身份不猜测。采集完成不证明查询成功、
  单元退出或资源可释放。
- CI 增加新 CLI 的触发、运行变更分类与编译覆盖；管理侧源码和测试沿用原有 glob。
  [启动与采集交接](E3_QUOTA_Q1_LAUNCH_HANDOFF.md)明确真实 fixture 仍须交付。

## 本地验证

UTC 2026-09-24 01:19:53–01:19:57：
`python3 -I -B -m unittest discover -s tests -p 'test_e3_quota_*.py' -v`。
**235 项通过，0 跳过，退出码 0**；原有 194 项与新增 41 项一起执行。

| 新增组 | 项数 | 验证范围 |
| --- | ---: | --- |
| 启动器与 CLI | 20 | 严格输入、安装与路径、身份变化拒绝、失败保留、短写/fsync、真实 exec 的 PID/双管道/有限 CPU 连续；宿主准入使用替身 |
| 外部采集 | 21 | 真实匿名管道、双流共享上限、超时与部分输出、EOF/客户端退出分离、收尾诊断、恢复、管道身份及关闭错误；不启动 systemd/quota |

编译、差异空白检查和批准文档/产品/分发边界检查通过。
独立复核收口了管理采集收尾期限、扩展模块和同名 package 覆盖源码的问题，最终在限定
源码/合同/测试设计范围内无剩余阻断。开发首轮失败和中间测试不能改写为最终候选成功，
详见 [开发与复核记录](validation/q1-launch-20260924/development-notes.md)。

本地未重跑整个产品/安装套件；Linux 和 Windows GitHub CI 必须在获准发布后验证准确
候选，当前分别为 **NOT_RUN**。没有沿用上一轮 passed/skipped 或安装计数。
未执行真实 quota 查询、真实 systemd 单元或 GX10 操作，未完成 E3 验收。

## 可核对的证据

- [最终原始测试日志](validation/q1-launch-20260924/unittest.log)
- [准确命令、时间、退出码与日志摘要](validation/q1-launch-20260924/commands.json)
- [开发环境](validation/q1-launch-20260924/environment.json)
- [源码/tree 及逐文件摘要](validation/q1-launch-20260924/source-map.json)
- [权威文档和产品边界检查](validation/q1-launch-20260924/boundary-check.json)

本轮不另生成 ZIP。下一步是发布这两项本地检查点并核对准确候选 CI，随后按既有清单
交付真实隔离 fixture：受监督控制器、独立停止、有限证据存储、准确安装与文件系统身份。
这些现场输入齐备后才运行 Q1 权限/硬配额/域外负例和独立退出验收，再进入 Q2 → Q3 → Q4。
