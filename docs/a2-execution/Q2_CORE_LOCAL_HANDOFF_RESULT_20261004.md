# Local Hand 核心交付：本地既有材料复核结果

2026-10-04 +08:00。落实[云端与本地交接](Q2_CORE_CLOUD_LOCAL_HANDOFF_20261004.md)的
saved-material-only 任务。本件是脱敏事实回传，不是新合同、Owner B、C、现场资格或执行许可。

**结论：准确 core anchor 的历史来源和 mount 记录可以对应；现有材料不足以选定可执行的
host capture 硬限额路线。** 不能把另一个旧 parent 的 12 KiB 状态套到 core anchor，
也不能把共享 ext4 的剩余空间当成 capture 的 64 MiB/16-inode 硬边界。
本轮没有连接 guest、运行真实任务或收回新的任务结果；不新增内核证明专项。

## 返回事实表

| 返回项 | 核对结果及限制 |
| --- | --- |
| 仓库基线 | 从 `6a93e9d2c6bb03b860fa07139648e4feb3146b76` 快进到 `1e1ecffb9e952f5210bcb0a40f2c85215e79b993`。修订 proposal A 为 `4009e1b560dd873bc3d9b937be539f329b93371a`，仍 **OPEN / REVISION REQUIRED**；没有批准、改写或实施该 proposal。 |
| 已有来源 | 本机保留的 R3 原件、其静态复核、帧文件及帧内 P/M/T；逐项长度/摘要见下表。K4 本轮只复用仓库中的既有收件索引，不声称取得或重新散列 K4 raw。 |
| 准确 anchor | P 的固定 wrapper 字面路径 = R3 的 T01 路径；T01 的父目录 = R3 `control_parent`。T 的四项控制对象与 R3 T01–T04 的路径、长度、摘要匹配，四项均在该父目录。四份内容摘要又与现 core entry 常量及 2026-10-03 live-input review 匹配。 |
| management host / mount | T 保留 QEMU、VM 控制文件、镜像和宿主身份关系；R3 将 control parent 绑定到所记录的同一 ext4 mount。它是既有管理环境的历史材料，不是本轮工具容器的 PID 1 推断。原 R3 仍为 `ENVIRONMENT_ASSUMPTION_NOT_PROVEN`，无独立原宿主鉴证；当前宿主、mount 和 namespace 状态未新测。 |
| parent 差别 | R3 的 **control_parent**：size 4096、blocks 8（512-byte units）、mode 0700、EXTENTS；另一个 **host_parent**：size 12288、blocks 24、EXTENTS+INDEX。二者当时同属 ext4，记录 mount options 为 `rw,relatime`。这是异角色目录的历史观察，不是当前峰值或持久性证明。 |
| 现成硬限额机制 | **UNKNOWN**。所复核材料没有把 core anchor 绑定到已生效的 host quota 对象或固定容量存储对象；不能据此断言宿主没有这种机制。guest project quota 不替代 host capture。 |
| byte / inode 上限 | **UNKNOWN**。64 MiB/16 inodes 是批准的 capture 预算，不是已证明的存储执行机制；proposal 的 52 MiB 是流逻辑上限。R3 的共享 filesystem `statvfs` 不证明两者被强制执行。 |
| 已占用 / 剩余 | **UNKNOWN（按 capture 计费范围）**。仅有 selected-file 和 parent 历史观察及共享 filesystem 余额；未取得该范围的完整 usage / reservation / remaining。不得把异时 K4/R3 或终态 `st_blocks` 拼成全过程账单。 |
| 执行身份权限 | R3 的三项 UID 值、三项 GID 值分别与当时 control parent 的 owner/group 相等，mode 为 0700；这仅支持历史 DAC 身份关系。当前权限、quota enforcement/control 权限、其它 writer、ACL/LSM 等执行条件不由此证明。 |
| 共享使用者 | T 的五个 `vm_images` 记录均与控制对象同 parent、同 recorded device；不是空的 capture 独占目录。镜像仅有历史元数据，不重读磁盘内容，也不把逻辑 size 当实际分配量。未证明当前是否运行或完整共享对象集合。 |
| 本次动作 | 复核既有文件和仓库记录、快进同步、已有入口回归及本报告。新 SSH/marker/carrier request/真实任务/安装/系统配置/清理/重试均为 **0**；未读 raw device、未探测当前内核、未执行保存的 payload。 |

## 来源索引与本次验证

完整私有定位继续保留在原帧 P/M/T、R3 和原本地文件中；以下代号足以由摘要回查，不公开路径、
IP、账号、boot/machine/device/inode 身份、控制原文或密钥。

