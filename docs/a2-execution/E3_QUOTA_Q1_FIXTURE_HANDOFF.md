# Q1 隔离 fixture：离线配置检查与实测交接

本文件是执行交接，不替换 `LH-E3-QUOTA-HARNESS-v1` 的三份权威文档。
批准 A 为 `415327ebdcc251bb055da9931a7a88990f750b7a`，独立 C 为
`5a4ea852091db06549a876e42bbd5f95d5869d3b`；范围见根 `AGENTS.md`。
当前管理侧源码及既有验证见 [Q1 README](../../tools/admin/local_hand_quota_observer/README.md)
和[运行装配验证记录](E3_QUOTA_Q1_RUNTIME_VERIFICATION.md)。本轮离线入口源码为
`c0b817b2b97be26d13053a4ce74d29c6dcaeac05`，见[离线配置验证记录](E3_QUOTA_Q1_FIXTURE_VERIFICATION.md)。

**实际输入仍为 NOT_PREPARED，Q1 实机与整体 E3 仍 BLOCKED。** 本轮交付离线检查入口，
不创建账户、FS、quota、slice、服务或安装目录，不再次盘点 GX10，也不启动查询。
下列占位符必须由既有管理入口的准确私有交付替换；它们不是主机默认值或待执行的配置。

## 1. 管理侧待交付的准确输入

| 交付项 | 必需字段及来源 |
| --- | --- |
| 候选和构建 | 干净完整 source commit/tree、逐文件 SHA-256；native 的源码、filter header、编译命令、编译器/headers、架构/ABI 和 binary 摘要。目标 binary 不链接测试 syscall shim |
| manifest 快照 | `local-hand-quota-q1-manifest/v1` 的原始字节及外部固定 SHA-256；authority/installation 摘要、source commit、boot ID、epoch、query UID/EUID、ABI sizes、cgroup parent、max_query_ns、slots |
| 每个 slot | ref/generation、准确路径、ext4/XFS、真实 FS UUID、root 的 device/inode/uid/gid/mode、project ID、继承 xflags、有限 hard_bytes；管理员另交独占、无其他 writer、稳定代次和真实 UUID 来源证据 |
| runtime 快照 | `local-hand-quota-runtime/v1` 的原始字节及外部固定 SHA-256；manifest 安装路径/摘要，Python/worker/native/systemd-run/systemctl 准确路径/摘要，三个 package_files 摘要，query slice、parent cgroup 与初始 user namespace 的 dev/inode，以及 memory/tasks/CPU/output 限额 |
| 控制账本 | 预建 journal 的绝对路径、dev/inode、实际管理 owner UID 和 0700 权限；独立有限本地存储、可保留容量及原记录。该目录与每个 slot、全部配置和安装输入互不交叠 |
| 独立控制器 | 树外专用控制器的源码/安装摘要、准确监督单元及 cgroup、时间/CPU/内存/进程/输出限额、停止入口和责任人；query 的父 slice 必须预建、独占且持续保留 |
| 系统和证据 | 准确 kernel/systemd/Python、stdlib、ELF loader/shared libraries 基准；私有原始日志位置、证据与封存峰值容量、保留策略、逐项停止/解除方法和管理交付来源 |

`package_files` 只含 `admission.py`、`protected_inputs.py`、`supervision.py`。
`installation_digest` 不覆盖 `systemd_runtime.py`、`journal.py`、整个控制器或系统依赖；
这些必须由外层 fixture 单独固定，不能用一个摘要冒充完整管理基准。
文件摘要证明字节一致，不能独立认证管理员来源、保护权限或当前宿主事实。

安装输入的每级祖先须符合现有 root 所有、不可被非 root 写入的检查，文件不接受符号链接、
setid、额外硬链接或可执行 file capability。常见 `python3`、systemd 工具路径可能是符号链接：
管理员须交付最终真实 ELF 的 canonical path 和摘要；程序不自动 resolve 或猜测替代路径。
manifest 中 root 为普通专用 UID 的 0700 目录；这不把普通作业提升为查询管理员。

## 2. 摘要装配顺序

