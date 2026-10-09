# 恢复原任务运行时准备并完成核心验收

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-RUNTIME-CONTINUATION-v1`，RT1–RT3；三文档为一个完整批次。
输入修复 `93227cf3c859d1f8fbda78f5123d9102f8ced3ad`。
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、直接来源及完整性、Owner mandate/authority、
无例外和实质变更规则保持。批准后由本地 Codex 连续完成，不依赖 ChatGPT 逐步交接。

## 问题和唯一交付

[离线复核](../Q2_CORE_VM_ADOPTION_IMPLEMENTATION_REVIEW_20261009.md#09a-返回后的普通修复与离线接线复核)
发现原准备只在当次启动用户管理器，并将用户 slice 配置写入 `/run`；VM 重启接线没有
恢复这些前提。维护仍要求用户 bus，核心还需要五个 system slice 和一个 retained user slice。
核心原 ordinary locator 来自旧 user plan，导致它和 retained ordinary 使用同一 unit 名、
同一 system 查询结果，却分别要求 32/64 tasks，无法同时满足。

09a 的 ENOENT 仍没有具体缺失路径证据。上述源码缺口不作为历史现场根因的断言。
历史系统准备 plan 也不证明 system ordinary slice 已创建；本方案明确处理其存在或缺席。
普通 cgroup 路径表示修复已单独完成，不代替本方案。

交付只包括：准确恢复这些原任务运行时前提，完成一次剩余 journal 256→512 MiB 维护，
成功后执行原未发行 `lhqcore-20261007a` 的 H01 正常任务及结果、Q4 运行取消、H11 同任务恢复。
没有额外诊断 SSH、单独观察窗口、包重装、额外 VM 启动、后台机制或其它功能。

## 请求批准的范围

- RT1：完成固定历史来源到当前 system/user 角色的显式映射、维护前后运行时准备及两侧
  返回验证；实现、相关测试、真实保留来源及大小核对、main 发布、准确 D 首次 CI、独立
  安装验证、维护与条件核心 caller 冻结。原安装保留，范围内不逐子步骤重复批准。
- RT2：唯一新维护 `lhqjgrow-20261009b`。最多两次原连接 SSH（pre/post）。每个 boot
  仅一次准备原用户管理器、五个固定 system slice 和一个固定 user slice；已有正确对象
  复用，缺失的两种 slice 运行时配置按固定来源创建，冲突即停。完整校验后才正常关机、
  备份/增长、一次维护内原配置启动及 ext4 增长。具体准入和动作见架构。
- RT3：仅 RT2 全部成功原件验证后，同一 D 发行一次原07a核心批次。失败时不换名、
  不重发；RT3 不能在 RT2 失败后单独执行。

这是对旧 VA1“guest 仅更换 session”的明确扩展，包括限定的运行时创建/启动和角色接线；
不是重放已消费09a。十旧窗口、旧 caller、UNKNOWN 和旧原件均保持。
所有首次失败均 STOP_AND_RETAIN；不自动重试、补采、停止业务服务、清理、回滚、恢复或再开窗口。
已经正确运行的目标不重启，未知或异常目标不修复后重试。

## 不变保护与资源

沿用已核验的 repaired VM、当前身份接入和原五盘配置；不重新安装 quota 包。
保留 DS 的19服务/7域/7 cgroup、准确Q1来源、业务进程/根目录/writer、quota/ext4/UUID/
内容、正常关机和前后身份保护。启动目标只限已声明的任务父域及它们原来需要的 UID 1100
用户管理器与 runtime-dir 服务，不启动历史业务 unit，不把用户 bus 缺席当作静止成功。
原 trusted-single-admin 与 declared-startup 管理前提覆盖准备、维护及核心交接；
unknown-startup 观察仍降低，continuous exclusion 仍未证明，未知/矛盾即停。

新增一代后，十一代维护完整义务为 **14256 MiB / 4070 inodes / 1320 CPU-s**；
加原核心捕获64 MiB/16 inodes，宿主底线为 **14320 MiB / 4086 inodes**。
不按实际小返回减账，不抵销旧失败。运行时配置的新增成本另按架构计入对应 guest pool，
不从旧承诺中退款；这不是增加执行时间、CPU、RSS、FD 或输出上限。

维护原900/780秒、CPU120秒、RSS512 MiB、AS256 MiB、FD128、8控制子进程、VM4 vCPU/
8192 MiB保持；准备计入同一累计时钟和额度。每个 boot 的准备最多12个控制命令、60秒，
也受剩余总期限约束，不能另开计时窗口。双源各98304 B、bundle49152/393216 B、
短预检4096 B、marker/transition65536 B、单流1 MiB保持。核心原900/800/750秒、
32 MiB包、1 MiB approved-input及原各项准入保持。任何静态大小/费用不适配须先修正实现，
不得先消耗现场窗口或放宽上限。

## 验收和披露

成功必须同时具备：维护完整 VERIFIED、重启前后准确运行时角色证据、原 live finalizer
三个实际 verdict。CI、源码复核、单独准备成功均不算核心 PASS。

请求批准这三文档、实现和必要脱敏记录发布到既有 `kongbu0621/infra-local-hand` main，
并仅披露旧09a五原件 basename/bytes/SHA-256 索引，用于新增历史 profile。
私有核对事件 `VA2-09A-ORIGINALS-INDEX-REVIEW-20261009-01` 已与原私有索引及保留原件核对。
旧09a原文、机器目标名/路径、PID/boot、启动30件及索引、新09b原件及索引继续私有。
真实 Owner B 和独立 C 完成前，本提案不授予新运行时动作、实现或现场窗口。
