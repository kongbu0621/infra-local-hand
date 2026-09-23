# E3 验收准备：已确认的实现与装配缺口

日期：2026-09-23。只读核查对象：`39d45a1c652289949f683e69c8ebb6bfff944bb1`。
本文件是 E1–E3 已批准范围内的实现核查记录，不修改三份权威文档、批准基线或 Gate，不授权生产部署、主机提权、故障注入或真实 NAS 操作。

**结论：当前不能直接在一台具备 systemd 的主机上运行现有测试并取得 E3 PASS。**
真实测试入口尚为占位；独立宿主 fixture/harness 未实现；当前 project-quota 查询与固定 upstream 权限模型存在冲突。
下面区分源码事实、由源码得出的影响判断，以及尚需目标主机验证的事项。目标内核的 backport、LSM 和实际 unit 行为仍待补证。

后续进展：GX10 的 nsfs 修复已完成实机重测；[一次性输入确认](GX10_E3_INPUT_CONFIRMATION_VERIFICATION.md)
结论为 NOT_PREPARED，结束重复盘点。[quota/harness 变更方案](e3-quota-harness/REQUIREMENTS.md)
已明确推荐独立管理侧观察组件及真实测试入口，但尚未批准或实现；新的受信边界按根 AGENTS 的 OPEN 范围处理。
下面保留本次缺口核查时的事实与候选方向，不能把后续提案理解为缺口已修复。

## 1. 当前真实测试没有可执行验收主体

[`tests/test_local_hand_jobs_runner.py`](../../tests/test_local_hand_jobs_runner.py) 中
`test_real_delegated_cgroup_integration_is_not_a_simulated_pass` 调用无配置的
`SystemdManager().support()`，不支持时 `skipTest`；即使支持结果将来变成 true，随后仍直接
`self.fail`，要求补充真实 admitted-manager fixture。它不是等待提供某个环境变量即可执行的完整测试。

[`runner.py`](../../tools/local_hand_jobs/runner.py) 的 `SystemdManager.support()` 固定包含
`E3_SUPERVISION_UNVERIFIED`。其余检查只有 Linux、PID 1、cgroup v2 控制器文件、配置路径的
`cgroup.procs` 可写性及匹配的非 root UID 等初步条件；没有证明 user manager 可用、有效控制器已委派、
每个 namespace 设置生效、project quota 可查询或硬限制已经实际执行。

因此，现有 SKIP 正确表示未验收。合成测试中的可信 Python DI、模拟 quota/cgroup 观察、
真实本地文件或匿名管道测试，都不能替代真实的三 unit 监督验收。

## 2. Project quota 的权限模型冲突

当前 `_verify_project_quota` 的实际路径是：

1. `_mount_for` 只接受 ext4/xfs；打开准确 root 并核对 device/inode/uid。
2. `FS_IOC_FSGETXATTR` 取得非零 project ID 和继承标志。
3. 对 `mount["source"]` 调用 libc `quotactl`，命令为 `Q_GETQUOTA`、类型为 `PRJQUOTA`。
4. 要求非零有限 hard limit，且不大于已准入上限。

Linux v6.12 固定源码的 `check_quotactl_permission()` 对查询本人 user quota 或所属 group quota
有豁免；project quota 不在豁免范围。其短摘录为：

```c
if (!capable(CAP_SYS_ADMIN))
    return -EPERM;
```

同版本 `capable()` 的定义明确使用初始 user namespace：

```c
return ns_capable(&init_user_ns, cap);
```

当前三个 unit 使用 user manager，要求专用非 root 账户，且固定设置 `PrivateUsers=yes`。
systemd v257 手册说明该设置不保留 host user namespace 的 capabilities，服务 namespace 内的能力
不能替代 host 的能力。对应原文短摘录是：

> all unit processes are run without privileges in the host user namespace

**据此推断：即使部署侧事先正确配置 project quota，在这组固定 upstream
语义下，当前 bootstrap 仍无法凭自己的 user-namespace 能力通过上述查询权限检查。**

该判断不是目标主机实测 errno。系统可能先在设备路径、filesystem quota 支持、LSM 或其他准入点失败；
目标发行版内核是否修改相关语义也尚未验证。不得预填每台主机都实际返回了 EPERM。