安装摘要刻意排除 manifest/config 的相互引用，按下列顺序装配即可避免哈希循环：

1. 固定准确候选、目标平台产物、安装路径及各文件摘要。按 `installation_digest` 的既定规则，
   对十个 `*_path`/`*_sha256` 安装字段和 `package_files` 对象作
   `json.dumps(value, sort_keys=True, separators=(",", ":")).encode()`，计算 SHA-256。
   十个字段分别对应 Python、worker、native、systemd-run、systemctl；不含 manifest path/digest、
   runtime 文件摘要、资源限制或 host 身份。
2. 将该安装摘要连同管理侧交付的其余事实写入完整 manifest；冻结其**原始字节**并计算
   `manifest_digest`。不把文件的解析后重排版本当作相同快照。
3. 将 manifest 的准确安装路径/摘要和相同安装字段写入完整 runtime；冻结原始字节并计算
   `runtime_digest`。runtime 的摘要通过外部受信交付固定，不写入其自身 JSON。
4. 私有交接同时固定两份快照、两项外部摘要、准确 source commit、runtime 安装路径和 journal 路径。
   后续任何字节、安装路径或宿主代次变化都重新装配并保留原版本；不能只修改单个摘要掩盖变化。

ABI sizes 来自准确目标构建和后续实测，不能沿用另一架构数值。
离线阶段不生成运行 ticket、request/allocation、BOOTTIME 时间或 journal 意图；
这些必须在真实执行装配中绑定原始身份和原截止时间。

## 3. 只检查已交付快照

下列是参数说明，所有大写项和尖括号内容均为占位符，当前没有可替换它们的真实交付：

```sh
python -I -B tools/validate_q1_fixture.py \
  --manifest-snapshot '<已交付manifest快照文件>' \
  --manifest-sha256 MANIFEST_SHA256 \
  --runtime-snapshot '<已交付runtime快照文件>' \
  --runtime-sha256 RUNTIME_SHA256 \
  --source-commit FULL_SHA \
  --runtime-path '<准确runtime绝对安装路径>' \
  --journal-path '<准确journal绝对路径>'
```

快照文件位置可以不同于实际安装位置；`runtime_path`、manifest 内 slot 路径和 runtime 内安装路径
在此只作词法及交叠检查，不打开它们或推导当前主机身份。CLI 只读取显式交付的两份快照；
不执行其中的代码、启动进程、创建账本或查询 systemd/quota。

检查器复用现有严格解码，核对外部摘要、source commit、manifest/installation 绑定、管理查询
UID/EUID 均为 0、专用 slice/cgroup 关系，以及**全部 slot**与配置/安装/journal 的路径几何；
同时拒绝配置和安装文件路径的别名及祖先关系。计费容量按 FS UUID/project 域去重，不能重复累加共享额度。

CLI 仅支持 Linux，须以 `-I -B` 启动；只对输入快照作普通文件、逐路径 NOFOLLOW、字节上限和
读取前后元数据检查。manifest 上限 32 KiB、runtime 上限 16 KiB；存储 I/O 没有 wall-time 保证。
返回码 0 仅表示 `CONFIG_CONSISTENT`，2 表示拒绝或命令行用法错误，3 表示平台不支持。
结果证据类别固定为 `OFFLINE_ONLY`。
`admission_proven`、`real_e3_accepted`、`production_supported` 始终为 false。
缺失输入时项目交接状态保持 NOT_PREPARED；CLI 缺文件返回 `REJECTED/SNAPSHOT_IO`，
缺必填参数则返回 argparse 用法错误。摘要/字段/路径矛盾应修正交付并保留原失败，不能改成忽略检查。
即使一致性检查通过，真实保护权限、FS UUID、quota、namespace、监督和退出仍待现场证明。

## 4. Q1 真实出口与后续阶段

以下是已交付隔离 fixture 上的后续验证顺序，不是本次启动指令；尚无完整一键 Q1 验收入口。
后续新增的[单次管理实验入口](E3_QUOTA_Q1_EXPERIMENT_HANDOFF.md)连接原票据运行/恢复和实际监督核验；
它仍依赖外层受信启动器及准确隔离 fixture，不替代下表全部出口。
每步先固定准确实施入口、作用对象和证据方式，再由既有管理流程安排；缺条件时停止依赖步骤。

