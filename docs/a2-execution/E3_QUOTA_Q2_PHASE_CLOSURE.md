# Q2 第四批：原进程退出、六阶段关闭和组合预检

日期：2026-09-25。本批完成六单元关闭合同、普通运行器双流采集、独立管理监督组件、
broker 阶段关闭检查及固定 fixture 预检入口。**Q2 整体尚未完成；真实整链 Q3/Q4 未运行。**
剩余工作包括受信管理端与常驻 broker 的双向桥接、固定 fixture 整链驱动及其外层采集。
生产 `E3_SUPERVISION_UNVERIFIED` 保留。

本批继承 `LH-E3-QUOTA-HARNESS-v1` 的隔离开发范围：R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、A
`415327ebdcc251bb055da9931a7a88990f750b7a`、独立 C
`5a4ea852091db06549a876e42bbd5f95d5869d3b`。本记录不改三份批准文档。
第三批历史状态见 [管理运行与绑定](E3_QUOTA_Q2_RUNTIME_BINDING.md)。
准确源码、最终回归、发布映射与 CI 在本批验证记录中另行保存。

## 已实现的行为

| 位置 | 本批行为 |
| --- | --- |
| `local_hand_jobs/quota_closure.py` | `local-hand-quota-phase-closed/v2` 绑定 bootstrap、helper、reader、query、collector、admission 六个原单元，三个原父树和完整证据摘要。缺项、身份变化、非真实布尔值、超期、父树占用均拒绝。 |
| `local_hand_jobs/quota_lifecycle.py` / `runner.py` | Q2 的三个普通单元都保存原 `systemd-run --pipe` 客户端。非阻塞读取 stdout/stderr；对同一 InvocationID 停止后，要求真实客户端退出码、两次 OS EOF 和原 cgroup2 父树为空。客户端被杀、只关闭管道、当前树空都不能补造原 EOF。 |
| `q2_runtime.py` | Q2 另外拒绝 ExecStartPre/Post、OnFailure/OnSuccess、RestartForceExitStatus；query 与管理单元共用这一检查。Q1 历史合同不改写。 |
| `q2_management.py` | 在独立、实际受监督的管理员控制器内，一次消费 listener/admission 启动意图，联合采集两条原管道，绑定两份 InvocationID，停止原单元并核实管理父树。外层控制器自身也计入有限管理预算。 |
| `q2_management.RunRecord` | 使用既有保护空文件的准确 dev/inode；独占锁、有界 hash 链和 fsync。先记意图再交付，原 DELIVERY/INVOCATION 各一次；缺同步、部分写、错误顺序或已消费文件均不重新开始。 |
| `q2_service.py` / `q2_journal.py` | 真实 Q2 admission 明确要求 v2 关闭。历史 v1 仍可读取，但不能满足新运行入口的前序关闭检查；旧记录不迁移。 |
| `broker.py` | 普通退出先写 `QUOTA_EXIT_PENDING`。可信内部 `close_observation` 核对原观察、原三次交付意图、普通退出和六单元关闭后，才写 `QUOTA_PHASE_CLOSED` 并推进 phase。释放前检查各原 phase 关闭。损坏快照不得重新生成已有事件。 |
| `tests/e3_host/q2_batch_check.py` | 一个显式只读预检入口：源码/模块/配置固定、原预算与父树、专用身份、既有空记录、实际管理员控制器一起核查。没有准确 fixture 时返回 `BLOCKED`/exit 3。 |

关闭合同的八项事实为 delivery settled、future start blocked、job empty、unit terminal、tree empty、
collectors stopped、stdout EOF、stderr EOF。每项还须具有原 boot、确定单元名、InvocationID、
cgroup、父树 dev/inode、观察时刻及原证据摘要。query 绑定原 receipt 中的身份与退出摘要；
bootstrap 绑定原已认证 peer；普通三单元绑定同一运行器保留的退出记录。
普通阶段关闭不延长原 phase deadline，管理阶段也不得越过原 request deadline。

## 管理组件的调用边界

`Management(installation, envelope, persist)` 首先复核其所在控制器的实际 UID/user namespace、
systemd InvocationID、父树和资源限制，以及两条独立匿名输出管道。它不创建控制器。
`envelope` 具有六个且仅六个字段：`controller`、`issued_ns`、`deadline_ns`、`output_bytes`、
`storage_bytes`、`storage_inodes`。其中 `controller` 使用现有严格控制器合同；
整个 envelope 是既有有限容量中的额外并发开销，不能从 query 额度隐式借用。

