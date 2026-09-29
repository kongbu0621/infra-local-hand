# Q2 文件系统资格与账单：准确来源和证明工单

2026-09-29 +08；基线 `65047d64934468acfca8e4f94aebe99ea56e6f93`。
原 R、H A/C 与[现场资格复核](Q2_FIELD_QUALIFICATION_NEXT_REVIEW.md)一致。
本文将已有缺项拆成可审查的来源与验证责任，不新增现场读取、采用范围或预算。
EA_INODE 漏拒已由 `293cb51f` 修复，不重复列为未修代码问题。

**当前可继续完成离线引用、覆盖与算术冲突校验；现有原件还不足以形成完整共同账单，
也不足以证明固定 indexed parent 的写前分配峰值。** 不通过改 flags、搬目录、试写
后删除或为缺少的成本填零取得准入。

## FS 工单：先证明哪些量

已留存 rerun3 对固定 host parent 的观察是 size/allocated 各 12,288 bytes，
flags 为 EXTENTS 与 INDEX。它只固定那个观察时点；当前实现仍只支持更窄的目录几何。
64 KiB/4 inode 是原 marker 子预留，capture 总限额仍为 64 MiB/4096 inode。

| 工单 | 必须绑定的来源和证明 | 现有事实的用途与缺口 | 完成判据 |
| --- | --- | --- | --- |
| FS1 设备与实现 | 同一 host/boot、held parent/device/mount、实际内核构建及适用 ext4 代码/配置 | mountinfo、statvfs、flags 有局部观察；上游代码不是现场构建 | 每项算法假设能对应已采用且适用的来源，不能只以 ext4 名称判断 |
| FS2 分配粒度与 features | block/cluster、相关 superblock features、mount/config 条件 | f_bsize=4096 不自动证明 cluster=4096；已有 EA_INODE 拒绝仅收紧一个 bit | 排除或完整计入会改变上界的路径；没有等价来源就保持未证 |
| FS3 索引目录插入 | 固定名称、HTree 插入/分裂/重启及 extent 映射增长的适用上界 | INDEX 和 12 KiB 总大小没有给出节点占用、碰撞或未来分裂数 | 正常与失败路径每项额外分配均有界，写后净增长不替代峰值 |
| FS4 创建属性与隐式对象 | inode 创建、security/xattr、默认属性、quota 及适用 allocator 路径 | ACL absence 不代表全部创建属性不存在；目录 scan 不列出所有隐式对象 | 与 FS2/FS3 去重后覆盖额外 inode/block，不能默认额外成本为零 |
| FS5 并发与残留 | 范围内其他创建者、父目录保护、失败时未释放分配、保留承诺 | held fd 固定身份，不是兄弟创建互斥；前后稳定不是全程互斥 | 上界成立所需的并发假设有来源；无法证明则拒绝 |
| FS6 同步与存储 | 文件、目录、必要父目录的 fsync 链、错误传播、底层存储假设 | SHA、close、stat 和 CI 不证明原设备持久性 | 保留原可信存储假设；错误或不明为 UNKNOWN/BLOCKED，不承诺发现任意回滚 |

证明目标保留未知项：

`record_peak = peak(new_marker_allocation + positive_parent_increment + other_uncovered_record_allocation)`

各项必须无重复且来源完整，再与 65,536 bytes / 4 inode 比较。
它衡量新增分配及必要承诺峰值，不把已有 inode table、bitmap 或 JBD2 区域的每次覆盖写
都重算成新分配；这些路径是否确有额外分配仍需适用证明。
JBD2 既有空间与 SSH/systemd/journald 审计文件不是同一费用对象。

## B、G、M 与历史义务分开

| 量 | 已有表示 | 不得推导的结论 |
| --- | --- | --- |
| B：父目录旧基数 | 某时点 metadata 的分配观察；其类别/既有覆盖还待证 | 不能置零、整体改归 capture，或把不同观察相减得到因果归属 |
| G：首次 marker 检查保留的 parent 正差 | 已有组件绑定准确 before/after 与首次 marker snapshot | 历史 4→12 KiB 差额不是未来该次 G；G 不是峰值 |
| M：marker 子树实际分配 | 严格 scan 与固定成员的实际记录 | 不能漏算 G，也不能把已含在 blocks 的量再加一遍 |
| C：marker 原池 65,536 | 显式 bill/v2 为 actual=M+G、future=C−M−G | 总 C 不变；不能再从另一池抵 G 或称旧 M+(C−M) 少预留 G |
| 原 guest/host 承诺 | 保留原义务及其准确覆盖、终止条件 | 本次离线复核不释放未用承诺，不因暂未观察到对象就撤销义务 |

现 bill/v2 对 parent/ancestor 已在旧 scan 或义务中、同物理身份别名的拒绝继续保持。
补齐 B 的来源表不自动放宽这个窄接口。若将来需要支持一种新的共享分摊方式，须先
说明准确类别/覆盖依据及不重复计算的规则，不能用新 schema 名称掩盖变化。

