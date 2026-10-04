# Local Hand 核心完成修订：实施方案

- Authority：Owner；状态：**DRAFT / Gate OPEN / NOT APPROVED**。
- Scope/R 见[需求](REQUIREMENTS.md)；职责见[架构](ARCHITECTURE.md)。
- 本文件不产生新增现场授权。C1–C3 只在准确 A、Owner B 和独立 CLOSED C 之后实施。

## 1. 当前允许的工作与准确 A

当前只完成本修订的三文档、只读复核与既有测试。逐池保证、v2 机读字段/版本、失败表示与逐设备
保守预留均按需求的准确方案提交；不能用宽泛“继续”替代本两项变更的准确批准。

现有核心范围内的 deadline 或确定性错误修复仍可继续，但应单独提交、保留原检查与证据。
不得在本修订 A 内混入新上限、资源语义、测试原型或其它受本修订影响的实现。

形成准确 A 的顺序：

1. 独立复核 11 个非 quota 池的新保证、21 根原 quota、32 池分类、v2 strict 对象及逐设备预留。
2. 校对原三个 A/B/C、固定 candidate/wheel/projection、package 预算及单次 F1 的继承关系。
3. 提交仅含三文档及必要 baseline 登记的准确 A；向 Owner 展示两个物质变化、明确局限和完整 C1–C3。
4. 原样保留 Owner 对准确 R/A/scope 的 B。若 Owner 改变方案，先更新准确 A，不能由实现者自行调和。
5. 另做仅含 bookkeeping 的 CLOSED C；第一个受影响实现 D 必须是 C 的后代，C 不混源码或新测试。

源码容量和 guest 资源保证两项尚未批准；既有 D1–D4 或“继续核心”不会自动关闭这一新范围。

## 2. C1：接齐当前 guest 准入

在批准的新 524288-byte dispatcher 上限内，迁移已保留的准入闭包并与现有真实准备/执行路径连接。
仍在三文件结构内实现；不调整 loader/bootstrap 自身上限或原 package 总输入限制。

交付包括实际 guest 身份、program、policy、parents/filesystem/cgroup、quota、retained、历史容量与
固定对象 absence 的收集、交叉绑定，以及原载入/staging 后、dispatcher 业务安装/准备/任务前取得
完整 admitted baseline 的顺序；不抹去原 bootstrap 已有动作，不增第二条现场连接。
ordinary owner 集合必须来自实际准入的 UID；不得由测试替身或历史猜测初始化。
每 pool 的所有物理输出设备分别预留完整预算，同设备去重；跨设备重复是不可消费的 headroom，
不是可写额度。验证 metadata wrappers/祖先跨设备时不漏账，也不要求不同设备合计硬凑逻辑 276 MiB。

验证覆盖缺字段、错误来源、UID/GID/PID/程序身份不符、别名和替换、retained 漂移、quota 缺失、
容量不足、对象已存在、晚返回与原时钟到期。真实文件 I/O 可以在隔离临时目录验证；mock quota 或
manager 只证明对应代码条件，不写作 guest 通过。任何新 field 读取仍只允许在原一次 carrier 内。

完成标准：当前准入由真实效果产生，缺失时 fail closed，已批准输入与观察不能互换；与准备/核心
入口的回归通过，独立审查能从业务安装/准备/任务入口反向追溯所有必要准入。

## 3. C2：完成资源记账、观察与明确保证

严格按需求第 4–5 节的逐池边界及 exact schema 实现，不能靠编码临时扩展本 A。
固定共享池及已批准的其它池均保留原数值、对象归属、历史义务、无退款和停止条件。

为 dispatcher 直接控制的创建、写入、fsync 和既有子进程前后接入实际对象分配观察，记录原身份、实际计账和最大观测量。
安装子进程依旧使用现有执行身份绑定、原 paired clocks、wait4 和双 EOF；不添加旁路监视器、管理
单元或第二次执行。冻结 child 内部 I/O 不要求逐次观察，不改冻结源码以制造该能力。
非 quota 只读元数据；21 根不递归，H11 原业务结果不 stat/open/hash，原 ledger 不导出。
资源汇总还须包含真实 CPU、memory、pids、流 bytes、任务/控制/query/dynamic
unit/native children 启动量，不能用静态预算、调用意图或成功返回推定真实观察。
carrier CPU/memory/pids 只按原 cgroup 的回传前观察定义；缺真实 pids.peak 时 INCOMPLETE，
不填当前数或限额，不新增系统升级路线。

