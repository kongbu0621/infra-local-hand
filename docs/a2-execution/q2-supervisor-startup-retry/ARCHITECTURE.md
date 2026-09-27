# Q2 监督器启动修复后单次新运行：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- Scope：`LH-Q2-SUPERVISOR-STARTUP-RETRY-v1`；R 与变更规则沿用根 `AGENTS.md`。
- [需求](REQUIREMENTS.md)固定运行候选、范围及预算；[实施方案](IMPLEMENTATION_PLAN.md)定义 R → A → B → C → D。

## 组件与信任边界

| 组件 | 职责 | 不能推导的结论 |
| --- | --- | --- |
| 外层批次所有者 | 首次探测前固定 300 秒；保留原 client、双流和一次 create-only 意图 | client 退出或 EOF 不等于服务已停止 |
| 双前驱只读鉴证器 | 绑定两次失败、全部来源、当前静止性、两份历史 ledger、七根与保留材料 | 目录空或当前树空不能抹去历史发行与缺证 |
| 容量与安装器 | 汇总历史占用/承诺和新峰值，独立安装固定候选 | 新 epoch 或空 ledger 不产生容量退款 |
| 新装配器 | 创建独立 authority/policy/ledger 和唯一身份，将七根关联到唯一新操作 | 新映射不代表配额根重建 |
| owner/supervisor/chain | 绑定实际同 MainPID 身份，执行原三阶段，保留退出、EOF、独立停止及 seal | 子级自报、收集完成或后续静止不等于 Q2 验收 |

新编排仅为 test-only 工具，不进入普通 wheel 或 Plugin。运行候选按需求固定，
编排 D 单独固定；不能以 monkeypatch、导入覆盖或现场源文件改写修改冻结运行行为。
原始机器材料、账户与路径、进程身份和私人运行计划留在私有交付，不进入公开文档。

## 双前驱准入与保全

新严格 schema 为 `local-hand-q2-supervisor-startup-retry/v1`，显式区分原准备来源、
CPUQuota 启动前失败和紧接着的监督器启动失败。旧 `local-hand-q2-cpuquota-retry/v1`
按其原语义保留；不能换常量后拿旧 NOT_FOUND/退出 1 条件接纳此次实际执行的监督器。
私有计划固定 scope/R/A/B/C/D、准确 candidate、全部历史计划/回执/报告摘要、两份
ledger、完整保留清单、新身份及路径、七根映射、设备和预算，拒绝未知字段、遗漏
前驱、路径别名、重叠、任意命令与未固定的来源。

首次持久修改前，必须同时满足以下条件：

1. 第一轮的准确 CPUQuota 解析错误、原 argv、退出 1、完整原流、未创建监督器及
   已发行 reservation/envelope/delivery 与原来源一致。不得重写为未发行。
2. 第二轮的 runtime/编排、prepared、原计划、reservation/envelope/delivery、
   `BLOCKED / PermissionError` stdout、退出 3、流 EOF/hash 和 owner INCOMPLETE
   报告一致；原缺失的 invocation、独立 stop 和 seal 如实保留。target 未创建及
   账本未消费由完整发行/输出/声明、实际 unit 状态和 ledger 联合验证，不能仅凭
   单一文件缺失或目录空认定。
3. 同 guest/boot 的历史外层和监督器为准确已知 FAILED 实例，InvocationID、终态
   和退出值与保留材料相符，当前无 MainPID/ControlPID/Job，相关父树无工作；
   target 没有创建。只允许这些精确列明的历史失败，不泛化为接受任意 failed。
   不能 reset-failed、stop/restart 或删 unit 来制造 NOT_FOUND；实际状态发生无法
   解释的变化即 BLOCKED/UNKNOWN。当前观察只证明当前，不补写历史停止。
4. 两份历史 SQLite 分别符合各自初始化回执的文件身份、权限、ledger_id、metadata
   和 generation；operations/events/leases/revocations/sqlite_sequence 全空。
   精确接受原合法自动索引和不可变 trigger，拒绝未知 schema、损坏、WAL/SHM/
   journal 或任何消费。所有历史 grant、发行及消费材料一并核对。
5. 七根逐项 dev/inode、owner/mode、文件系统 UUID、project/inherit、实际硬限额、
   使用量和成员符合原准备回执；七根全部无 payload/消费，不能混入已用根。
   已准备 store 根是预期结构，核验该根本身，不能把其父目录非空误判成消费。
   旧 collection 的空成员结果不能替代本次现场 quota 鉴证。
6. 账户、组、manager 和专用 slice 配置/限制保持，相关工作为空；所有 Q1、准备、
   恢复、两次运行、安装、账本及证据保持，原 byte/inode ceilings 能容纳新旧合计。
   在安装后、发行前再次核验；采样间身份、成员、摘要或静止性变化即停止。