## 3. EXT4、XFS 和设备路径不能混为一个条件

同一 Linux 固定源码中，generic `do_quotactl()` 先检查 quota 支持和权限，再分派 `Q_GETQUOTA`。
EXT4 的 `.get_dqblk` 对应 `dquot_get_dqblk`；XFS 的对应实现是 `xfs_fs_get_dqblk`。
因此，当前使用的 generic 查询路径不会因为把 EXT4 换成 XFS 就避开前述权限检查。
Filesystem 类型正确也不证明 quota 已启用、正在强制执行或项目继承关系正确。

另一个独立条件是设备路径：当前将 mountinfo 的 `source` 作为 `quotactl` 的 block-device 路径。
Linux `quotactl_block()` 会先执行 `lookup_bdev`，再取得 superblock 并进入权限检查。
systemd 的固定 `PrivateDevices=yes` 会给服务提供不包含物理块设备的新 `/dev`。
由此，原 source 节点在 unit 内可能不可见，查询可能先以设备路径相关 errno 失败。
这不能通过关闭设备隔离、添加任意设备访问权或临时换一个 mount source 静默解决。

`quotactl_fd` 是可以研究的准确文件描述符定位方式，但同一 upstream 实现仍调用
`do_quotactl()`；只更换入口并不消除权限要求或以下阻塞／元数据语义。

## 4. “查询”不等于保证无写入或无阻塞；现有 errno 也未保存

Linux 的 `quotactl_cmd_write()` 将 `Q_GETQUOTA` 归入需要 write/thaw 协调的路径。
源码解释其 quota-acquisition 路径可能分配配额元数据；若 filesystem 处于冻结状态，
`quotactl_block()` 的相关路径会等待解冻。这不表示每次 EXT4/XFS 查询都必然修改数据，
但足以说明当前 runner 注释中的“read-only kernel query”不是严格的零副作用保证。

因此，本轮**只读 readiness probe 不执行 `Q_GETQUOTA`**，也不在控制线程中为探测 quota
打开任意挂载或等待解冻。需要实际调用的 quota 测试应属于另行明确影响根、故障解除条件和监督边界的
隔离宿主验收步骤；其结果不能由主机只读库存代替。

当前诊断缺口也应在实现前明确：

- libc 通过 `ctypes.CDLL(None, use_errno=True)` 调用，但代码没有读取并记录 `ctypes.get_errno()`。
- `quotactl` 非零返回、hard limit 为零、hard limit 超出准入值，会落入同一个 `UNSUPPORTED` 信息。
- `os.open`／`ioctl` 的 `OSError` 虽保留 Python cause，但 bootstrap 的 stdout/stderr 均为 null；
  manager 只看到 unit 退出状态，当前没有传回可用于验收的逐项原始 syscall errno 证据。

未来隔离验收需区分准确 syscall/命令、返回值、即时 errno、原 root/mount/project 身份与准入上限；
不能把一般 `UNSUPPORTED` 反向解释为已经观察到 EPERM、配额不存在或配额未生效。本轮不修改生产诊断路径。

## 5. 尚缺的真实 harness 与最小验收顺序

