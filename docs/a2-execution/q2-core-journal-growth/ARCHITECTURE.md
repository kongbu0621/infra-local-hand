# 核心 journal 保留数据扩容架构

状态 **PROPOSED / Gate OPEN**，scope `LH-Q2-CORE-JOURNAL-GROWTH-v1`，仅 J1–J3。
[需求](REQUIREMENTS.md)定义唯一对象、预算、两条维护连接和必须接受的停机边界；本文不改变原核心合同。

## 组件与固定来源

以 main `3412fa65c5fdced51db4254e44dfbc4d8ad9f89b` 为源码检查基线。
新增 test-only host 维护 coordinator 与两个固定阶段的 guest helper；不修改 Local Hand runtime、
wheel、业务 harness、quota observer、bootstrap、dispatcher 或空 release allowlist。
coordinator 负责准确输入、一次性消费、离线备份/镜像处理、单次启动和受保护捕获；
helper 负责 guest 当前身份、静止/启动风险检查、原 journal 内容比较及条件关机/增长。
不建立通用远程 shell API；不复用任何已经消费的 runner 的 run/main。

原受保护管理 anchor 仍由固定本地 frame 中 `sources/P` 的 WRAPPER parent 定位。
frame SHA-256 `c9f4bb2744d48f9e7174157a95761d081be038cf4dd4f67ae42620a1a9e6d315`，
P SHA-256 `5eef22e497e9e0a867470c6c490336dc80fadd0e506e3419847e6c37b687918b`。
原 plan 9814 B，SHA-256 `efff343c7967dcc43c54420accafb2e91a5b4fb563419b00a86d41a58817fa7c`，
仍来自原固定 guest archive/member，不在新工作中搜索替代副本。

| 固定管理来源 | SHA-256 |
| --- | --- |
| start.sh | `1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a` |
| ssh.sh | `aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63` |
| user-data | `5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523` |
| public key | `e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c` |
| known_hosts | `d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd` |
| 已保存容量 stdout | `00cc8b744b8d63bf7d83a4044921fc1a80b7a21b289cf62b4e6f33cd9548b8db` |

保留既有 root-owned executable、祖先/no-follow、O_NOATIME、single-link、owner/mode 和名称/fd 复核。
本地小头部观察仅指导方案；J3 必须重新验证实际进程和设备，不能从启动脚本推断当前进程完全相同。
目标镜像必须是准确 start.sh 的 journal drive 对象、原 anchor 内的单链接普通文件；
guest 目标必须同时匹配原 plan journal 路径、保存输出中的 UUID、virtio serial 与当前 mount/block 关系。
实际设备名仅来自这些匹配，不固定假定 `/dev/vdc`。拒绝分区、LVM、backing/snapshot、加密、替换或额外 writer。

## 维护状态与拒绝点

状态单向：LOCAL_CHECKED → CONSUMED → GUEST_QUIET → POWERED_OFF → BACKED_UP →
IMAGE_GROWN → BOOTED → FILESYSTEM_GROWN → VERIFIED。每个阶段只能进入一次。
失败进入 STOP_AND_RETAIN；下一次进程启动发现 marker 或任一目标输出存在即拒绝，不恢复执行。
原 marker/receipt 和任一历史 deadline 都不修改。

1. 本地核对 R/A/B/C/D、管理 pins、全部四旧核心和两旧诊断原件、原镜像/进程身份及预算。
   读取原 vm.pid 只是定位；须用持有的 pidfd、进程启动标记、root-owned QEMU executable、
   完整参数及四盘/seed/network 关系共同核验。无法读取或发现多个实例/未知 writer 即停止。
   不以 kill(pid,0)、文件锁空闲或截图单独证明身份/静止。
2. 建立 O_EXCL 0600 marker，写入全部绑定、原时钟和两个准确阶段命令的摘要并 fsync。
   第一条 SSH 只读取既有固定旧 scope/安装对应的 systemd/cgroup/process 状态、必要启动关系及
   journal 的 mount/block/文件树；只扫描这台隔离 VM 内判断 writer/自动启动所必需的范围。
   对未知启动依赖或无法穷尽的写入方 fail closed，不停用 unit 来制造静止。
   状态必须可解释为所有旧业务域当前不活跃且不会自动恢复；历史退出仍 UNKNOWN。
   旧账本/必要证据不得仅存在于将消失的 tmpfs。检查通过、前摘要完整回收后，才在同一连接中
   允许 host 发送一次固定继续令牌，guest 请求正常 poweroff。无令牌不关机；不用第二连接关机。
