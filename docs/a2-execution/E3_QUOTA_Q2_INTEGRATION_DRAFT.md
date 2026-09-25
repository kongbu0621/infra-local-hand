# Q2 接口、绑定、预算与恢复：接线设计草案

日期：2026-09-25。状态：**DRAFT / DESIGN ONLY，Q1 出口待容量来源核对，尚未开始 Q2 实现**。

本草案细化已批准的 [QH 架构](e3-quota-harness/ARCHITECTURE.md)与
[实施顺序](e3-quota-harness/IMPLEMENTATION_PLAN.md)，不替换权威 A/R/C，
不创建模块、服务、配置、fixture 或运行请求。当前进展见
[Q1 收口清单](E3_QUOTA_Q1_CLOSEOUT_REVIEW.md)。
源码核对基准：`32852f28b4edefb7acd1b5c6562cecc29524637d`。

## 已核实的接线差异

| 位置 | 现有行为 | Q2 必须明确解决的差异 |
| --- | --- | --- |
| admin/supervision.bind_query | Q1 execution_id 为 32 位 hex，一次绑定一个 Slot | 作业 execution_id 为 namespace-record-phase；不能截断、隐式改名或直接套用 |
| bootstrap_roots.validate_grant | 三个写根，evidence 阶段最多加一个 retained store；business 继承 preflight 分配 | Q2 必须覆盖完整 3–4 根集合及跨阶段原分配关系，不能只证明一个目录 |
| admin/journal.StartJournal | Q1 对 request/allocation/slot/root/domain 永久消费；同步持久化可能阻塞 | 不能直接充当多根、多阶段服务账本；不能换目录绕过原 UNKNOWN |
| bootstrap.prepare | 普通隔离身份逐根直接执行 generic quota 查询，随后按 source/project 去重 | 改为本地 FD 身份/继承检查加受认证事实消费；域键应为已证明的 FS UUID/project |
| budget.substage_limits | supervision v2 为两阶段，v3 为三阶段；观察器无管理分额 | 新管理开销独立有限记账，墙钟仍消耗原 bootstrap/phase 窗口；不能多领三段预算 |
| runner._properties | 原三单元已有 PrivateUsers/PrivateDevices/NNP 和写路径限制 | socket 只对准确 bootstrap 可见；只读目录不能被当作连接拒绝证明 |
| runner._inspect_unit | 基准代码曾按缺失叶 cgroup 和 inactive/failed 推导为空；本轮本地已改为 UNKNOWN 并阻止后续交付 | 完整父树身份和退出证明仍需在接线前整合；保守拒绝不等于已补齐成功证明 |
| state/broker/runner | 既有 v2/v3 监督记录和 root/budget grant 有严格字段与版本 | 新字段必须显式版本化；旧记录不补成功回执、不重新查询或升级后启动 |

这些差异来自当前代码，不是额外扩展需求。业务执行入口、六类 job、七个公开接口和生产
`E3_SUPERVISION_UNVERIFIED` 保持原合同。

## 第一批先固定的合同

新内部请求建议使用 `local-hand-quota-observe/v1`。网络可见部分最大 8192 字节、JSON 深度 4；
只接受 observe 和以下固定字段族。全部 scalar 为精确类型，未知/重复字段、浮点伪整数、
数值溢出和未知版本拒绝。最终精确键集合须在编码前作为同一合同与测试向量固定。

| 字段族 | 绑定对象与来源 |
| --- | --- |
| schema、operation、request_id | 固定版本/observe；原管理分配已固定的一次请求身份 |
| authority_digest、installation_digest、manifest_digest、epoch、boot_id | 事前准入的管理配置和部署代次；不信任客户端自报即可放行 |
| slot_ref、generation | 管理 manifest 的有限逻辑 slot；服务端映射整个 3–4 根集合 |
| execution_id、phase、allocation_digest | 保留完整作业执行 ID 和原 root grant；与服务端受保护的准入原件一致 |
| observation_grant_digest、deadline_boottime_ns | 原管理额度、原预算和绝对截止时间；客户端只能收紧截止时间 |

客户端不得发送路径、device、project ID、能力、期望 hard limit、argv、代码或 FD。
socket ancillary FD 必须被拒绝并按有限规则关闭已接收描述符；它不能成为绕过固定 roots 的入口。
服务端不能因为 allocation_digest 的格式正确就承认资源授权，必须有独立受信的对应原件。

响应建议使用 `local-hand-quota-receipt/v1`，不超过 32768 字节。包含原请求和 grant 摘要、
原 issued/deadline、观察起止、准确 source/install/boot/epoch、所有根与唯一配额域、每次 syscall
原 rc/errno、query unit/InvocationID、采集/退出引用、缺失事实和诊断原因。
Q1 的 128 KiB 私有 experiment 输出不能直接作为此响应。将多根原报告与证明引用组合后必须
实际验证最大编码尺寸；超限保留失败，不截断成成功，也不扩大响应上限。

