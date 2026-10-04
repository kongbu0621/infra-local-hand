# Local Hand 核心完成修订：架构

- Authority：Owner；状态：**DRAFT / Gate OPEN / NOT APPROVED**。
- Scope、R、原批准关系及数值边界见[需求](REQUIREMENTS.md)。本文件不是 CLOSED 记录。
- 精确保证、32 池及 strict schema 以需求第 4–5 节为准；准确 Owner B 和独立 C 前不实施本修订。

## 1. 系统边界不变

现有 local entry、三文件 field 程序、固定安装候选与本地 finalizer 继续承担原职责。
本修订不新增服务、常驻进程、监视器、module repository、运行时插件或现场探针。
原固定权限、独立 host/guest 身份、原通道以及一次性消费边界保持。

| 组件 | 本次变更 | 保留边界 |
| --- | --- | --- |
| loader / bootstrap | 本修订取得准确 Owner B 与独立 CLOSED C 后，整合新 dispatcher 长度校验 | 两文件各自原长度上限、原 package/HELLO/BIND 和总输入界 |
| dispatcher | 在 524288 bytes 内接回真实准入与资源记录 | 单文件可读源码；原 deadline、对象和权限校验 |
| 固定 installer / 原 harness | 不改冻结源码、wheel 或 projection | 原安装调用与 H01/Q4/H11 语义 |
| local finalizer | 消费准确绑定的资源保证说明 | 原六文件、原 wait/EOF/fsync/同 inode 回读、原 host capture 保证 |

源码容量增加不增加运行容量。包构建仍按实际最终字节逐成员核验，原 32 MiB 输入等限制仍可拒绝发行。

## 2. 当前准入的职责

准入只在原唯一 carrier 内，按原 bootstrap/package 接收与载入顺序进行，并在 dispatcher 的业务
安装、case 准备及任务执行之前完成；不能把 bootstrap 已有载入或 staging 写入改述为从未发生。
已保留的准入闭包可以作为
待迁移源码依据，但须按当前接口重新审查、集成和验证，不能整体恢复后直接宣布可发行。

准入从当前 guest 取得身份、program、policy、filesystem、cgroup、quota、retained 和对象 absence；
再与准确 approved-input、HELLO、locators 和历史义务交叉绑定。历史输入只证明来源关系，不能代替当前观察。
容量按实际设备与既有义务归属计费；不把 configured quota、实际用量和新增预留相互代替。
每个固定 pool 在其全部输出路径涉及的每个 distinct `(dev,fs_uuid)` 各预留完整预算，同设备去重。
跨设备重复仅是不可消费的保守 headroom；逐设备合计可高于单次逻辑基准 276 MiB/16512。
state/carrier 下归账的 metadata wrappers 与会话祖先仍按实际物理设备计入，不能漏掉 quota、journal
或 evidence 设备上的祖先。原同设备约束及历史义务关系保留，不新增所有父目录必须同设备的条件。
只从已核实 ordinary UID 设置 `{0, ordinary_uid}` 所有者集合，不接受任意 observed owner 或调用方扩展。

所有读取保留受保护的 descriptor/path 关系、原时钟、无别名及 no-atime 要求。晚返、未知、缺项或漂移
触发原停止规则，不进行第二次 guest 连接补采，也不因为已消费 marker 而降低准入条件。

## 3. 资源记录分为三种事实

| 事实 | 可以说明什么 | 不能说明什么 |
| --- | --- | --- |
| 固定预算与应用记账 | 原对象的可消费额度、已知写入和创建是否满足应用规则 | 子进程内部所有短暂写入或整个文件系统物理峰值 |
| 实际 owned allocation 观察 | 指定身份对象在观察点的 block/inode 分配量及最大观测量 | 两次观察之间从未超限 |
| 既有内核/cgroup/quota 证据 | 对原单元或 project 已实际核验的限额与观测值 | 未纳入该边界的父级、其它池或整个 guest 的严格上限 |

三种事实分别记录，禁止从其中一种推导另一种。累计记账、当前分配与最大观测量必须有不同的语义；
已消耗的申请/任务/时间不退款，临时文件消失也不重置最大观测量。独立副本分别计费，真正同一受控
inode 的重复路径不得重复计费或因此放过未授权 alias。