针对真实失败模式验证：短写、重复副本/身份去重、部分创建、临时对象消失、前后不同 inode、观测
失败或晚返、超限后停止、子进程非零退出、reap/EOF 缺失、原 deadline 不刷新、最终证据缺项。
特别验证“前后采样均未超限，但子进程中途峰值未知”仍保留 false 保证，不能得到严格峰值为真的结果。
受控 I/O 只观察触及的非 quota 池，原 quota 初始化未完成阶段不谎报 OBSERVED/ABSENT；原 root
创建、project assignment、hardlimit 设置仍按原顺序及 guards，quota 完整观察从 setup 完成后开始。
验证最后完整观察不晚于原终结窗口、各 maxima 不低于最后用量且两种原时钟次序正确，三种观察
状态与 null/missing 组合严格一致。保留 32 行完整记录和来源/总快照摘要，不能只存自报总数。
保留现有 quota/cgroup 技术检查；新报告不得把它们的局部证明范围扩大到整个 guest。

完成标准：每个资源字段均能指向真实来源；统计未知不会填零或通过；
`full_guest_filesystem_peak_proven=false` 及逐池保证按本 A 的 remote-result/v2 被机读、摘要绑定并由 consumer 检查。
总 180 MiB/13440 不再被误述为已证明的瞬时硬峰值；原 H01/Q4/H11 语义无变化。

## 4. C3：离线审查、冻结与原单次验收交接

完成定向失败回归、完整源码测试和原独立 installed verifier。测试生成 wheel 只用于验证，不能替换
准确 A 冻结的现场 wheel。复查实际 field 字节数、三文件闭包、原输入输出/内存/CPU/pids/deadline、
strict schema、private source 关系和 candidate provenance。

独立审查从“用户要求执行并收回一个任务”反向检查准入、准备、原业务执行、结果收回、取消和恢复；
不把新资源记录本身当作核心完成。修订需求、实现、失败测试及用户可见结果须一一对应。

冻结准确 D 后，由具备原本地私有材料的本地 Codex 进行原 package 两次独立 build/parse，验证
loader/bootstrap/dispatcher、准确 A/B/C/D 与全部输入关系。新增本修订的第三条 source-lineage
固定 A/B/C pin 与 C→D 检查，并要求 D 同时下降于原所有 C；原 package/session/marker/HELLO/BIND
及 manifest.amendment 不改字段或版本。新 authority descriptor 只内联在 v2 资源对象，D 必须
等原 manifest.implementation，旧 v1 不得在新发行中转换成 COMPLETE。任一原 gate 或新 gate 未闭合，release
allowlist 保持空，package 保持 NOT_ISSUED；不得先加 release digest 再补证据。

离线全部通过后，仅交接原条件性单次 F1，保持 H01 semantic PASS → Q4 semantic PASS → H11。
复用既有 SSH/环境，保留旧现场，不重复历史安装，不重连、不重试、不清理、不新增 marker/request。
本修订不授权另一轮资格测试或现场探针。任何一步失败都按原停止与保留规则处理，准确区分未发行、
已消费但失败、case 未运行及真正现场 PASS。

## 5. 验收与退出边界

三文档批准只开启 C1–C3，不意味着其内容已实现；CI 成功不意味着单次 F1 已消费或核心已通过。
最终报告必须明确准确 commit/tree、测试结果、package/release 状态、是否发出 carrier、三个 case 的
实际状态、真实结果是否收回和新的资源保证局限。保留失败证据与未完成项，不生成不存在的现场事实。

若新上限仍不足、其它资源数值需变、需新执行次数/权限/系统配置或新 runtime 对象，则停止受影响
工作并按原 R 处理，不能把本窄修订用作后续无限扩张授权。无须改变原批准边界的核心错误修复继续
按原范围进行；namespace/watchdog、NAS、E4–E6 与 production 激活仍暂停或排除。