请求重复读取原记录仍使用相同 observe 绑定；不提供 retry/reset/setquota/release 动作。
历史 OBSERVED 记录可以作为原历史读取，但过期或不同 boot/epoch/phase 的事实不能供当前 bootstrap 放行。

## 多根与跨阶段决策

一个作业 slot 包含 work/evidence/temporary 三根；evidence 阶段最多一个额外 store。
管理侧映射应使用显式的新版本组合 manifest，保留每根逻辑角色及完整 host 身份。
Q1 单根 manifest/native ABI 保持历史语义，不把三个互不相干的单根成功拼成未经绑定的整体成功。

首选候选是在一个已登记的 query unit 中，以固定有限根集合执行有界观察；需要在 Q2 实现前
审阅 FD 布局、逐根前后身份复查、参数级 seccomp、失败即停止后续 syscall 和整体 deadline。
不得把根数变成客户端参数、对每根无限派生 unit，或给普通 bootstrap 增加 host 权限。
若无法在原 32 KiB/管理额度内完整证明整个集合，整体拒绝，不只验部分根。

作业侧完整 execution_id 与管理侧内部观察身份分开保存，建立不可变一对一映射。
若复用 Q1 需要的 32 位内部身份，由受信分配方事先分配并持久化，不能从客户端任意覆盖或仅截断完整 ID。
原请求、完整执行 ID、原 root grant、phase 和内部观察身份全部参与绑定摘要。

业务阶段复用同一操作的原 root allocation，是既有 bootstrap_roots 语义；不等于释放后重新分配。
Q2 账本须区分永久资源所有权、每阶段一次观察意图和当前活动观察：

- 同 request 与同绑定只返回原记录；异绑定冲突。
- 同 allocation 任一先前观察或相关 writer/collector 的退出仍未知时，不准入新观察。
- 同一原操作推进到下一阶段，须由 broker 原持久阶段围栏和新阶段预算共同授权，并保留前阶段原记录。
- 其他 operation、改 generation、改 journal 或重启服务不能取得原已消费资源。
- 旧 Q1 UNKNOWN/INCOMPLETE 的对象没有新 broker 分配来源，不能转成 Q2 可用池。

服务账本作为显式 Q2 版本设计；共享查询/退出核心只在先持久意图的受信边界之后被调用。
不得每次新建一个 Q1 journal 来取得可再次交付的假象。

## Peer、socket 和阻塞边界

bootstrap 校验预先固定 endpoint、受保护目录及服务 OS peer；服务校验 OS peer 与该原分配
允许的 bootstrap 身份。相同 UID 不能单独区分 bootstrap、helper 与 reader，须结合准确阶段围栏
和实际入口隔离。私有 user namespace 下的映射必须在目标 fixture 取证，不直接比较两侧自报 UID。
PID 存在、socket 路径只读、摘要相等都不是独立的身份认证。

listener 在准入时预加载有限管理表，使用有限连接数、请求/响应字节和绝对接收窗口。
listener/broker 控制线程不执行目标 FS 读取、fsync、quota syscall 或可能阻塞的 manager 命令。
需要 I/O 的准入、持久化、查询和恢复交给具有独立预算/监督的固定工作对象。
工作对象卡住时拒绝后续同域交付并继续提供有限失败响应，不派生替代 worker。
服务重启只恢复原持久状态；无法完成有界恢复时关闭新准入，不能空表启动。

固定 fixture 交接必须同时列出 socket 可见性、允许 peer、启动器和全部监督对象的停止入口，
并实测 helper/reader 无法连接。client 连接的 peer 变化、半包、超量、断流、服务退出分别记失败。

## 原预算与封存峰值

所有容量都在相关交付前记入准确原件。管理预算独立于业务三段分额，但仍进入全局总量：

`全局占容 = 唯一业务配额域保留 + 管理控制记录上界 + 日志/原件上界 + 同时存在的封存副本上界`

计算须明确 FS 分配粒度、文件数量/inode、目录和元数据，以及压缩前后同时存在的副本；
原 UNKNOWN 和已保留历史仍计入。不同名称映射到同一 FS UUID/project，只计算一次相同硬限额；
相同域的额度声明矛盾即拒绝。当前空闲量不能退款；查询不写业务 payload 也不能按零成本计费。

建议新 observation grant 固定：原 job/root/budget grant 摘要、完整执行和 phase、管理分配 ID、
各管理监督对象的 CPU/RSS/pids/输出/时间限制、全局容量原件摘要、接收与停止保留量、
issued_ns 和绝对 deadline。单位均显式，整数运算溢出拒绝。
实际值由该原分配交付，不由客户端建议或超时后重算。