## 观察与费用证据的最小关系

每个待审条目分别保留原件摘要、准确字段位置、观察时点、机器/设备/inode 身份、
所观察的量、角色依据、类别依据、义务与覆盖/抵扣关系。未知量显式保留未知。
引用能解析且摘要匹配，只证明输入关系一致；不证明原件可信、来源已采用或分类合法。
同一 JSON 容器也可能包含多个历史时点或失败前的 metadata；按原件摘要分组不是
观察 epoch 证明，所选字段的算术合计不成为同刻 actual 或当前下界。

1. K4、rerun3 M7/T4 及后来另存回执按各自来源保留，不能拼成同刻完整清单。
2. 路径、文件名或位于 result 目录不决定费用类别；角色和类别各需可定位依据。
3. 物理身份只在明确机器与观察边界内去重；跨时点 inode 数值相同不证明对象始终未变。
4. coverage 关联须防止同一实际量抵多个池、同一义务重复释放、host/guest 或不同 owner 池互抵。
5. 已知条目算术可以显示带前提结果；它不能填补未知 actual/future，也不能直接交给现准入入口。

## 原生日志与隐含副作用矩阵

| 阶段／机制 | 要列出的对象和事件 | 取得有界费用仍缺什么 |
| --- | --- | --- |
| host wrapper、env/Bash/SSH | 解释器与工具解析；连接、认证、失败/重试策略；可能的 known_hosts 写入 | 准确工具/配置/环境、文件副作用条件及原允许用途；只拿到脚本文本不够 |
| guest SSH/shell/sudo/probe | 会话、权限调用、初始化及失败审计 | 服务版本/配置、记录目的地、设备、事件次数和最大记录/轮转分配 |
| outer、owner、supervisor、manager 子单位 | start/Job/状态变化、停止和异常路径 | 各管理域真实事件界、审计路由及已有池覆盖；不能只计业务 stdout |
| collector、stop/EOF/seal | 收尾期间的管理和审计、原流、结构化结果 | 原窗口内的收尾余量、真实 allocated 与未来承诺，不能失败后另开采集补齐 |
| 另存诊断、重试、盘点与维护留存 | 由其他明确动作写出的结果文件 | allocated/身份、准确生成授权及合法覆盖；observer 无主动写入不意味着这些文件不存在 |

原生审计上界需要事件数、单记录/分配取整、轮转、失败收尾、并发范围及已有覆盖共同成立。
2 MiB 双流上限、3 MiB host capture 或 stderr 为空，都不能替代这个证明。
改变日志配置来制造上界属于另一项实际变化，本文不执行、不预先批准。

## 准确变更界线与执行顺序

| 动作 | 当前处理 |
| --- | --- |
| 已持原件的离线引用、角色/费用依据映射、条件算术和冲突校验 | 原 CLOSED H1/H3/H4 内继续；不产生来源采用或消费资格 |
| 原预算、原读取保护下充分证明更宽 indexed profile | 可作为已有范围修复研究；当前尚无完整证明，不先放开谓词 |
| 新 FS 接口或现字段新用途 | 逐项对照原批准用途、对象、权限、字节/时间上界；仅“缺事实”不自动重开，也不自动获得读取权 |
| 把 K/L local-only 例外升级为消费入口依据 | 准确用途变化需按 R 处理；本轮不接入 |
| 新监督设施、日志/系统配置、目录迁移、试写删除、扩预算或新窗口 | 不属于本轮组件；先给准确受影响方案与决定 |

先完成离线审查组件与独立反例，保留清楚的未决列表；再针对真正缺少的来源
形成最小、一次可交付的方案。没有适用机制或充分上界时，不要求 Owner 重复已有采集。
当前 FS、完整账单、H07、现场准入均未通过；原 startup batch 仍未发行。

## 一手机制参考

- [ext4 directory](https://docs.kernel.org/filesystems/ext4/directory.html)、
  [extent tree](https://docs.kernel.org/filesystems/ext4/ifork.html)、
  [bigalloc](https://docs.kernel.org/filesystems/ext4/bigalloc.html)、
  [EA inode](https://docs.kernel.org/filesystems/ext4/eainode.html)。
- Linux v6.12 [namei.c](https://github.com/torvalds/linux/blob/v6.12/fs/ext4/namei.c)、
  [ialloc.c](https://github.com/torvalds/linux/blob/v6.12/fs/ext4/ialloc.c)、
  [extents.c](https://github.com/torvalds/linux/blob/v6.12/fs/ext4/extents.c)。

这些一手资料用于列出候选证明路径。适用代码、配置及对象必须另与原机绑定；
本文未把 v6.12 或当前在线文档声明为原机内核，也未给出尚未证明的数值峰值。
