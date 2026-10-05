# sshd 配置单次只读取证需求

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1`，仅 P1–P3。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接规则、完整性、Owner mandate、无例外和 change control 沿用根 AGENTS。
- 本文、[架构](ARCHITECTURE.md)和[实施方案](IMPLEMENTATION_PLAN.md)共同组成待批准 A。截图要求准备方案，不是新的现场授权；先准确 Owner B、独立 bookkeeping-only CLOSED C，再实施 D。

## 目标和证据缺口

唯一目标是取得隔离 Q1 guest 当前固定 sshd 配置的私有快照，在本地重放既有解析器，定位阻断核心交付的输入。
不再搜索同一批旧材料，不重跑无关全量测试，不新增 namespace/watchdog 专项。

源码基线固定为 `46b08d9640ca19505fa02aa89d5d71d298536489`，tree `11ed2221630b5d73c5abfd9fb4d443947977e99e`。
[诊断记录](../Q2_CORE_SSHD_DIAGNOSTIC_REVIEW_20261005.md)已记录有限搜索未发现原件、诊断修复及其测试；
该版本 [CI 37287845245](https://github.com/kongbu0621/infra-local-hand/actions/runs/37287845245) 三个 job 均 success。
诊断代码尚未取得现场输入。`AcceptEnv LANG LC_*` 只是合成复现，不能称为实际失败行。

03a、05a、05b 三次核心机会均已消费。05b 在 sudo 检查后返回 `CORE_ADMIT_SSHD_GRAMMAR`，没有配置原文、业务结果包或 case verdict。
其[原记录](../Q2_CORE_POST_SUDO_ACCEPTANCE_REVIEW_20261005.md)和所有 UNKNOWN、完整承诺、旧 marker、账本、失败原件保留，不退款。
本提案只新增一次**诊断连接**，不是第四次核心验收，不恢复任何旧批次。

## 固定对象与读取边界

对象仍是既有受保护管理 anchor 绑定的 Q1 隔离 guest：同一账号 `q1admin`、本机回环 IPv4 `127.0.0.1:22221`、同一私钥及已固定 host key。
管理源的准确版本与读取关系在架构中列出；不换机器、账号、端口、密钥或管理入口，不假定当前工具进程就是物理宿主。
新固定取证 ID 为 `lhqsshd-20261005a`；没有业务 unit、operation UUID、project、安装目录、wheel 或业务包。
原核心 candidate、wheel、harness 和全部已消费窗口不变，本次既不安装也不执行它们。

允许采集的数据对象仅为：

- `/etc/ssh/sshd_config`，必须存在。
- `/etc/ssh/sshd_config.d` 的一层目录名清单，以及其中以 `.conf` 结尾的文件；按 ASCII 名称排序，主文件在先。
  目录不存在可记录经前后核对的 ABSENT；存在时最多 256 个 ASCII 目录项、64 个选中文件。非选中项不打开，不递归。
- 为上述路径提供身份保护的 `/`、`/etc`、`/etc/ssh` 和配置目录元数据；不扫描这些父目录。

所有选中文件必须为 root 所有、single-link regular；路径组件也必须 root 所有，文件及路径组件不可被 group/other 写入，逐组件 no-follow，使用 O_NOATIME，无弱读 fallback。
不得打开 symlink、设备、FIFO、socket 或其它 Include 指向。读前后及返回前复核 held fd、名称身份、mode/owner、size、mtime/ctime 和目录名清单；变化即失败。
快照保留原始 bytes，不要求通过 sshd 文法检查才能取回；文本只作数据，绝不执行或据此扩大读取范围。
这不改变核心准入的 Include/Match/quote/glob 拒绝规则，也不授权 `sshd -T`、sudo 枚举、进程/cgroup 扫描或旧 scope 核验。

## 新增预算与一次性规则

下表是本次独立诊断的新增边界，不延长或冲抵任一旧预算。

| 项目 | 固定上限或规则 |
| --- | --- |
| 配置输入 | 最多 65 文件；每文件 262144 B；合计 1048576 B；目录名清单编码后最多 65536 B |
| 新实现规模 | guest reader 源码最多 32768 B；host runner 最多 65536 B；无第三方依赖 |
| 传送 reader | 仅固定 remote command 参数；本地 argv 加环境总编码最多 65536 B；SSH stdin 为 EOF，不传包 |
| 网络结果 | stdout 最多 2097152 B；stderr 最多 65536 B；超限截停并标记失败，不继续排空无限流 |
| 私有 capture | 新承诺 4194304 B（4 MiB）/ 8 inodes；固定四件，详见架构；不得按实际小文件退款 |
| 当前 host 可用条件 | 同一 capture 设备至少 205520896 B（196 MiB）/ 56 inodes；含三旧各 64 MiB/16 的完整承诺及新 4 MiB/8 |
| 本地窗口 | 从首次本地现场预检读开始最多 60s，沿用该次 monotonic/boottime 起点；最后 5s 留给停止及封存；SSH ConnectTimeout 10s |
| guest reader 限制 | 初始化后设置 CPU soft/hard 均 5 CPU-s、address-space 128 MiB、NOFILE 128、FSIZE 0、CORE 0；不创建子进程 |
| guest reader 时间 | 初始化后设置一次 20s alarm，并在每次数据操作前后检查同一 monotonic deadline；不重置 |
| 请求消费 | 最多一次 O_EXCL marker，最多一次 SSH exec request；ConnectionAttempts=1；所有本地准入先于 marker |
| 本地解析对照 | 取证窗口结束后，完整输入最多作一次双解析器对照；每个解析器最多 5s，输入仍限 1 MiB；零远端操作 |

当前可用量检查不是排他预留，不证明完整历史容量；更早 host 承诺仍 UNKNOWN，旧实际占用不抵扣上述承诺。
本次请求 Owner 明确接受这些历史缺口不单独阻断本固定快照；空间竞争仍可能使 capture 或 receipt 不完整。
4 MiB 是应用写入限额和实际分配量观察边界，不是共享文件系统全程物理硬上限，可能发生观察间隙超限。

任一固定新文件已存在或部分存在即停止，不换名；marker 一经创建即消费，无论后续是否真正发送。
marker 前可以重新进行仅本地的预检；一旦存在 marker，任何后续调用均不得连接。
同一 winner 不刷新预检时钟。失败不重试、不重连、不补采、不清理、不删除 marker，不向旧批追加现场指令。

## 必须明确接受的保证边界

这是**配置数据只读**，不是整台 guest 零写入承诺。原 SSH 登录、sudo/PAM、审计、日志以及解释器所需的运行时读取可能发生；
不改变这些系统设置，不规避审计，不授予读取其它业务数据或凭据的权限。配置原文可能含敏感值，只留受保护本地 capture，不进入 Git、CI、聊天或公开日志。
自有配置读与本地预检使用 O_NOATIME；SSH 内部读取既有凭据/known_hosts、运行时文件仍可能产生访问时间与管理审计副作用。
这不授权修改这些文件的内容、权限或所有者，也不声称整个管理过程的元数据完全不变。

本次通过固定 host key 和账号识别 endpoint，信任其现有 sudo/Python 运行时；不另作 HELLO、可执行文件 attestation、有效 sshd 策略验证或旧 scope 静止证明。
guest 限制只覆盖已初始化的 reader；不声称它覆盖 SSH/sudo/PAM 祖先进程或其初始化开销、全机 CPU/内存/pids、审计空间。
本地最多一个 SSH 子进程，reader 无子进程；这不是远端整棵进程树的 hard cap。此较窄保证**只用于诊断，不能作为核心准入放行依据**。

本地停止只针对本调用拥有的 SSH 子进程。20s alarm、60s caller 窗口及信号停止不能保证不可中断 I/O、PAM 或其它远端进程在硬期限内退出；
本地 wait/EOF 不是远端独立监督闭合。超时、断连或无法收尸时记 UNKNOWN，保留现场，不追加连接确认或终止。
正常得到完整快照也只能证明当前采集输入和 reader 报告的完成，不能恢复 05b 历史配置、证明没有并发变化或宣称已查明 05b 的历史触发行。

## 完成标准与明确排除

P1 实现固定只读取证器和窄回归；P2 离线验证、准确版本冻结及仅本地私料绑定；P3 条件执行单次取证，收回私有输入并作有界离线解析诊断。
快照完整须同时满足身份/稳定性、结构/摘要/大小、SSH exit 0、双 EOF 和本地窗口；任一不满足则 PARTIAL/FAILED/UNKNOWN，不称成功。
后续修复须区分既有 CLOSED 范围内的缺陷与需重新批准的文法/信任变化；本次不自动授权放宽核心检查。

明确不授权 H01/Q4/H11、现场重装/重启/配置修改、任何新业务或 systemd unit、清理历史、换批次再试、生产启用。
namespace/watchdog 及所有支线暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。取得快照、CI success 或本范围 CLOSED 均不意味着核心验收通过。