| 顺序 | 所需实际证据 | 现状与禁止替代 |
| --- | --- | --- |
| 宿主准入 | 准确源码／安装身份、专用 UID、user manager、固定 slice/cgroup、已预建本地 roots/store 的身份、原有限预算 | 只读库存可以收集；不能从 PID 1 是 systemd 推出这些条件全部满足 |
| 测试装配 | 独立 test-only harness、合成任务与影响根、受保护私有 fixture、准确 unit/intent 台账和退出后保留策略 | 尚未实现；不能直接把 production support 改成 true 或用模拟返回值充当宿主资格 |
| 配额前置 | 原 unit namespace 下的准确查询结果、hard-limit/继承/总额度实际证据，并解决本文件的权限与设备定位冲突 | 当前实现 BLOCKED；仅预配置 quota、读到配置文本或选择 ext4/xfs 均不够 |
| 三 unit 正常链 | bootstrap→helper→reader 的独立交付、原 boot/invocation/cgroup、真实 namespace 与 readonly/writable 边界、完整结果传输 | 现有行为仅有合成验证，不能据此清除 E3 封堵 |
| 原预算与取消 | 三份 CPU 原分额、同一绝对截止、RSS/进程数/日志/文件与配额上限；子孙进程、排队启动、TERM/KILL 及真实退出 | 需记录实际 cgroup 属性和计数；配置请求、超时或发送 KILL 都不是执行上限／退出证明 |
| 故障与恢复 | 每次 intent/delivery/receipt、reader 管道与 broker 崩溃窗口；原身份观察，不重投、不续额、UNKNOWN 不释放 | 需真实 manager 与持久账本，不以普通 process-group 或单个 PID 替代 |
| 阻塞 I/O | 专属隔离存储条件下 bootstrap/helper/reader 挂起，status/cancel 有限响应，未确认退出继续屏障 | 没有固定、可解除的隔离故障 fixture 时列 BLOCKED；不得冻结主机根盘、全机断网或操作真实 NAS |

已有 `_verify_cgroup_limits` 检查实际 `memory.max`、`pids.max`、`cpu.max` 比率及
`RLIMIT_FSIZE`，但它本身不构成触发限制、统计全部子孙累计 CPU、验证终止宽限或故障恢复的实测。
真实结果必须逐项记录 PASS/FAIL/UNSUPPORTED/BLOCKED；不能用总体测试计数覆盖尚未运行的项。

## 6. 尚未实施的候选解决方向

这里只列待评估方向，不选择或批准新的生产权限边界：

- 明确能够在当前隔离身份中取得并核验 quota 事实的机制，以及事实与 root、mount、project、
  预算、有效期和可能变化的绑定；不接受一个表示“配额已配置”的布尔值或过期快照。
- 评估基于准确 FD 的定位与受信观测协议分别能解决什么；明确 FD 定位本身不解决 host capability 要求。
- 将真实宿主 harness 的资格检查、受限测试授权和生产支持声明分开；验收入口必须执行真实系统调用和
  原生产监督路径，不能隐藏模拟条件或给公开请求增加绕过开关。
- 若方案需要新增受信进程、能力或改变隔离边界，先按既有文档与变更规则评估。当前记录不启动
  root helper、不授予 `CAP_SYS_ADMIN`、不关闭 `PrivateUsers`／`PrivateDevices`，也不自行重开 Gate。

## 7. 固定官方来源与完整性

以下源码均经 GitHub Connector 按完整 commit 再次读取。Linux v6.12 标签解析为
`adc218676eef25575469234709c2d87185ca223a`；systemd v257 解析为
`70bae7648f2c18010187c9cf20093155eaa26029`。表中 Git blob 用于核对读取内容，不是目标主机版本证明。

| 官方文件 | Git blob | 本文使用的事实 |
| --- | --- | --- |
| [Linux fs/quota/quota.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/quota/quota.c) | `290157bc7bec2c8101713471510d248865a5bd38` | 权限检查、generic 分派、设备定位、write/thaw 与 fd 入口 |
| [Linux kernel/capability.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/kernel/capability.c) | `dac4df77e376ec01268528f1464c52064861f89a` | `capable()` 使用初始 user namespace |
| [Linux fs/ext4/super.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/ext4/super.c) | `16a4ce704460e141cebba38b88513221ca16461e` | EXT4 generic get-dqblk 接口 |
| [Linux fs/xfs/xfs_quotaops.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/xfs/xfs_quotaops.c) | `4c7f7ce4fd2f4238e1ed14012ec5cacc01edcfd1` | XFS get-dqblk 接口及 quota 未启用分支 |
| [systemd man/systemd.exec.xml](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/man/systemd.exec.xml) | `14075cb4e7d5ceec0f878fbb0fafe1a86d6b7ecc` | PrivateUsers 的 host capability 边界；PrivateDevices 的设备可见性；user service namespace 的条件 |

保守结论保持为：**固定 upstream 权限模型与当前实现冲突；目标主机 backport/LSM、原 namespace 下的
准确失败点和 errno，以及可行修复方案均待后续隔离验证。当前生产 `E3_SUPERVISION_UNVERIFIED` 保持。**
