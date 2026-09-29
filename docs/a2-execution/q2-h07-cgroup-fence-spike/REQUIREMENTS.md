# H07 受控进程子树原语实验：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- Scope：`LH-Q2-H07-CGROUP-FENCE-SPIKE-v1`，仅 F1–F4 隔离实验。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接原件与完整性沿用根 AGENTS。
- 输入仓库基线：`7392575c8d78899f8f7d31e64c5de145e0f24855`。
- 配套：[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)。准确 A 由包含三份确定文档的提交给出；尚无本范围 B/C/D。

## 问题与这一步的价值

固定 Q2 链把启动请求交给外部 system manager。客户端超时、错误应答、退出和
一次树空都不能证明该请求不会后来激活；已有 broker 的 guard 也未覆盖这些调用。
见[准确源码复核](../Q2_H07_PENDING_REQUEST_SOURCE_REVIEW.md)。

本阶段只验证一个具体替代原语：**把所有合成任务的启动者也放入同一受控子树，
直接通过内核创建任务，由子树外的独立监督者关闭入口并停止整个子树。**
关键验证对象是尚未返回身份的创建、并发 fork 和启动者崩溃，而非另一个纯状态模型。
内核接口有文档支持，不等于这个组合已实现或经过验证。

本实验的消费者是后续 H07 架构评审。结果可否定候选，或说明准确 fixture 中的
局部能力；不能自动接入 Q2。它确实改变执行权威及生命周期机制，不能冒充原
CLOSED H4 的常规测试，也不改变原 H 的历史三文档或关闭决定。

## 范围与验收

| 编号 | 要求 | 可核验结果 |
| --- | --- | --- |
| F01 | 固定可丢弃 fixture | 仅 GitHub 托管 `ubuntu-24.04` x64 单个临时 runner；记录 image/kernel/tool/source 身份并核验 cgroup v2、权限及 syscall；不满足为 UNSUPPORTED，停止有副作用病例 |
| F02 | 全部启动者受控 | 单个固定 launcher 与全部合成后代均位于 generation 子树 B；没有向外部 manager/服务转交请求的路径 |
| F03 | 创建时已入组 | 使用 `clone3(CLONE_INTO_CGROUP | CLONE_PIDFD)`；无先启动再迁移的回退；取得准确 cgroup FD 与原 pidfd |
| F04 | 关闭状态不可倒退 | `CLOSE_REQUESTED` 停止接收；只有 launcher 原身份退出、B 树空及原流事实齐备才记录 `FENCED`；cgroup.kill 本身不被称为永久锁 |
| F05 | 缺身份仍不漏清理 | 丢失启动应答不能按未启动处理；可通过整树清理，但逐实例身份/结果未知仍保留未知，不用复用 PID 补证 |
| F06 | 原时钟与有限收尾 | guardian 在启用提交前固定本机双钟，每例 20 秒含最后 3 秒停止观察；迟到、超限、控制者丢失均拒绝或 UNKNOWN，不刷新同例时钟 |
| F07 | 独立证据 | 原 pidfd、cgroup 实物、原 stdout/stderr EOF 与 guardian 退出分别核验；外部 cleanup 不回填已经丢失的 seal |
| F08 | 严格局部结论 | 六个固定病例含失败对照；结果不生成 Q2 READY、生产许可、原批次消费或完整账单资格 |

只运行本实验源码中的固定合成角色，无 shell、任意 argv、上传任务、外部请求、
原 wrapper/凭据/VM/业务输入。launcher 和 guardian 属于受审可信控制程序；
worker 用于有限故障注入，不把此原语宣称为任意恶意原生程序的完整沙箱。
专属低权限实验 UID、无附加组、capabilities 清空、NoNewPrivileges 和限定 seccomp
关闭已知 manager/namespace/FD 逃逸入口；NNP 单独不证明已有 IPC 授权被撤销。

## 明确的新授权范围

准确关闭仅允许：本仓库内独立实验实现、非特权离线测试、独立手动 CI workflow，
以及最多三轮托管 runner 验证（首轮与至多两轮有明确源码修复理由的复验），
每轮六病例各一次，最多 45 分钟 job 配额。runner 的 root setup 只创建本实验专属账户、
cgroup 分支和临时输出目录，配置其子树限额；不修改共享 root 控制器、SSH、
systemd、journald、宿主账户策略或安装服务/软件包。
实验结束只清理登记的本次对象；不借失败清理执行新工作或自动重跑。
每轮准确 D 发布后由 executor 在 GitHub 页面触发 `workflow_dispatch`，无 push/PR
自动运行和定时运行。页面不可访问时保留“未派发”，不要求用户搬运终端输入。

原 R/H/startup/reconciliation/K/L 的 A/C 均保留；新范围为独立 spike，未授权：
替换冻结 runtime、原机/guest 调用、原 batch 消费、预部署 guardian、扩费用或
重做已完成补证。后续采用实验代码或改变真实执行链，须另有准确方案和决定。

## 资源与故障边界

- 单个 CI job 最长 15 分钟；准备/编译 120 秒、六例共不超过 180 秒、清理 30 秒。
  job 超时只是托管设施后备，不是已证明本实验任务停止。
  准备阶段包含唯一能力 probe 的 20 秒子窗口（最后 3 秒停止观察），不额外加时。
- 实验共同 cgroup E：memory.max 128 MiB、swap 0、pids.max 32、CPU 速率不超过一核。
  guardian 叶 G：64 MiB/4 tasks；工作子树 B：64 MiB/16 tasks；每例至多 8 个 worker 后代。
  限额相加仍受 E；cpu.max 是速率，另记录实际 cpu.stat，不冒充累计 CPU 硬上限。
- 合成 worker 不写普通文件；每例双流合计至多 128 KiB，六例至多 768 KiB。
  probe/setup/编译/cleanup 的诊断另合计至多 256 KiB，不将大段原流打印进 job 日志。
  主报告至多 2 MiB；构建/证据目录普通文件合计逻辑不超过 32 MiB、128 项。
  记录实际 blocks/inodes，逻辑界不冒充文件系统分配峰值。
- 托管 runner、编译器、setup 与原生日志属独立实验基础设施成本，显式不纳入
  原 Q2 的 64 MiB capture/64 KiB marker 池，也不以此实验声称原账单通过。
- 可信 fixture root、内核与外部收件器必须声明；不承诺任意宿主停摆、不可中断
  I/O 都在 3 秒消失。不能确认则 UNKNOWN、停止后续病例，保留残留和超时事实。

当前云执行器已只读确认 cgroup 只读、无有效 capabilities、PID1 非 systemd，
不作为这个真实实验 fixture。托管 runner 的标签亦不是能力证明；F1 首先实录核验。

## 完成定义与待决定项

完成定义为准确实现 D、六例各自事实与缺项、失败原件、资源记录及可追溯报告。
`QUALIFIED_IN_FIXTURE` 必须满足所有预期判据；UNSUPPORTED、UNKNOWN 或未运行
均不能改成资格通过。某个故障对照按预期返回 UNKNOWN，只表示负例判定正确，
不表示该次停止/EOF/seal 成功。

需要 Owner 决定的只有上述 F1–F4 新实验范围及最多三轮手动 CI 的有限额度。
范围内修复与剩余额度内复验不逐次请求批准；全部失败记录保留，不无理由重试。
真正的 first-remote 保护、跨钟、冻结角色接线、FS 资格和完整账单仍留待后续方案；
实验即使成功，也不会使这些问题自动成立。