32 池的互斥分类按需求固定，其中 11 个非 quota 池采用新保证，21 个 quota roots 保留原 kernel
quota 检查。共享安装池包含原 staging、最终 installation、受控编译/venv 临时目录；case metadata
wrappers 归该 case state，共享新 SESSION 祖先归 carrier；分类不改变实际路径或新建对象。
非 quota 扫描只取元数据，不读取/hash 文件 payload；到其它专属 pool 边界就排除其子树。
21 根一律只用原 project quota 汇总，不递归遍历。H11 业务 result 不为核算而 stat/open/hash，
ledger 不导出；观测来源摘要只对本次观测记录自身编码。

dispatcher 直接控制的 I/O 沿现有 guarded 接口记账并观察触及的非 quota 池；子进程沿现有执行
身份绑定、原 wait4 与双 EOF 路径运行，只在启动前、结束后与原受控交接点观察。不声称逐次观察
冻结 child 内部 create/write/fsync，也不新增这种要求。quota 完整观察位于原 setup 完成后，
不在 root 创建、project assignment、hardlimit 设置之间错误要求 quota 已生效。
观察错误、身份漂移、观察期间对象变化或超限时保留原失败和部分对象，停止后续动作；不自动重试
取得一个较好样本。停止时可能已经超限，未观察瞬时峰值也可能更高。

本机制不增加监视线程、额外管理单元或旁路目录，也不安装新的文件系统限制。既有采样无法证明的
瞬时行为必须以 `full_guest_filesystem_peak_proven=false` 报告，不通过加快轮询改名成硬峰值。

## 4. v2 结果中的严格资源证据

每项 guest 资源事实须有原执行身份和原时间窗口内的来源，进入已绑定的 output/remote result 证据链，
由原 local finalizer 核验。禁止在最后终端输出附加一个无法回到 guest 证据的“资源通过”结论。
CPU、memory、pids、stdin/output 与启动计数仍要求真实观察，不能以已知上限或预期调用数填值。
carrier 的 CPU/memory/pids 是原绑定 cgroup 在回传前观测时已知的值，不是所有业务单元峰值之和。
原 carrier 内读取不到真实 pids.peak 就报告 INCOMPLETE，不用 TasksMax/pids.max/pids.current 替代，
不借其它 CI 内核的文件存在性作证明，不修改系统来补这一事实。

唯一新 wire 语义是 remote-result/v2：旧顶层字段保留，新增内联 resource_accounting。
其 exact keyset、各观察 record 和摘要 preimage 按需求第 5 节；32 行分别记录受控 I/O、最后完整
观察及 bytes/inodes 各自最大完整观察。消费者重算 observation 摘要和整份 snapshot 摘要，复核
实际池身份、原 clocks、阈值、来源与 complete/missing 状态。摘要绑定观察记录，不声称保存了
不存在的逐文件 raw preimage。INCOMPLETE 保存已取得的观察，未知值为 null 并进入 missing。

guest_allocated_bytes/inodes 仅在全部池完整时分别等于各池最大 bytes/inodes 之和，
两个数可来自不同时间，既不是同刻实际总量也不是全生命周期峰值。
完整成功必须严格报告 full_guest_filesystem_peak_proven=false；本字段不是可自行升级的能力位。
观测额或记录大小超限均不能 COMPLETE，不能为了保持成功截去某池/记录或把未知填零。

新 resource_accounting.completion_adjustment 复用既有四项 authority descriptor 的严格形状，
只绑定本 A/B/C 和原 manifest 的 D。原 package v3、session、marker、HELLO、BIND 及
manifest.amendment 不扩字段、不改版本，manifest.amendment 继续指原输入绑定修订。
离线 source-lineage 增加本修订准确 pin 与 C→D 祖先检查，D 还必须为原所有 C 的后代；原 field
digest、implementation/release 检查与 finalizer 一起验证新结果。旧 v1 仅保留历史只读解析，不能
被静默当成新保证发行或验收。82 output members、六 host 文件、原 framing 与全部大小限制保持。

## 5. 失败与最终验收

资源观察失败进入原 STOP_AND_RETAIN/INCOMPLETE 状态机；不能自动另开一轮、另名重建或清理后继续。
在原 deadline 内仍可执行原已授权的有限停止和 owned descriptor 释放，但不刷新结束窗口。
缺失事实不得补零，也不能把被取消、超时或 incomplete 的观察当作通过。

源码、CI 与离线 package 校验只证明各自边界。H01 真实执行与结果收回、Q4 取消、H11 原任务恢复
仍由原事实定义；H11 不启动新业务，不读取/封装原业务结果，不创建新 grant，不解除旧 UNKNOWN。
资源保证变更不会改变这些语义或 production 限制。