| 顺序 | 必须取得的真实证据 | 不满足时 |
| --- | --- | --- |
| 交付核对 | 准确候选/安装/系统基准、当前 boot、独占 FS/普通 UID/roots、真实 UUID、初始 namespace、持续父 cgroup、树外监督、有限账本和证据容量 | NOT_PREPARED / BLOCKED，不由检查器准备宿主 |
| 原权限对照 | 原普通隔离身份的 generic 查询与 FD 定位结果、准确 syscall/即时 errno、设备与 namespace 事实；保留最先发生的真实失败 | 不预填 EPERM，不给普通作业 root/CAP_SYS_ADMIN 或关闭原隔离 |
| 管理侧单次观察 | 准确 ABI、能力和 seccomp 生效；同 FD 的根/project/继承前后事实、真实 FS 绑定、accounting/enforcement、hard bytes；原 stdout/stderr 与逐 syscall rc/errno | 拒绝/UNSUPPORTED/IO_UNCERTAIN 原样保存，不换 API 或重试取得成功 |
| 停止与保留 | 原 boot/unit/InvocationID/cgroup、queued job、launcher/control/collector、双 EOF 和递归父树空；全部在原 query deadline 内，原失败与清理失败分别保留 | UNKNOWN 保持占用；额外清理时间不转为成功 |
| 强制与边界 | 有限合成超限写入的真实硬配额拒绝、计费域唯一和合并峰值；普通身份不能改 project/继承或写出计费域；准确负例与停止记录 | 仅有 hard limit/enforcement 标志或 ENOSPC 不算完成证明 |
| Q1 出口审阅 | 上述事实与准确来源一致，普通身份失败和管理侧结果分别留存，缺失项均列明；实际 ABI/权限/绑定/强制条件成立 | Q1 仍 BLOCKED，不假定成功进入 Q2 |
| 后续 Q2 → Q3 → Q4 | Q2 认证通信/receipt/原分配与预算；Q3 同生产核心真实三单元 H01–H05；Q4 H06–H13 故障/恢复与独立复核 | 分项保留阻塞，不提前移除生产封堵或宣称 E3 PASS |

原始证据至少含准确命令/版本/时间/退出码、源码与产物摘要、配置原件、boot/请求/原分配/slot
绑定、系统调用和 namespace 事实、资源计数、全部进程/单元停止或缺失事实，以及完整或部分输出。
真实主机原件按私有交接封存并校验 manifest/seal；Public 只保留脱敏结论与摘要。
普通开发离线测试记录不冒充实机原件，也不要求每次开发产生 ZIP。

## 5. 永久占用和停止语义

`StartJournal` 最多保留 32 个永久意图；文件与目录 fsync 后，首次调用最多交付一次。
成功、失败、取消、崩溃、响应丢失或 deadline 到期都不退款。原 request/allocation、逻辑 slot
（即使改 generation）、root dev/inode、FS UUID/project 计费域继续占用；没有 GC/reset/release 接口。

已有意图只能读原记录或观察/停止准确原身份，不能重新启动查询。需要另一个独立验证场景时，
必须先核对原停止/保留条件，再由管理侧交付真正不同、容量已计入的资源；新 id、换 generation、
删 journal 或重装实例都不能作为原未知操作的成功重试。容量不足即停止。

恢复缺原 InvocationID 时，不停止当前同名单元；原 launcher/pipe 归属丢失仍为 UNKNOWN。
TERM/KILL、单个 PID 消失、JSON 完整、空 `pending_clients` 或找不到叶 cgroup，都不是完整停止证明。
存在未知查询、排队启动、writer 或 collector 时，禁止变更 mount/project/limit、重新分配 root、
卸载观察服务或回收文件系统；保留原始失败、账本和资源，交由准确独立停止入口处理。

本交接不授予 GX10 准备/安装/切换或 E4–E6 权限。生产 `E3_SUPERVISION_UNVERIFIED` 保持。
