# 收窄维护启动检查，直接接续核心任务

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-DECLARED-STARTUP-CONTINUATION-v1`，仅 DS1–DS3。
本[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)、[计划](IMPLEMENTATION_PLAN.md)
组成一个批次。沿用 AGENTS 固定 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、
直接来源/完整性、Owner mandate/authority、无例外及 R→A→B→独立 C→D。

## 目标与问题

唯一产品目标仍是 H01 正常执行与结果、Q4 运行取消、H11 同任务恢复查询。复用原
安装、SSH、隔离 guest、五镜像；完成原 journal 256→512 MiB 维护后，发原未运行的
`lhqcore-20261007a`。不新增产品功能或观察工具。

输入基线 `b4dde5d387a9206a41925a2d051b51eb74fb0235` 的
[QI2 返回](../Q2_CORE_Q1_BINDING_FIELD_20261008.md)确认：准确 D
`fa30146b0a49744b25df0f23969bf96b17eaacad` 首次 CI 3/3，QI1 声明实际为 19/7/7；
08e 又在另一服务 ExecStart 的 `GROWTH_UNDECLARED_BUSINESS_UNIT` 条件停止。
没有关机、备份、扩容或核心运行。新服务是否活动、是否只剩定义均未证明。

源码的全量启动枚举要求每个引用受保护路径的单元都预先声明，而历史材料原本只提供
选定来源；C10 的 complete_q1_domain_inventory 明确为 false。补齐一条 Q1 关联
不使清单变完整，继续逐个补名仍可能遇到下一项。本次不把新服务叫作“无害”，也不
宣称先前修复无效；改变的是维护要求穷举所有历史启动定义的前提。

## 唯一保证范围调整

停止维护 pre/post 中的全单元和模板启动枚举：不调用 list-units、list-unit-files、
模板 cat，也不对未知服务的定义做业务路径拒绝或逐项声明。只查询已有声明目标及
声明域，保留其原身份、静止、启动边、cgroup 和域属性校验。

此取舍减少了**未声明单元、模板、timer/socket/path 等启动入口的静态观察**。未知
入口可能无需新的管理员操作就自动启动；当前进程检查只是快照，不能弥补这个缺口。
不是安全等价修复，也不再报告全量启动清单已检查。新报告准确标注
`undeclared_unit_inventory_observation=NOT_PERFORMED`，原间接启动观察仍
NOT_PERFORMED，continuous_exclusion_proven 仍为 false。

Owner 需明确接受该覆盖缩减及其依赖的既有管理前提：隔离 guest 中的旧业务不会
通过未声明服务、模板、timer/socket/path、cron、脚本或其它入口自动启动；从本次
维护开始、停机前、原配置重启后的 post 阶段直到核心交接，不新增这种入口，也不从
其它会话启动旧业务或写受保护目录。它覆盖已经存在的自动入口，不能仅解释为今后
“不手动操作”。执行者复用既有管理交接确认；未知或有相反证据即停止，不新增全机
扫描来证明，不由“没有报错”推导前提为真。08e 的路径引用本身既不证明这个前提，
也不证明它已被违反。

保持：已批准的 19/7/7 声明及完整 Q1 来源绑定，声明内服务前后静止/启动边检查，
域单元准确 Id/LoadState/ControlGroup/无 Exec 属性，声明 cgroup 身份/为空及前后
复核，现有当前业务进程、可写 FD/共享 mmap 检查，必要持久证据，journal 内容保护，
目标 QEMU/pidfd/argv 与五镜像身份，正常关机及旧进程退出，锁、独立完整备份与比较，
一次原配置启动，ext4/UUID/内容和五池容量验证。实际活动业务或 writer 仍阻断。
不修改凭据、权限、任务 allowlist、隔离、资源限制、进程扫描判定或产品任务语义。
不停止/禁用未知服务，不清理残留；不增加 replacement scanner 或逐项豁免表。

## 一个批次

- DS1：一次完成范围缩减、准确覆盖报告、八旧维护历史和维护/核心全部消费者；
  完成离线验证、准确 D 的 CI、独立安装验证、真实静态输入和原上限核对，再冻结
  两个 caller。现场安装不变，维护成功前不发行真实核心包。
- DS2：唯一新维护 `lhqjgrow-20261008f`。普通预检与 execute 共用原点、nonce、
  manifest 和累计计量，新九名 create-only，开始即消费，旧 caller 不可重放。
- DS3：仅 DS2 全部成功原件通过验证后，同一 D 发一次原 `lhqcore-20261007a`，
  H01→Q4→H11。原核心对象已存在即停止，不改名替代。

八旧窗口 06a/07a/07b/08a/08b/08c/08d/08e、原件、消费和 UNKNOWN 全部保留。
九代维护每代 1296 MiB/370 inodes/120 CPU-s，累计 **11664 MiB/3330 inodes**，
加原核心 capture 64 MiB/16 为 **11728 MiB/3346 inodes**，名义 1080 CPU-s。
不按失败小产物减账，不释放旧实际用量或未知义务。

继承 QI/GS 全部单次边界：维护 900/780 秒、最多两次固定 SSH/ConnectionAttempts=1，
备份 320 MiB、目标 576 MiB、capture 8 MiB/32 inodes、每流 1 MiB、CPU 120s、
RSS 512 MiB、AS 256 MiB、FD128、8 控制子进程、VM 4 vCPU/8192 MiB；两源各
98304 B、bundle 49152/393216 B。核心 900/800/750 秒、四旧加新
1380 MiB/82560 inodes/10450 CPU-s 及更早义务、新核心 276 MiB/16512 inodes/
2090 CPU-s、32 MiB 包、1 MiB approved-input、60 MiB 输出、64 MiB capture/reserve。
短预检 4096 B、marker/transition 65536 B、journal 至少 400 MiB/32768 inodes。
删除观察不换成其它工作额度；历史和新协议必须先证实仍装入原上限。

## 验收、披露与停止

验收证明不再发全量单元/模板查询，准确报告覆盖减少，保留上述每项保护并完成两侧
来源/历史/boot 接线；然后一次维护 VERIFIED，原 live finalizer 给出三个核心 verdict。
离线/CI 不能替代现场成功。后续 process、数据、关机或容量等真实条件仍可能失败，
本方案不保证“下次必过”。任何失败 STOP_AND_RETAIN，DS2 不完整则 DS3 NOT_RUN，
不重试、补采、清理、恢复、回滚、二次启动或自动另开窗口。

请求批准三文档及必要脱敏记录发布 main，并仅允许从已留存 08e 五件原件核对并公开
basename/bytes/SHA-256 最小索引，旧 D 固定为上述 fa30146。须与原私有索引及
保留副本一致，不因缺项或冲突补采/换件。云端未持有这些 pins，不填造数值或审阅事件。
08e 原文、新服务名/路径、Q1 当前捕获与 C10 原文仍私有；新 08f 索引不自动公开。

待决仅为此覆盖取舍、DS1–DS3 及上述限定披露。批准后范围内不逐子步骤再审批；
未经准确决定与独立 C，不改运行/测试源码、配置或执行新窗口。原 QI 失败仍按其
原保证解释，不追溯改写为本次较窄保证下的成功。
