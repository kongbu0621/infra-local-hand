# 核心容量单次观察需求

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Authority：Owner。
Scope `LH-Q2-CORE-CAPACITY-OBSERVATION-v1`，仅 O1–O3。
本文、[架构](ARCHITECTURE.md)、[计划](IMPLEMENTATION_PLAN.md)组成待批准 A。
R 仍为 `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，直接来源、完整性、Owner mandate、
无例外及独立 R→A→B→C→D 顺序沿用根 AGENTS；本提案不记录新的 Owner B。

## 要解决的问题

源码基线 `128f72d0864dd631df4941c1a453ef436221f3db`，tree
`2322ba42f34b66af6aa292103032e8bccc873920`。其容量诊断已修复、准确 CI 37336643512 成功。
[离线核算](../Q2_CORE_CAPACITY_DIAGNOSTIC_REVIEW_20261005.md)已验证固定分量及 15 种角色分组；
没有当前 guest 可用量。[已消费 05c](../Q2_CORE_POST_LOCALE_ACCEPTANCE_REVIEW_20261005.md)
在容量准入返回 `CORE_CAP_INSUFFICIENT`，尚无 H01/Q4/H11 verdict。

本次唯一目标：一次读取原计划五个 parent 的设备身份和可用 bytes/inodes，按既有 05c 冻结
容量合同输出各设备的历史、05c 增量、合计门槛和缺口。它是**当前观察与条件比较**，不复原
05c 当时的可用量，不作为完整 core admission，也不新增第五个业务批次。
03a、05a、05b、05c 和既有 sshd 诊断均已消费；其完整承诺、原件、UNKNOWN 和空发行 allowlist 保留。

## 对象、固定输入和输出

复用现有 Q1 管理 anchor、账号 `q1admin`、回环入口 `127.0.0.1:22221`、原私钥和固定 host key。
原安装、runtime、wheel、harness 不变。新诊断 ID 固定 `lhqcap-20261006a`；不接受改名重试。

仅允许以下五个 parent，路径从原始 plan 的准确 9814 B、SHA-256
`efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c` 推导：

| 角色 | 原始 plan JSON pointer | 推导 |
| --- | --- | --- |
| state | `/directories/state/path` | `posixpath.dirname` |
| quota | `/mounts/quota/path` | 原值 |
| install | `/candidate/destination` | `posixpath.dirname` |
| journal | `/mounts/journal/path` | 原值 |
| evidence | `/mounts/evidence/path` | 原值 |

映射以实际已发 `657b1bcd749cb4281b0193b2bc9430b0662faf98` 的
`tests/e3_host/q2_core_delivery_freeze.py:LOCATOR_MAPPING` 为准确依据。
只接受原 absolute-path 验证再加本次长度上限；不接受用户任意指定 guest 路径。
原计划与映射足以绑定本次读取意图，不冒充完整 approved-input/package 重建、当前设备身份
或完整历史证据链复验。已有保存的 05c manifest 可额外比对，但不要求重新生成已消费 package。

允许读取五个目录和必要祖先的元数据、持有目录 fd 的 ext4 UUID、`fstatvfs`、固定内核
`/proc/self/mountinfo` 和对应 `/proc/self/fdinfo/<fd>`。不枚举目录、不读取子项内容，
不打开 block device，不查询项目配额、历史对象、SSH 配置、进程/cgroup 或业务结果。
解释器/SSH/sudo 的既有运行时读取不计作新的业务数据采集范围。

私有结果固定五行，记录角色、采样时间、目录及挂载身份、原始 statvfs 数字和计算可用量。
公开报告仅角色组、设备身份摘要、AVAILABLE/HISTORICAL/05C/REQUIRED/DEFICIT；不公开路径、
原始 UUID、凭据或配置。完整且全部校验通过才记 `CURRENT_CAPACITY_OBSERVATION`；
阈值计算记 `CONDITIONAL_05C_THRESHOLD_COMPARISON`，不能记 ADMITTED 或业务 PASS。

## 限额与一次性规则

| 项目 | 固定边界 |
| --- | --- |
| 新源码规模 | reader ≤32768 B，runner ≤65536 B，无第三方依赖 |
| 路径描述 | 五个角色，单路径 ≤512 ASCII B、≤16 个组件；描述 ≤8192 B |
| 传输 | 固定 remote-command 参数传 reader/描述；本地 argv+env ≤65536 B；stdin EOF |
| 内核数据 | mountinfo 前后各 ≤1048576 B；每个对应 fdinfo 每次 ≤4096 B、最多十次 |
| 返回 | stdout ≤65536 B，stderr ≤65536 B；超限截停，不无限排空 |
| 新私有 capture | 固定四件；完整承诺 4194304 B / 8 inodes，不能按实际小文件退款 |
| 当前 host 可用条件 | 同一 capture 设备 ≥276824064 B（264 MiB）/80 inodes |
| 本地窗口 | 首次 O3 现场本地预检读取起，同一 monotonic/boottime 最多 60s；55s 停止点，余下 5s 封存；ConnectTimeout 10s |
| reader 限制 | 初始化后一次 20s alarm；CPU soft/hard 各 5s；AS 128 MiB；NOFILE 128；FSIZE 0；CORE 0；无子进程 |
| 请求数 | 最多一次 O_EXCL marker、一次 SSH exec；ConnectionAttempts=1，无 reconnect |
| 本地结论 | 完整回收后最多一次纯本地计算，≤5s；无新增远端操作 |

264 MiB/80 是四旧核心各 64 MiB/16、已消费 sshd 诊断 4 MiB/8、本次 4 MiB/8 的相加。
这是当前可用量检查，不是排他预留或全部更早历史容量证明；更早 host UNKNOWN 保留。
本提案请求 Owner 接受这些缺口不单独阻断这一次固定诊断；不据此放行核心业务。
4 MiB 是应用写入和实际分配观察边界，不宣称共享设备全程物理硬限额。

任一新固定文件已存在即停止。marker 一经创建永久消费，包括部分写入或未发出 SSH。
marker 前允许仅本地预检；同一 winner 不刷新时钟。失败后不换名、补采、清理、退款或重试。

## 保证边界与完成标准

这是指定数据的只读观察；现有 SSH、sudo/PAM、审计、解释器可能有日志/访问时间等副作用。
沿用固定 endpoint、host key 和现有 sudo/Python 信任，不新增 HELLO、运行时 attestation、
有效 SSH 策略或旧进程静止证明。reader 限制不覆盖其初始化、SSH/sudo/PAM 祖先或全机资源。
只停止本调用拥有的本地 SSH 子进程；alarm/信号不能保证不可中断 I/O 或远端祖先按硬时限退出。
正常 wait/双 EOF 不是远端独立监督闭合；不能确认时如实记录 UNKNOWN，不再连接核实。

五个 parent 的当前采样不是原子全机快照。实际历史 placement、当前 configured quota/enforcement
和旧进程闭合均 **UNVERIFIED**；条件计算假定原冻结合同仍适用，不能把未读取的事实记为已验证。
发现身份漂移、state/install 不共设备、格式/权限不符或额外已知证据矛盾则停止，不自行采用新布局。
可用量变化本身不等于身份漂移，共池取各角色采样的最小可用值并保留时间差。

O1 实现，O2 窄离线验证与冻结，O3 条件单次观察和报告。
完整结果要求固定身份/输入/结构/摘要校验、exit 0、双 EOF 和原窗口全部满足；否则保留部分原件，
报告 PARTIAL/FAILED/UNKNOWN。即使各池当前足额，也不授权 H01/Q4/H11 或未来批次。
不重装、不改 SSH/容量/配额/权限，不开新 unit、不执行业务、不清理历史。
所有支线暂停，production `E3_SUPERVISION_UNVERIFIED` 保持。