3. host 观察原持有 pidfd 退出及原镜像没有其它 writer，然后才运行 qemu-img 的正常锁定检查。
   不使用 `-U`、强制共享、修复 check 的 `-r`、force 或 ignore-locks。离线 info/check 必须通过，
   仍为 256 MiB、无 backing/snapshot/encryption。连接断开或 SSH wait 非零不能替代 VM 停写证据；
   预期 poweroff 导致的断流单独记录，只有已收固定确认及 host 退出/锁证据才能继续。
4. 创建唯一备份，受限流式复制全部原镜像字节，fsync，重新读取比对完整 SHA-256/长度/身份。
   不稀释为文件树摘要、增量、reflink 或运行中拷贝。稳定单写管理边界和工具锁均保持。
   然后一次 qemu-img resize，显式 qcow2、目标 536870912 B，不改其它格式选项；再次正常 info/check。
   对备份与扩容后镜像作有界逻辑内容比较，旧 256 MiB 内容相同且新增区读零才可启动。
5. 不执行旧 start.sh。从其固定配置形成审阅/测试的准确 QEMU argv，仅将 pidfile 改为
   本次唯一文件、serial backend 改为 `null`，避免覆盖历史或无限捕获；
   CPU/RAM、磁盘/serial 标识、seed、网络、固件等字节等价，仍保留同一串口设备。
   不新增 monitor/QMP，不用后台 shell 重试。parent/pidfd 和单实例 guard 保护唯一一次启动。
   保留原 daemonize 模式；父命令返回 0、正确新 pidfd/镜像绑定持续存在后，被动等候 60s，
   不发探测 SSH/TCP；原双时钟和 780s 启动点内条件满足才发第二条 SSH。连接失败不再试。
   60s 不是 SSH 必然就绪保证；不把 daemonize 返回当成 guest 已启动成功。
6. 第二 helper 先确认新 boot 与同一 VM 关系、原 host key、journal UUID/挂载选项、整块目标大小
   512 MiB、静止条件和前树摘要；不重新运行任何业务。固定 root-owned resize2fs 路径/版本/文件摘要
   须在第一阶段绑定、第二阶段相同。缺工具不安装；online resize 不支持就停止，不换离线路线。
   一次非 force 增长，不改变保留块比例、UUID 或 feature flags。完成后确认原文件内容、路径、owner/mode、
   链接关系和 mtime 保留；FS 自身大小/元数据及 boot 必然变化，不能宣称全字节不变。
   返回固定五 parent 的新身份/容量和 journal 后摘要，与前摘要及原 pins 比对。

guest helper 的内容枚举须有字节/条目界、no-follow/O_NOATIME 和不跨 mount；遇不支持对象、
并发变化或必要证据不完整即停止。只传前后摘要和必要私有结构，不把历史文件原文上传公共仓库。
原文件的 atime 不以弱读回退改变；支持性缺失是前置阻断。

## 传输、保存及风险

沿用准确容量观察 D `dafa4360c1b62c59677236ab93da5af203fac240` 的显式固定 SSH 选项原则、
既有 endpoint/host key/凭据，禁用 agent、proxy、forwarding、PTY、multiplex、配置隐式读取。
第一阶段仅增加一个长度固定、绑定本次 nonce/前摘要的 stdin 继续令牌；不提供任意命令输入。
第二阶段 stdin EOF。guest 通过原 sudo/env/Python 入口运行；不修改 SSH 或 sudo 配置。

所有新文件在原保护 anchor，固定 `.lhqjgrow-20261006a.` 前缀：consumed.json、events.jsonl、
pre.stdout、pre.stderr、post.stdout、post.stderr、receipt.json、vm.pid、journal.backup.qcow2。
除备份外共同受 8 MiB/32 inode 上限；events 追加、其余 create-only，不覆盖历史 vm.pid/serial。
备份独立 320 MiB 池。pidfile 是 QEMU 唯一新增的控制输出；四个原磁盘仍可能接收正常 OS 写入，
不复制私钥、system/quota/evidence 镜像。准确 argv 的 pidfile/serial 差异必须冻结并验证，
串口原文没有回收，不描述为零字节成功日志。旧 start.sh/vm.pid/serial 原件保持，不运行其重启入口。

receipt 明确记录每步是否开始/返回、退出码、流 EOF、预算观测、旧/新 boot 摘要、镜像与备份摘要、
前后目录摘要、当前容量和未闭合进程。能回收多少就保留多少，不能伪造未返回步骤的成功。
严格服从需求的维护中断规则：不在超时中强杀 mutator、不自动回滚或第二次启动。
介质错误、掉电或超时可能留下损坏/关机 guest；有备份仍不构成完整 VM 自动恢复保证。
原管理信任、历史 UNKNOWN 和非排他存储保持披露。

维护后只是生成新 boot 的可核实交接，不修改核心的旧 boot 校验或批准新业务。
持久账本/原 unit 身份原样保留，丢失的内核 invocation 不能补写为旧身份。
