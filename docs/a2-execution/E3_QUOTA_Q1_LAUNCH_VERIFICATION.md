# Q1 单元内启动与外部采集：验证记录

源码提交 `c1c37dd31763726eeca3084c0db690836b0d43fa`，
tree `88a7c4fe373ce7a8775e674c760af914d8440782`，
父提交 `d6f5e5a907eea722919e526c1313cce870f67ddb`。
本报告与开发证据另作后续提交；测试完成后未修改被测源码。

此前推送 main 被自动审批拒绝，理由是未识别到明确公开发布授权；用户随后明确授权
发布上述两个检查点并核对 CI。普通 git push 缺少登录凭据，改由已连接的 GitHub 接口
建立提交；提交元数据不同，文件树逐字节一致，原本地提交保留。

| 检查点 | 本地提交 | 已发布提交 | 相同 tree |
| --- | --- | --- | --- |
| 源码 | `c1c37dd31763726eeca3084c0db690836b0d43fa` | `07807d62b49f07d31e9e41d4f2fd25c3cefe8f83` | `88a7c4fe373ce7a8775e674c760af914d8440782` |
| 初始验证记录 | `25ace7f87cd370a699c8b11636d20f06b2bb64b2` | `8cc2b2b8255502d1407f8b820be86b47cc813559` | `d86aa665a14552554b9ade9bcd80cf0bbc4f25ee` |

发布 `main` 已核对为 `8cc2b2b`，准确候选 CI
[run 35956624107](https://github.com/kongbu0621/infra-local-hand/actions/runs/35956624107)
attempt 1 已完成 **success**。独立只读核对确认原始 source-map 的 39 个文件、日志摘要及两个检查点间仅
文档/证据变化均一致。详见[发布映射](validation/q1-launch-20260924/publication-map.json)
和[发布状态](validation/q1-launch-20260924/publication-status.json)。

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

本地未重跑整个产品/安装套件；Linux 和 Windows GitHub CI 已验证准确发布候选。
没有沿用上一轮 passed/skipped 或安装计数。
本轮 Q1 开发未执行真实 quota 查询或 systemd 查询单元，也未操作 GX10，未完成 E3 验收。

## 准确发布候选 CI

准确 head `8cc2b2b8255502d1407f8b820be86b47cc813559`，
tree `d86aa665a14552554b9ade9bcd80cf0bbc4f25ee`，
run `35956624107`，attempt 1。三项 job 均 success；本轮无需 CI 修复或重跑。

| 平台与 job | 源码通过 | 源码跳过 | 独立安装 |
| --- | ---: | ---: | --- |
| Linux `107496239609` | 1122 | 1 | PASS：94 checks、292 commands |
| Windows `107496239604` | 261 | 343 | PASS：10 checks、10 commands |

运行/作业身份、实际步骤结果、准确计数、逐项跳过原因及完整抓取日志的规范化摘要见
[CI 元数据](validation/q1-launch-20260924/ci-runs.json)，原日志对应行见
[CI 摘录](validation/q1-launch-20260924/ci-excerpts.log)。日志规范化仅移除开头 BOM、
将 CRLF 转为 LF 并保留末尾换行，摘要不冒充未经转换的传输字节摘要。

Linux 唯一跳过是未具备专用非 root 账户/预委派管理准入的真实 systemd/cgroup 集成测试，
明确报 `E3_SUPERVISION_UNVERIFIED`。Windows 343 项按原日志中的平台/能力原因跳过；
跳过数独立记账，不是通过数。CI 运行既有平台启动与安装检查，不提供本轮 Q1 fixture、
真实 quota 或完整三单元退出的验收证明，生产封堵保持。

本次 CI 结果补记只修改文档/开发证据，不改变该候选源码、测试或 workflow。

## 可核对的证据

- [最终原始测试日志](validation/q1-launch-20260924/unittest.log)
- [准确命令、时间、退出码与日志摘要](validation/q1-launch-20260924/commands.json)
- [开发环境](validation/q1-launch-20260924/environment.json)
- [源码/tree 及逐文件摘要](validation/q1-launch-20260924/source-map.json)
- [权威文档和产品边界检查](validation/q1-launch-20260924/boundary-check.json)

本轮不另生成 ZIP。下一步按既有清单交付真实隔离 fixture：受监督控制器、独立停止、
有限证据存储、准确安装与文件系统身份。
这些现场输入齐备后才运行 Q1 权限/硬配额/域外负例和独立退出验收，再进入 Q2 → Q3 → Q4。
