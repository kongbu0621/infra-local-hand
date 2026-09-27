# Q2 监督器启动失败后的单次新运行：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- Scope：`LH-Q2-SUPERVISOR-STARTUP-RETRY-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；采用、可读来源、完整性、权限和变更规则沿用根 `AGENTS.md`。
- 本文、[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)构成待批准的准确文档基线 A。没有本 scope 的 Owner B 与独立 CLOSED C，不实现或运行本次新批次。

## 目的与保留事实

上次 `LH-Q2-CPUQUOTA-RETRY-v1` 已完成新安装和装配，发行了一次新的 owner 请求。
这次 systemd 已创建并执行监督器；监督器返回 `BLOCKED / PermissionError`、退出 3，
owner 报告 `INCOMPLETE / SUPERVISOR_DELIVERY_UNCERTAIN`。已回传原管理 client 和
owner 捕获的双流 EOF、退出 3；这证明完整捕获了一次失败，不证明 Q2 成功。
没有发布 invocation 声明或 seal，原独立停止记录为空。后来观察到外层服务和监督器
处于 FAILED、无剩余进程或 job、相关父树为空；target 未创建，新 ledger 保持初始化
generation 和空表，七个已准备根仍空。当前静止不能补写原停止记录或 seal。

这与再前一次 `CPUQuota=100.0000%` 被解析器拒绝、客户端退出 1、监督器未创建的
失败不同。两次已发行尝试、其准备/恢复来源与全部结果均保留，各自授权已消费。
现有源码修复处理真实排队启动状态，以及受限 Q2 角色对 PID 1 namespace 的访问假设；
原 guest 未返回准确 errno/调用栈，不能宣称已证明其具体失败 syscall。
已观察事实、源码诊断和验证边界见
[修复记录](../Q2_SUPERVISOR_STARTUP_REPAIR_VERIFICATION.md)。

目标是在同一隔离 guest 上使用固定修复候选、独立新状态及一次新窗口，完成原 Q2
固定三阶段的真实监督链验证。不重新请求不受影响的 CLOSED 开发范围源码修复授权，
不把新运行冒充旧尝试的续跑或补证。

## 范围与要求

| 编号 | 要求 | 可验证结果 |
| --- | --- | --- |
| S01 | 接受准确的双前驱失败链 | 原准备/恢复、CPUQuota 启动前失败和本次监督器启动失败的来源、计划、发行材料、流、结果及当前状态相互绑定；拒绝未知交付或错误失败类型 |
| S02 | 保留全部旧对象与结论 | 两次尝试的安装、policy/authority、ledger、journal、reservation、期限、报告、捕获及原 Q1/准备材料保持；无清理、退款、续期或追认 |
| S03 | 条件复用准确七根 | 同一普通账户/组、准确 manager/专用父 slice 配置、七根真实身份/限额/成员、两份历史 ledger 和消费材料共同证明可复用；任一不明即停止 |
| S04 | 准确候选和独立新对象 | 来源及 wheel 固定；新安装、policy/ledger、journal、session/control、声明和输出均 create-only；新身份与所有历史尝试去重 |
| S05 | 一次完整新批次 | 一次新 300 秒窗口包括首次探测、鉴证、安装、装配、固定三阶段、退出/EOF、独立停止和封存；不得自动重试或换名继续 |
| S06 | 空间累计、执行资源有界 | 历史实际占用、未释放承诺、新峰值暂存及最终证据同时符合原 byte/inode ceilings；本次新增时间/CPU 单列，内存/pids/输出不扩限 |
| S07 | 受保护身份与只读保全 | 管理员/owner 实际鉴证的同 boot namespace pin 经受保护来源传递；受限角色核验 self；历史读取 no-follow、noatime、无恢复或写入副作用 |
| S08 | 分层报告和严格验收 | 准备、发行、捕获、退出、停止、树空、seal、Q2 acceptance 分开记录；缺失或冲突保持 INCOMPLETE/UNKNOWN/BLOCKED |

本 scope 一次覆盖 C 后专用工具实现、负例和贯通验证、准确交付及一次实机运行，
范围内不逐项询问。只执行既有 `host.inspect`、空 inputs 和原固定三阶段，不提供
任意 shell、通用恢复入口或一般性 rerun。

## 准确候选

运行候选固定为 commit `b49d3df3d1e76813faf08e59ab4975e25279c2fc`，tree
`2d957ccf1d9cbdf5e538189c6b68d56f34590a42`；wheel 为
`infra_local_hand-0.2.0a1-py3-none-any.whl`，SHA-256 `c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b`。
准确来源、wheel 逐文件来源、隔离安装和修复验证须在 A 提交前完成并记录；文档基线
A 不保留未确定的摘要。以准确 commit 为准，不依赖可变分支指针。
C 后编排 D 单独固定来源与文件摘要，不动态改写或替换上述运行候选。

允许独立安装及新运行状态；准确已有普通 manager 或专用父 slice 仅处于正常
inactive 且配置与限制未变时，允许各一次有界 start，并记录当前 cgroup 身份。
禁止 restart、重写配置、改通用模板，或处理 failed manager、未知 job 和其他工作。
准确已知历史外层/监督器 FAILED 实例按原身份保留，不 reset-failed、重启或删除。

禁止新增账户/project、修改 quota、清空根、删除旧记录、回收 reservation、挂载或
重挂载、扩容、系统升级、新增系统依赖、增加 capability 或修改现役服务。
不包含 Q3 接纳、H06–H13、production、GX10、真实 NAS 或 E4–E6；不重新开启
S1 或 Ledger A2。production `E3_SUPERVISION_UNVERIFIED` 仍保留。

## 预算与关闭决定

空间沿用原总上界，按**全部历史与本次累计**计费：安装/source/build 暂存 256 MiB，
普通 state 和准备日志 32 MiB，管理 journal 64 MiB，捕获和声明 64 MiB。
这四类合计 416 MiB 不是本次新增额度。各类原初始化计划的 inode ceilings 原样
保留，不提高或重新分配。七个项目保持各 1 MiB/128 inode；四个 Q1 域的 196 MiB
保留承诺继续计入。唯一文件系统/project 硬限制只计一次；实际分配块、inode、未用
承诺和未来封存费用均可核查。剩余容量不足时 BLOCKED，不清理或扩上限。

新增外层窗口 300 秒，guest service ≤270 秒、准备鉴证/安装/装配 ≤140 秒、
owner ≤120 秒、stop ≤3 秒；内部沿用原更小角色限额。新管理服务 CPU≤300 秒、
内存 512 MiB、tasks 64；独立运行域本次 CPU 合计≤400 秒、内存合计≤1536 MiB、
tasks≤1024。两域分别计费并检查嵌套峰值。外部双流所有阶段合计≤2 MiB，内部
输出上限不扩大。同一绝对 deadline 留足 stop、EOF、fsync 和 seal 余量。

Owner 须在准确 R/A 上明确关闭本 scope，批准保留两次已发行失败、换用上述固定
候选、在全部条件成立时复用七根、创建独立新状态及一次新 300 秒批次。该 B 不改变
历史期限或结论；独立 C 只登记关闭。第二次新运行、候选再替换或实质边界变化需要
另有明确决定，不由本次失败或剩余预算自动推出。