1. `begin()` 确认确定名称未占用、原管理父树为空，持久保存 INTENT 后仅启动 listener。
2. 调用方确认固定私有 endpoint 已就绪后，才能调用一次 `launch("admission")`。
3. 调用方在原绝对期限内调度有限 `poll()`；manager 命令仍有既有 32 次总调用上限、
   单次有界输出/时长及控制器总输出上限。单元尚未出现但原客户端仍运行时只等待原交付。
4. `finish()` 要求两份完整原采集和独立停止事实，再持久保存 CLOSED。
   `assemble()` 组合普通退出、原 query receipt、两份管理退出和三个父树的最后观察。

`assemble()` 是内部严格校验组件，调用方仍须认证其保护输入和证据来源。
它不会把普通请求给出的布尔值当成 OS 事实，也没有文件导入或公共 RPC 启用入口。
外层控制器本身的最后退出和输出，须由独立外层采集证明，不能由自身 CLOSED 自证。

## broker 与管理员账本

受信桥接的顺序是：普通退出持久保存 → 原管理单元关闭 → 管理 journal `close_phase` →
broker `close_observation` → 既有 phase 完成逻辑。两个 journal 不宣称原子提交。
中途崩溃保留已消费意图和原预算，禁止自动重新查询、补启动、换 InvocationID、退款或续期限。
broker 重启失去原传输所有权后，不从快照恢复一份可继续运行的关闭证明。

本批未交付实际双向桥接进程。`close_observation` 是内部受信方法；既无 MCP/CLI 路由，也不提供
普通用户可伪造的关闭通道。测试真实执行 SQLite 事务和阶段状态变更，OS 身份及管理结果明确建模。

## 一次组合预检

从准确、干净、受保护的源码安装目录运行：

```sh
python3 -I -B tests/e3_host/q2_batch_check.py --fixture /absolute/private/q2-fixture.json --sha256 FIXTURE_SHA256
```

此命令中的路径和摘要必须由已有私有 fixture 提供，不能直接复制占位值执行。
无参数运行可确认入口安装；它应报告 `EXPLICIT_PRIVATE_FIXTURE_REQUIRED` 并退出 3。

fixture 使用严格 `local-hand-q2-fixture/v1`，准确字段如下：

| 字段 | 原始输入 |
| --- | --- |
| `schema` / `purpose` | `local-hand-q2-fixture/v1` / `ISOLATED_Q2_CHECK` |
| `source_commit` | 该保护安装的准确干净源码提交，40 位十六进制 |
| `files` | 相对源码路径到 SHA256 的表；固定入口自身，以及 `tools/admin/local_hand_quota_observer`、`tools/local_hand_jobs`、`tools/local_hand` 下所有 Python 模块；至少 1、最多 512 项 |
| `observer` | 已有 `local-hand-quota-service/v1` 保护配置的 `path`、`sha256`；配置自身固定原 allocation、有限 grants、程序、源码和管理存储身份 |
| `ordinary` | 既有专用 `uid`、`gid`、`parent`；parent 为 `path`、`device`、`inode`，必须与认证 peer 和 work root 相符 |
| `controller_envelope` | 上述原控制器六字段 envelope；声明后还须通过运行中的实际 OS 检查 |
| `management_record` | 既有独立保护空文件的 `path`、`device`、`inode`；单链接、0600，与各安装/记录/作业路径不重叠 |

保护文件逐段 nofollow，要求 root 所有且无组/其他用户写权限；模块字节核验后才导入运行代码。
源码 commit 与干净状态另外核查。独立 host 检查在一份 JSON 中汇总；依赖输入失败则保持 BLOCKED。
预检成功也只表示 `CHECKED`：`q2_accepted=false`、`q3_status=NOT_RUN`、
`production_supported=false`。入口不创建账户、配额、挂载、socket、单元或 journal。

## 下一批直接接续

同一批完成下面三个相依项，不让用户逐个运行小探针：

1. 管理端与常驻 broker 的受信桥接：绑定准备记录、准确 bootstrap argv、有限原 grant 表、
   journal 关闭及 broker 关闭；保存原退出对象，不把新快照解释成新运行许可。
2. 固定 fixture 协调器：调度 listener readiness、一次 admission、实际普通三单元、管理停止及外层
   控制器采集；明确轮询/输出/存储上限。消费既有专用 fixture，不增设宿主 provisioning。
3. 在准确已提供的 systemd/quota 隔离 fixture 上组合运行正常链与故障场景，分别记录准确源码/
   安装身份、完整 IPC/EOF/退出、超时与恢复保留。当前执行器不具备该 fixture，不能记录实机 PASS。

历史 slot-001 UNKNOWN、slot-002 INCOMPLETE、slot-004 的限定成功和已消费容量分别保留。
本批代码通过不意味着 E3 生产准入或 GX10 部署。