| 非敏感来源代号 | bytes | SHA-256 | 原记录时间 / 本次处理 |
| --- | ---: | --- | --- |
| R3 raw | 32439 | `700a17989fec4271973a0620e87dccee64ce30ef4f7082a97ab42e5b6648f119` | 2026-09-29 收件复核；JSON 无独立 wall-clock 时间。本轮重算摘要。 |
| R3 static review | 8383 | `93eebdd40ca102641fb1b2624ee9a17b8ed41c19cdebf510419bb1aedf127684` | 2026-09-29；本轮重算摘要。 |
| Saved source frame | 5496087 | `c9f4bb2744d48f9e7174157a95761d081be038cf4dd4f67ae42620a1a9e6d315` | 既有 89c725ef 交付输入，无新增采集；本轮重算摘要。 |
| Decoded archive | 4113937 | `e6ed13681e79492aae5ba8216996056ef03c987c901d4f23db4906989d92eeec` | 帧内既有 archive；仅 RAM 解码，匹配帧声明及 R3 绑定。 |
| P | 5426689 | `5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b` | R3 固定私有来源；未另认定可信采集时钟。仅 AST 字面值读取。 |
| M | 50266 | `7672ac050609fc7e05481443c9239df0d36f25b4ec9860c2bb833024b962647a` | R3 固定历史 archive manifest；未另认定可信采集时钟。仅 JSON 读取。 |
| T | 5913 | `76cc2c698dbe882ed246509746bc7088ba55df4199f550af8bad42c9f925dd65` | 记录的 realtime 为 2026-09-27 15:14:06.134682260 +08:00；不是独立时间鉴证。仅 JSON 读取。 |
| K4 retained reference | 34013 | `281ff17ffd7bb83f7afd0bcae7488f5fa5b9bf551852f63494ceb8d84cc5cab9` | 2026-09-28 既有收件索引；此行是索引引用，不是本轮 raw 重验。 |

R3 和静态复核摘要与[已发布收件记录](Q2_LOCAL_SOURCE_EVIDENCE_COMPLETION_REVIEW.md)一致；
P/M/T 与 R3 的固定来源摘要一致。四份控制 raw 在 RAM 解码后长度/摘要一致，未执行脚本，
未读取其引用的私钥或当前管理目录。私有原件以 O_NOATIME/O_NOFOLLOW 只读访问，不调整权限。
历史五项 atime 漂移及其它既有失败不被本次摘要核对抹除。

复用的仓库记录还包括 [R3 原独立复核](evidence/q2-local-source-field-20260928/diagnostic-rerun3-independent-validation.json)、
[K4 收件索引](evidence/q2-kernel-field-20260928/full-return-review.json)、
[异时计费边界](evidence/q2-cost-source-review-20260929/retained-input-check.json)和
[core 输入关系](Q2_CORE_LIVE_INPUT_REVIEW_20261003.md)。R3 原始 mountinfo 未返回，
本轮核对的是其已保存的解析字段，不声称重新计算原始 mountinfo 或重新资格化 mount。

## 机制覆盖与准确缺项

| capture 计费项 | 现成机制覆盖证据 |
| --- | --- |
| 七个固定输出对象 | UNKNOWN；合同列出了对象，本批次未创建它们，没有机制对象绑定。 |
| parent 增长 | UNKNOWN；仅有当时 4096-byte 目录观察，不是后续分配上界。 |
| 额外 inode | UNKNOWN；未有作用于准确 capture 范围的 inode hard limit / usage 记录。 |
| 瞬时分配和释放前峰值 | UNKNOWN；旧记录明确 `allocation_peak_proven=false`。 |
| 共享使用者及其它义务 | UNKNOWN；存在上述同目录镜像历史记录，但无完整共享计费与保留量。 |

**最小缺项是一份既有 host 存储执行机制记录（如确已存在）**：明确绑定准确 anchor/mount 与
enforcement object，分别给出 byte/inode hard limit、usage/reservation/remaining、执行身份权限，
并说明上述五项覆盖。所复核材料没有该记录；无需再次索取或重采已有 K4/R3、四控制原文。
旧记录即使补齐，也只能证明保存时点，不能自动升级为当前现场准入。

因此目前不能从所复核材料中选定“现成硬配额”或“现成固定容量存储”路线，也不能声称两条路线
不存在。交回云端据这些具体事实收敛 capture 合同：保留原 64 MiB/16-inode 上限，处理共享对象与
全过程计费，不仅删除约束，也不默认转去 loaded-ext4、raw-device 或完整内核证明项目。
若实际方案要求新现场动作或 material contract change，再形成准确、最小 A 请求必要 B/C；
此报告不请求批准仍有缺项的 `4009e1b`，不授权采集、迁移、安装或改 quota。

## 验证与核心交付状态

- 本轮直接读取固定 R 并核对 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- 在同步后的 `1e1ecffb9e952f5210bcb0a40f2c85215e79b993` 运行已有
  `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_e3_q2_core_delivery_entry.py`：
  **18 passed**。这是本地入口回归，不是真实执行验证；本轮未跑全套测试。
- 该提交的[主干 CI 37170034690](https://github.com/kongbu0621/infra-local-hand/actions/runs/37170034690)
  已完成 success；不能替代现场验收。
- 本轮只新增本报告和交接链接；无 runtime/test/配置变化，没有新 candidate、package 或 release digest。
  既有 `package=null / NOT_ISSUED`、空 release allowlist 及 production
  `E3_SUPERVISION_UNVERIFIED` 保持。
- 此次核心批次真实受理、受监督任务执行、退出确认、取消、恢复及任务结果/证据回收仍为 **0**。
  下一直接步骤是据本报告收敛可执行 capture 合同；必要准确 B/C 后补齐真实效果入口、绑定输入、
  验证并冻结 package，才条件执行 H01 → Q4 → H11。H11 使用自己的 origin 原 ledger/unit/grant/deadline，
  不复用 Q4 ledger、不重启业务、不延长 deadline。历史批次仍保留，不重放；namespace/watchdog 保持暂停。