观察完成并停止的时刻必须在 `min(原 phase deadline, 原 bootstrap 窗口, 管理 query 上限)` 内。
独立管理清理可以保留失败证据，但不续原请求期限、不恢复其成功资格。
既有 v2/v3 分额和记录原样保留；需要新字段时采用独立内部版本，不用可选字段绕过原严格校验。

## 状态与恢复规则

| 持久状态或断点 | 同绑定再次到达 | 后续行为 |
| --- | --- | --- |
| 未准入、无持久意图 | 完成全部准入才可能进入下一步 | 没有管理授权不发起查询 |
| 意图持久化完成，交付结果未知 | 返回原 UNKNOWN/未完成事实 | 不补投、不依据“没看到单元”推导未执行 |
| 原 InvocationID 已记录，进程未确认退出 | 返回原绑定 | 仅有限观察/停止原身份；保留额度 |
| query 已退，launcher 或 EOF 不完整 | 返回原不完整记录 | 不重新打开新管道、不重新查询补输出 |
| 原完整成功 | 返回原不可变 receipt | 仍须当前执行/phase/代次/期限匹配才可消费 |
| 同 request 异绑定、同资源异 owner | 返回冲突 | 保持原对象和账本，不重分配 |
| broker/observer 一方提交后失联 | 保留两边原意图及差异 | 无分布式原子性假设；不跨账本自动退款 |
| boot/epoch 改变、损坏或记录缺失 | 关闭对应新准入 | 不以迁移、空目录或新 ID 消除原不确定性 |

退出证明必须含原 boot/unit/InvocationID、原 launcher 的交付已结束、无排队启动、重启/激活围栏、
被固定身份的完整父树为空，以及所有 collector/client 与管道关闭事实。
共享 runner 本轮已保守拒绝缺失叶 cgroup 的退出判断，回归证据见
[Q1 收口清单](E3_QUOTA_Q1_CLOSEOUT_REVIEW.md)。后续仍须补齐完整证明，才能据此放行下一阶段。

## 按风险合并的验证矩阵

| 组 | 必须覆盖的正反例 | 证据类型 |
| --- | --- | --- |
| 合同 | 精确边界与多字节 UTF-8；超长/深度/重复/额外字段；bool-as-int、溢出、未知版本；请求内路径/FD/argv | 纯解码与真实有限传输 |
| 来源 | 错 peer/同 UID 错角色；endpoint 替换；boot/epoch/安装/manifest/generation 任一不匹配 | 合成负例 + 实际 socket/namespace |
| 多根 | 3 根及第 4 根；漏根/多根、身份互换、共享域去重、矛盾额度、mount 别名/根替换；响应最大尺寸 | 纯映射 + 独立实际根绑定 |
| 分配 | 完整执行 ID 映射；错 phase/grant；business 原分配继承；同域不同 owner；旧 Q1 保留对象拒绝 | 实际持久记录 + 合成状态机 |
| 预算 | 原 deadline 不延长；墙钟/CPU/日志重复计费；管理预算耗尽；保留峰值含临时副本/UNKNOWN | 纯预算 + 原预算下真实执行 |
| 防重 | 同绑定并发到达、异绑定冲突、意图前后崩溃、交付/ACK/响应丢失、服务重启 | 持久化和真实进程/管道 |
| 退出 | 原 unit 正常退出、信号退出、client 仍活、单流缺 EOF、叶树被清除、父树缺失/换身份、有排队激活 | 管理适配器负例 + 实际 systemd |
| 隔离 | bootstrap 准入且 helper/reader 无法连接；普通身份保持 PrivateUsers/PrivateDevices/零能力 | 准确目标 fixture 实测 |
| 阻塞 | 目标 quota/控制持久化 I/O 等待时有限响应；无替代派生；取消后原身份保留 | 有可解除入口的真实故障；sleep 不替代内核 I/O |
| 兼容 | 旧 v2/v3 仍按旧语义恢复/停止；未知新版本拒绝；Task v1/MCP/CLI 无静默扩展；支持封堵保持 | 相关旧链回归与分发包边界 |

LOGIC_ONLY、真实 socket/pipe、真实 systemd/quota、BLOCKED 分开报告；不按测试总数覆盖未做实测。

## 编码批次与一次实机交接

Q1 通过后，先完成合同和测试向量、多根/跨阶段状态、预算与版本设计的同一轮审阅；
随后实现纯合同/客户端、服务状态/监督和 bootstrap 消费，合并验证以上风险。
发现需要改变已批准权限、公开合同或实施顺序时按原规则审阅，不能以赶进度作例外。

最终机器交接一次给齐：候选和产物摘要、有限私有对象/额度清单、阶段化执行脚本、
原件保留规则、停止入口、所有正反例的预期结果及机器可读汇总。
依赖条件未通过时该批次停止并保存一次完整失败包；脚本不自动重试或切换 fixture。
准确结果返还后统一形成验收记录，再进入 Q3 正常链，避免每完成一项就交付一个手工命令。
