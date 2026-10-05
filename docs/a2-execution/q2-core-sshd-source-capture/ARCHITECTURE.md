# sshd 配置单次只读取证架构

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1`，仅 P1–P3。
R、源码基线、对象、预算、风险和排除项以[需求](REQUIREMENTS.md)为准；本文件定义如何固定一次取证，不是可执行脚本。
Owner B 和独立 C 之前不得创建 reader、runner、测试或执行 scaffold。

## 固定管理来源

复用源码基线 `46b08d9640ca19505fa02aa89d5d71d298536489` 中 `q2_core_delivery_entry.py` 和
`q2_core_delivery_freeze.py` 已有受保护路径、稳定读取、凭据关联和本地 writer 校验原则，不调用其业务 carrier 或消费入口。
`wrapper_argv` 只接受原核心 remote token，不能当作通用执行器。本范围在 C 后实现单独固定的诊断 argv 构造器，原 wrapper 不修改。

| 既有 anchor 内对象 | 原固定 SHA-256 |
| --- | --- |
| `ssh.sh` | `aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63` |
| `start.sh` | `1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a` |
| `user-data` | `5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523` |
| `id_ed25519.pub` | `e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c` |
| `known_hosts` | `d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd` |

私钥只在原受保护路径本地使用，不打印或打包；用已有受验证 `ssh-keygen -y` 的有界本地操作检查与固定公钥的关联，不新增远端试连。
anchor、文件 owner/mode、no-follow/no-atime、basename 与 held fd 身份须一致，endpoint 必须被上述已知 host key 覆盖。
额外私钥、自动证书 sidecar、agent/provider 不得成为认证来源；隐式证书 sidecar 若存在即停止，不读取它或扩大对象集。
校验原 `start.sh`、cloud-init 和 wrapper 是本地来源绑定，不执行它们、不将其视作当前 guest boot 或当前完整 sudo 策略证明。

本地 SSH 使用受验证 `/usr/bin/ssh`、隔离环境、`-F /dev/null`、固定密钥与 known_hosts、原回环地址/端口/账号。
新 argv 明确将原 `accept-new` 收紧为 `StrictHostKeyChecking=yes`，并固定 `UpdateHostKeys=no`、`CheckHostIP=no`、
`GlobalKnownHostsFile=/dev/null`、`VerifyHostKeyDNS=no`、`BatchMode=yes`、`IdentitiesOnly=yes`、`IdentityAgent=none`、
仅 publickey 认证、`ConnectionAttempts=1`、`ConnectTimeout=10`、`ControlMaster=no`、`ControlPath=none`、`ControlPersist=no`。
关闭 proxy/jump、转发、PTY、local command、DNS canonicalization 和密码交互，不创建 host-key 条目或控制 socket。
这些是本次命令参数，不修改 SSH 配置；其 key/连接行为依据 [OpenSSH 官方手册](https://man.openbsd.org/ssh_config)。
本地支持性必须离线检查，未知/不支持选项不得临场删去或 fallback。

唯一 remote command 由冻结 literal tokens 组成：原账号的非交互 shell `exec` → `/usr/bin/sudo -n --` →
`/usr/bin/env -i`（只保留固定 HOME=/root、PATH=/usr/bin:/bin、LANG=C、LC_ALL=C）→ `/usr/bin/python3 -I -B` 的固定 reader。
不传 shell 自由文本参数、配置路径参数或用户代码；无交互 shell、无 `systemd-run`、无额外 probe，无远端临时文件。
reader 的 bytes 与必要 literal launcher 一并计入 32768 B 源码上限，argv/environment 总计不超 65536 B。
解释器、stdlib、SSH/sudo 的固有执行与日志副作用属于需求中明确披露的诊断信任边界，不作业务运行时 attestation 声明。

## 消费及 capture 状态

主机选取原管理 anchor 中已绑定的同一 carrier capture 父目录，不接受 caller 另选输出位置。
仅以下四个新 basename，全部 mode 0600、single-link、O_EXCL/no-follow；父目录沿用既有保护，不创建新目录：

| basename | 最大内容长度 |
| --- | --- |
| `.lhqsshd-20261005a.consumed.json` | 4096 B |
| `.lhqsshd-20261005a.stdout` | 2097152 B |
| `.lhqsshd-20261005a.stderr` | 65536 B |
| `.lhqsshd-20261005a.receipt.json` | 65536 B |

内容合计最多 2232320 B，计入新 4 MiB/8 inode 承诺；实际分配量另观察，不以 sparse size、当前小占用或失败退款。
capture 父目录不变，原三批文件不覆盖、不追加、不修改。任何新名字存在（含 broken symlink）均拒绝。

状态顺序是仅本地预检 → O_EXCL marker → create-only 三个结果文件 → 最多一次 SSH → 封存 → 离线分析。
预检先核验准确 R/A/B/C/D、源码/命令摘要、私料和 writer、所有目标不存在、同设备 196 MiB/56 inode 可用条件。
winner 保留首次预检的 60s 双时钟起点。marker 和父目录持久化失败即停止，不发送；存在部分 marker 同样永久消费。
marker 绑定 A/C/D、固定 ID、source/argv digest 和原时钟，不包含原文或私钥。
marker 后任何错误也不得删除、覆盖或重试。只允许同一已打开 receipt fd 写出一次最终记录；部分结果不另建替代名字。

host 并行读取两个流，按配额先检查再写入；stdout 是快照载体，stderr 只私有保存，不在终端直接回显。
到第 55s 或任一超限即停止新读写/发送并终止本调用拥有的 SSH 子进程，在剩余窗口内有界 wait/封存；60s 不再继续等待。
不按进程名扫杀，不信号旧业务，不另开 SSH 验证。阻塞 I/O/无法停止导致的截止违约、部分文件或未知远端退出如实记录，不承诺一定能写成 receipt。

## 固定 reader 与结果格式

reader 核验自身 euid=0，初始化固定 rlimits/alarm，随后才打开需求允许的数据路径；任一限制不能设置即失败，无弱化重试。
[Python resource 文档](https://docs.python.org/3/library/resource.html)说明这些是进程资源限制；本方案不将其扩写为祖先或整机保证。
路径按 held parent fd 逐组件打开，保留所有选中文件 fd 到最终复核；打开前拒绝非普通文件，打开使用 O_NONBLOCK/no-follow，立即复核 fd 类型和原 inode，任何替换即停止。
逐文件读前后检查原时钟、长度和元数据，严格读原 st_size 并检测额外字节；不跟随文件中的 Include，不对文本做插值。
读取后再次枚举同一配置目录并复核全部 fd/name；目录缺失也复核仍缺失。无权限、漂移、超限或时间不足均不输出 COMPLETE。

返回恰一个 UTF-8 JSON 对象，schema 固定 `lhq-sshd-source-capture-v1`；禁止重复 key、尾随对象和任意扩展字段。
包含固定 ID、reader source digest、euid、限额设置结果、采集耗时、目录 present/absent 与排序名清单、文件有序数组及终结状态。
每文件含私有固定路径、长度、SHA-256、原 bytes 的 base64、读前/读后/最终元数据；路径不能是结果指定的新读取目标。
COMPLETE 只表示本 reader 的固定快照检查完成；异常只返回固定 reason code 和阶段/序号，不回显 arbitrary exception/raw line。
host 对 JSON 编码长度、base64 严格解码长度、允许路径/顺序/数量、全部摘要/metadata 关联和身份逐项复核。

receipt 绑定四件的角色、长度/摘要（自身不自引用）、D、实际请求/字节计数、exit、EOF、deadline 和快照验证状态。
不得把 SSH exit 0 或文件名存在单独当作成功。保留 `remote_supervision_proven=false`；未知退出不能改成已闭合。
若完整返回，取证窗口结束后，在内存中将同一有序输入交给固定
`71d6f43d98a8b71763e7925c43b2becaec184e11` 原解析器与 `46b08d9640ca19505fa02aa89d5d71d298536489` 诊断解析器。
最多一次双解析对照，每个解析器最多 5s；不导入或执行配置内容，不追加远端操作。
公开摘要最多报告来源摘要、数量、固定错误码、文件序号/行号；原路径清单、配置、stderr 和机器元数据只留本地。
输出的是当前输入复现结果，05b 的历史触发行仍不能由它单独证明。

## 版本冻结与原系统隔离

C 后实现的 host runner、reader、窄测试只服务本范围，不修改核心发行 allowlist、原 dispatcher 文法、bootstrap、业务 wheel 或系统配置。
P2 冻结准确 D commit/tree、逐文件摘要、完整 argv/environment 摘要和私有执行清单；source 或参数变化须重新完成 P2，不能在消费后重新发行。
旧三次承诺、UNKNOWN 和 capture 原封保留，本次 4 MiB/8 另计；这不是旧 host/guest 总历史证明。
P3 后无自动下一阶段；任何业务验收请求或材料不足后的补采必须另有准确授权。