历史对象的读取沿受保护祖先逐段 no-follow，核验实际 fd 身份、owner/mode 和
无别名；实际读取/枚举描述符保留 O_NOATIME。仅打开/stat、不读取或枚举的祖先
无需 O_NOATIME；实际叶项被拒时不得无保护重试。SQLite 从已 pin 的 O_NOATIME fd
有界读取原始 bytes 并计算原摘要；仅在 RAM 副本将合法 WAL header `2/2` 转为
`1/1`，使用内存 `deserialize`、`query_only`、`trusted_schema=OFF` 及受限 schema
检查。SQLite 不打开任何历史路径或 `/proc/self/fd` 路径，不创建 sidecar、修复或
迁移；读取前后核验 sidecar、fd/文件身份和内容摘要。无法无副作用鉴证时保留 BLOCKED。

## Namespace 与新对象

管理员准备和 owner 入口先真实比对 PID 1 与 self namespace，与准确同 boot 的
初始 namespace pin 一致。该 pin 由已校验来源、受保护安装配置和 envelope 摘要
传递。受限 supervisor、fixture checker、launcher、management 和 runtime 在
各自准入后，核验实际 self namespace 与 pin，以及观察前后的同 boot；保留真实
UID、MainPID、InvocationID、cgroup 身份、manager 限制、独立 pipes 和期限检查。
不由受限进程 self 推导新的 initial pin，不忽略 namespace 读取失败，不增加
ptrace 或其他 capability。owner 的双 namespace 鉴证与原 Q1 guard 保留。
pin 的保护链不能依赖调用方布尔值或未经保护的声明。

新 source/runtime/native 安装、authority/policy、broker state/SQLite、journal、
session/control/endpoint、声明、输出和批次 reservation 均独立 create-only。
新 attempt/operation、ledger、deployment/installation、epoch/session/query/
management request 及 unit 名，须与所有历史来源的身份集合去重，不能只检查原
preparation。新 authority 绑定本 scope R/A/B/C/D、原准备、两次失败、双 ledger
未消费鉴证、七根真实映射和唯一新 operation，形成完整 `supersedes_failed_attempt`
链；不改写前驱 authority 或 ledger。

状态为 `DECLARED → ATTESTED → RESERVED → INSTALLED → ASSEMBLED → ISSUED → RECORDED`。
每个副作用前保留 intent；排他 reservation 只允许一个赢家。中途失败保留实际
完成边界及全部材料，不回滚、不删后重建、不换 ID、不自动续跑。新请求发行前
再次检查容量、期限、历史保持与空树/空账本；合作性锁不能替代真实状态核验。

准确已有普通 manager 或专用父 slice 仅正常 inactive 时，可各一次有界 start，
保留 intent/result 和新 cgroup dev/inode；不伪称旧 cgroup 身份未变。failed manager、
配置变化、未知 job、其他工作、需 restart 或新增范围外对象均阻塞。历史 FAILED
外层/监督器不进入这条 start 分支。

## 累计成本、剩余窗口与验收

各类原 ceiling 与 inode ceiling 不变。对每份历史 reservation 显式列出实际占用、
其中已覆盖的承诺及仍未覆盖的承诺；本次另列实际与未来承诺。剩余可用量由原类目
上界扣除这些累计费用得出，不能只扣最新一次或把每轮 416 MiB 当新增额度。
同一文件/费用按真实 dev/inode 和归属去重，同一文件系统/project 硬限制只计一次；
既不能重复收费，也不能用小的当前占用冲销未释放承诺。安装构建峰值、源/wheel/
runtime 共存、块/inode、最后的报告/诊断/封存和未完成输出均纳入。
各设备实际剩余容量仍须覆盖其所属全部保留承诺；缺容量不发行、不清理、不扩限。

新窗口在首次只读探测前固定，host/guest 采用一次往返保守绑定，不直接比较两台
机器的单调时钟。guest 入口首次读取前固定准备阶段期限；预检、装配、owner、
停止、捕获和收集都消费同一原始窗口。owner 发行时须容纳实际剩余 owner、stop、
EOF/fsync/seal 余量；静态 140+120<300 不能替代绝对 deadline 准入。
原运行域及管理域分别检查 CPU、memory、pids、输出和嵌套峰值；只读收集同样计费。

原 client 双 EOF/退出值、guest 结果、原 owner/child 身份、独立停止、树空、各级
seal 和历史保持分别记录。非零退出与双 EOF 是完整捕获失败；collector 完整性只
说明已收集，`RECORDED` 只说明已保留。Q2 验收必须另满足原 Q2 合同和本次完整
原进程证据。后来的树空、新一次成功或新 seal 都不能补判两次旧 INCOMPLETE。
收集缺项、超限、超时或流错误显式标记；不能截断后声称完整，也不能另开窗口补封。
