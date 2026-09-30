# systemd 取消修复：准确候选与下一批验收交接

最新候选、已补齐的外层 Q4 交接和现场输入见
[2026-09-30 候选交接](CANDIDATE_HANDOFF_20260930.md)。下文仅保留 `8b72306` 当时事实。

后续源码进展见[固定 helper 取消场景](Q4_CANCEL_CASE.md)。下文保留 `8b72306` 候选当时的
CI、产物和缺口记录；其中“取消 driver 尚未实现”是该候选的历史状态，不是后续源码状态。

2026-09-30。接续[取消修复与原生实验退役](SYSTEMD_CANCELLATION_REPAIR.md)。
本轮完成普通 CI、分发产物核验和现有真实验收入口的静态对齐；没有运行新的主机批次。

## 已完成的候选核验

- 准确源码：`8b723063caa2a628c491435a98e8e1d8f80c8e55`。
- Git tree：`68d8adbc23e157629c3362346ffd0aa2e6f3df34`。
- [CI 36679838718](https://github.com/kongbu0621/infra-local-hand/actions/runs/36679838718)：
  push、attempt 1、HEAD 与源码一致，三个 job 全部 SUCCESS。
- 已下载两个平台的保留产物，核对 GitHub artifact SHA-256、wheel 的完整源码清单和实际成员字节，
  并读取独立安装验收报告。不是只看绿色状态。

| 验证范围 | 准确结果 |
| --- | --- |
| Linux 源码 | 3190 passed，51 skipped |
| Linux 独立 root collector | 16 passed，0 skipped |
| Linux 独立安装态 | PASS，94 checks / 292 commands |
| Windows 源码 | 1117 passed，996 skipped |
| Windows 独立安装态 | PASS，10 checks / 10 commands |
| 此前本地取消定向回归 | 114 passed，1 skipped |

两份安装报告都明确 `fixture_only=true`、`physical_node_tested=false`。这些结果不等于真实
systemd、project quota、三单元停止或 GX10 验收。平台跳过项保留原结论。
完整脱敏记录见 [CI 与产物核验](evidence/systemd-cancellation-8b72306/ci-verification.json)。

## Linux 验收使用的准确产物

| 对象 | 已核验身份 |
| --- | --- |
| GitHub Linux artifact | `11081034897`，`local-hand-Linux-36679838718-1` |
| artifact SHA-256 | `343bbe742755155620216adbc65052ad276dc3cb5adebcf38ea5ee558e07d2dc` |
| wheel 成员 | `dist/infra_local_hand-0.2.0a1-py3-none-any.whl` |
| wheel SHA-256 | `2bc97156c8a360d398065841b49120210f093981fed8e6f136ce80e85624a0fb` |
| 完整 payload 摘要 | `f75a18f2b7b8d52dadb51285e0a7ae392541076855164e85aac45b7abcc4972e` |
| 未配置 Plugin ZIP SHA-256 | `0e9d11b89f196dda2bf23a2995cf20ddf5e203a74c71f67fcb14369a17769bb4` |

Linux wheel 已通过当前 `q2_prepare_build.verify_wheel()` 的实际校验：metadata 固定到准确源码，
四包共 53 个 payload 文件、RECORD 摘要/大小、完整成员集合均一致。它仍是安装输入，不是现场安装收据。

Windows wheel 的代码 payload 相同，但 ZIP/metadata 字节不同，wheel 摘要也不同。
额外把 Windows wheel 输入 Linux fixture 的严格检查器时得到 `BUILD_DISTRIBUTION`：
其 METADATA 使用 CRLF，而该既有检查器要求相应 LF 字节。此结果已保留。
本次明确选择 Linux artifact，不改包、不放宽检查器，也不把两个 wheel 当成同一文件。

## 来源清单与安装重绑定

[source-alignment.json](evidence/systemd-cancellation-8b72306/source-alignment.json)
固定准确源码及其 146 个 host-loader Python pins、50 个 installed Python pins、74 个 admin pins
和关键入口摘要。它是源码/产物对齐材料，`is_runtime_fixture=false`，没有虚构主机路径或身份。

现有几个接口的字段不能互换：

| 接口 | 准确 source 字段 |
| --- | --- |
| `q2_prepare_build.install_candidate()` 真实安装收据 | `root, commit, tree, files` |
| `q2_prepare_assembly.assemble()` 输入 | `root, commit, files` |
| 嵌套 launcher fixture | `commit, files` |

实际装配时必须使用本次安装结果，更新 `installation.source_commit/files/payload_digest`、
admin `package_files`、`peer.runner.sha256`、查询的 `installation_digest`，以及由它们形成的
preparation、policy、request、assembly 和最终 fixture 摘要。不能只替换旧 fixture 的 commit。
安装路径、程序字节、解释器 device/inode 等仍由现场真实安装取得。

源码清单按既有规则保留了 `tests/e3_host/spikes/` 的 12 个历史 Python 文件。
这是来源库存，不是执行依赖；它们未进入 wheel，也未被正常 Q2 主链导入执行。
H07 实验 workflow 的 job 已禁用。

`q2_prepare_build.compile_native()` 中另一处既有编译属于固定目录 FD 的 quota 查询组件
`tools/admin/local_hand_quota_observer/quota_fd_query.c` 和 ABI 尺寸核对，不是已退役的
clone3 原生实验。本轮只读取其源码并固定摘要，没有编译、改写或运行这一组件。

## 当前能复用什么，还缺什么

| 项目 | 当前事实 | 下一步处理 |
| --- | --- | --- |
| 正常任务主链 | `q2_resident` 使用实际 Broker/SQLite/执行核心；`q2_launcher` 已串联 preflight→business→evidence | 复用，使用本次候选重新形成准确安装和现场声明 |
| 现场前检与证据复核 | `q2_fixture_check`、`q2_supervisor`、`q2_evidence_review` 已存在 | 保留原身份、原期限、完整退出和原流判据 |
| 真实取消场景 | 现有入口只支持正常链；没有触发 `broker.cancel` 的 case driver | 需要独立、固定的 test-only 取消场景，见下节 |
| 取消主体 | 现有 Q2 合成 policy/principal 只有 submit/read/evidence，无 `lh:cancel` | 新取消 fixture 须显式绑定同一 owner 的既有取消能力；不能修改旧冻结 policy 或伪造高权限 Principal |
| 现场环境 | 尚无与本候选匹配、可执行的新准确 fixture | 核对专用身份、父 cgroup、quota roots、实际安装、独立监督者和容量 |
| 旧来源材料 | 既有 11 项来源补证已有匹配结论 | 复用历史材料；不为相同缺口要求重采，变化项和运行时身份单独核验 |
| 旧单次运行 | 旧冻结 runtime、消费记录、截止和预算属于原批次 | 不因更新源码恢复额度、刷新 deadline 或重跑旧入口 |

因此，当前缺口不仅是提供一台机器：**正常链的真实环境装配未就绪，真实取消场景驱动也尚未实现。**
此前定向测试证明修复逻辑，不代表正常 Q2 harness 已经具备取消验收功能。

## 下一处代码工作：固定取消场景

在已批准 E3 quota/harness 的 Q4 故障验收范围内，先具体化下面的 test-only 入口及报告合同。
沿用现有产品 `broker.cancel`，不新增产品 MCP/CLI 命令，不向正常 `quota_bridge` 偷加消息，
不改变正常 `quota_closure` 对 ordinary 三单元及管理三单元完整关闭的要求。

1. 同一合成 owner、准确 operation ID/request digest，经真实 policy 授权后受理固定任务。
2. 透传真实执行核心的观察结果；只有准确 helper 的原实例已报告 RUNNING，且原期限仍有余量，
   才通知控制线程调用 `broker.cancel(..., {kind: job}, principal)`。不能用外部 StopUnit 代替该调用。
3. 保存取消请求、持久事件、原实例观察、实际停止及双流事实；继续使用原预算和资源账本。
   正常链和取消链使用分别核定的资源及单次操作，不能重用已消费根。
4. `CANCEL_REQUESTED` 持久点之后不得新增 reader 或后续业务的授权投递。
   此前已投递但未 ACK 的请求仍可能迟到；继续观察和停止准确原身份，未证明前不能宣称
   未来启动已经阻断。缺 reader/完整退出证据时，业务状态继续 UNKNOWN、容量继续占用；
   不能伪造缺失阶段来套用 `CHAIN_CLOSED`。
5. 场景报告分别表达“取消行为是否实际命中”“原进程停止事实”“证据/资源最终状态”。
   helper 在取消前自然结束时记录 `NOT_EXERCISED`，不假造阻塞、不自动循环重试。
6. 独立 test-only fixture/result 使用明确版本和 purpose，并与外层监督及离线复核准确连接。
   当前旧入口不接受这些尚未实现的新合同，本文件也不是其替代 decoder。

一次 RUNNING 观察、后续 UNKNOWN、StopUnit 请求或成功 ACK 都不等于实际停止。
命中本次取消回归必须记录：取消触发后、原 helper 仍非 terminal 时、原 deadline 前的
实际 stop 交付；stop 前已自然 terminal 的场景仍为 `NOT_EXERCISED`。
实际停止与完整退出另查原身份终态、无待处理 Job、准确父级树空、原客户端退出及双 EOF；
缺少任一必要事实就保留 UNKNOWN，不把“取消行为已测试”扩张为“全部退出已证明”。

这不是已完成取消 driver 的声明。具体接口、工作负载能否稳定覆盖运行中取消、费用和停止责任
还需在实现前核清；若需要扩大已批准权限、现场范围或更换架构，按原变更规则处理。
不为方便测取消而改变产品任务语义或放宽不明状态的处理。

## 进入实际运行前的唯一交接边界

下一份实际运行交接须一次固定：准确候选及 Linux wheel、安装记录、专用普通身份、
controller/ordinary/query/management 父级、真实 quota 与容量、独立监督者及外部停止所有者、
受保护配置/账本/输出位置，以及正常和取消场景各自的原始预算和使用次数。
现场先完成正常链验收，再运行取消场景；提前实现取消 driver 不改变这一执行顺序。

前检是当时观察，不是可复用启动许可；普通 shell 不能冒充已有监督服务的 MainPID。
本轮未执行 SSH、主机安装、用户创建、quota/cgroup 修改、真实任务提交或第三轮原生实验。
原 Q2 startup、Q3、生产资格、E4–E6 和 NAS 的未完成结论保留。

本文件和两个 JSON 是准确候选的交接检查点；后续文档提交不会把 CI 证据的 HEAD
从 `8b72306` 改成文档提交。若新增测试入口或修改源码，须建立新的准确候选和验证记录。
