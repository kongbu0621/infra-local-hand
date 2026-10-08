# 补齐原 Q1 声明，接续核心任务

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-Q1-BINDING-CONTINUATION-v1`，仅 QI1–QI3。
本[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、[计划](IMPLEMENTATION_PLAN.md)
组成一个待决批次；沿用根 AGENTS 的 R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、直接来源及完整性、Owner
authority/mandate、无例外及 R→A→B→独立 C→D。不是既有 GS2 的重试授权。

## 目标与已确定的缺口

唯一交付仍是 H01 正常任务及结果、Q4 运行取消、H11 同任务恢复查询。复用原安装、
SSH、隔离 VM、五镜像及任务语义；先完成 journal 256→512 MiB 维护，再接原未发出的
`lhqcore-20261007a`。不增加扫描器、诊断平台、服务控制入口或其它支线。

输入事实基线 `5d8e5db79ebd137716145a60e71e85fe0252fe1d` 的
[本地核对](../Q2_CORE_UNIT_CURRENT_REVIEW_20261008.md)已确认：08d 拒绝的准确服务
通过 ExecStart 真实引用原保护根；其当前 runtime 摘要唯一匹配固定 C10 的
original_config。同条 manifest 摘要加规范票据六项身份重算准确请求名/实际 Id；
同配置的父域、source 和历史 boot 关系匹配。原清单同时漏掉此服务及其父 slice。
当前 `_growth_inventory` 未接入这条来源关联；不应修改直接引用谓词。

只补一个关联项：expected_units 增加准确服务及**非 null** 完整 control_group，
domain_units 增加对应 system slice，domain_cgroups 增加同一逻辑父路径。
原 18/6/6 变为 19/7/7，保护根、必要证据及其它已有声明不删改。拒绝名称前缀豁免、
仅加服务名、空 cgroup 或遇到冲突覆盖旧声明。

## 待批准的来源采用边界

固定 C10 原始 report.json 为 **9632 B**，SHA-256
`0183b985fdab6a755e96c916617484e274f38e284e575dcb298349d44ccba1e9`；固定 C11
exporter 为 **20208 B**，SHA-256
`a5265e00222eb9cea4a9675627650c4a51adeac69c6383732a3aac0e3a3b8deb`。
本地已核对直接原件；不重找 bundle、不运行 exporter、不读取 guest 配置或 intent。

本批请求采用上述 C10 配对摘要，以及已完成单次 systemctl show 的**原始当前响应及其
捕获/请求绑定**，作为这一条前向维护声明的来源。当前响应只能证明其捕获时的事实，
不能补写 08d 历史状态；其私有派生候选也不能独立替代原始输入。C10 为
Q1_EVIDENCE_ONLY，不是完整 Manifest / intent、完整旧域清单、源码全部字节或当前
cgroup 证明。保留 independent_authority_proven、q2_reusable_allocation、
q2_parent_admitted 为 false；不声称通过完整 slot/deadline 或独立授权验证。
本采用仅用于准确识别需要继续接受原检查的旧服务和父域，不授权任何 Q1 请求执行，
不把旧配置转为可复用 Q2 allocation。

准确服务名、路径、票据、响应原文及机器元数据保持私有。采用对象仅限任务提交
`38ff00109ee102c9530e6bac01c8baa705ab69ed` 的唯一查询原件，其完成记录为
`7d720868bf01dea8b382d9d9216704069c5cfb92`，并已在上述 5d8 核对中使用。
QI1 由本地执行者将这些既有载体的角色、长度、SHA-256 及相互引用，与**原私有
捕获索引**、请求绑定和 08d 原 stderr 的准确请求名称交叉核对，在新 D/输入冻结前
固定私有 pins。派生候选只能用于比较增量，不能替代上述来源；不得在不一致时生成
新索引冒充原索引。缺项或冲突即停止，不换对象、不新增现场读取，也不虚构云端已
审阅私有原文的记录。Owner 对本方案的决定采用这组已明确定位的既有对象及限定用途；
范围内的摘要固定和一致性核对不再拆成单独审批。实现只接受该固定来源，持有原件并
核验字节与关系；不能接受任意同形新响应或手填声明。

## 保留的保护与保证

保留直接业务根匹配、已声明服务静止及启动依赖、domain/cgroup 身份与为空、当前
进程/writer、必要持久证据、目标 QEMU 及五镜像身份、正常关机/原 pidfd 退出、锁、
独立完整备份/内容比较、一次原配置启动、ext4/UUID/内容及容量验证。已捕获 quiet
属性通过不能代替下一次维护的这些当前检查。没有停服务、杀进程、改权限/凭据、
放宽 allowlist 或修改 guest 配置来制造通过。

既有可信单管理员访问前提与四字段 guest_startup_assurance 原样保持；间接启动
穷尽观察仍为 NOT_PERFORMED，continuous_exclusion_proven 仍为 false。Owner 先前
已接受的前提在本批持续适用；存在相反证据即停止，不新增全机扫描来证明它。
本来源采用不提升这些覆盖声明，不把名称绑定等同于维护或核心成功。

## 一个批次与原限额

- **QI1：**一次完成准确来源接线、七旧维护历史、维护生产者及全部核心消费者；完成
  有意义的离线回归、准确 D 的 CI、独立安装验证、静态私料与原限额核对，冻结两侧。
  维护成功前不生成真实可执行核心包。
- **QI2：**唯一新维护 `lhqjgrow-20261008e`，新九名 create-only；预检和 execute
  共用原点、nonce、manifest 及累计用量，开始即消费。不得重放 08d 或其它旧 caller。
- **QI3：**仅 QI2 完整成功原件验证后，同一 D 发一次原 `lhqcore-20261007a`
  H01→Q4→H11。原核心对象已有即停止，不换名字替代，不单独利用旧条件许可。

保留 06a/07a/07b/08a/08b/08c/08d 七旧窗口及原件、消费、UNKNOWN 和全部义务。
八代各 1296 MiB/370 inodes/120 CPU-s：维护准入 **10368 MiB/2960 inodes**，
加原核心 capture 64 MiB/16 为 **10432 MiB/2976 inodes**；八代名义 960 CPU-s。
旧实际用量及未知义务不退款，不按失败产物较小减账；这些是累计准入，并非另造对象。

沿用已批准 GS 的所有单次限制：维护 900s 双钟/780s 修改截止、最多两次固定 SSH
/ConnectionAttempts=1、备份 320 MiB、目标 576 MiB、capture 8 MiB/32 inodes、
每流 1 MiB、CPU 120s/RSS 512 MiB、AS 256 MiB/FD 128、8 控制子进程、VM
4 vCPU/8192 MiB、两源各 98304 B、bundle 49152/393216 B。核心 900/800/750s、
四旧加新 1380 MiB/82560 inodes/10450 CPU-s 及更早义务、新核心 276 MiB/16512
inodes/2090 CPU-s、32 MiB 包、1 MiB approved-input、60 MiB 输出、64 MiB capture
及 reserve 均保持。短预检 4096 B、transition 65536 B、journal 至少 400 MiB/32768
inodes 保持；新增绑定及历史必须装入这些限额，超限即停止，不默认提高预算。

## 验收、披露和停止

验收须证明固定来源及唯一关联可重现、同项三处声明绑定一致、所有原拒绝路径仍有效；
随后由一次维护证明备份、增长、内容、容量与新 boot，再由原 live finalizer 判断三个
核心 case。CI 及离线名称匹配均不等于现场成功。失败 STOP_AND_RETAIN，QI2 不完整
则 QI3 NOT_RUN；不重试、补采、清理、恢复、回滚或二次启动。

请求批准三文档及必要脱敏记录发布 main，并允许本地执行者仅从已保留 08d 五件原件
生成/核对/公开 basename、bytes、SHA-256 最小索引，准确旧 D 为
`341796561a6aaa6f95779f438b57d958a1fd5954`。仅在与原私有索引及保留副本一致后
公开；云端未见这些私有 pins，不预填数值或附件事件。当前单元捕获、准确身份、
C10 原文及其它机器证据仍私有；新 08e 索引不自动公开。

待决仅为上述明确来源采用、QI1–QI3 和最小披露，批准后范围内不逐步再审批。
未批准前不修改运行/测试源码、配置或 caller；不以当前方案或旧 CLOSED 记录冒充
新的来源/窗口授权。R、原管理前提及所有未受影响的保护保持。
