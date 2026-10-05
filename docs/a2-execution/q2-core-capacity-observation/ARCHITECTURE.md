# 核心容量单次观察架构

状态 **PROPOSED / Gate OPEN**。Scope `LH-Q2-CORE-CAPACITY-OBSERVATION-v1`，仅 O1–O3。
服从[需求](REQUIREMENTS.md)的准确输入、限额、信任和一次性边界；不建立通用远程执行平台。

## 管理入口与私有输入

复用 `bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891` 的
`tests/e3_host/q2_sshd_source_capture.py` 已有管理源保护与传输原则；不能调用其已消费 run 入口。
该 runner 33426 B、SHA-256 `cbf8e3de028f987ca5e034a12dc7d870dcb163c48e1e8713cfc72108b9e5ee91`。
以下管理 anchor pins 保持，不从任意脚本猜测或搜索新入口：

| 原管理文件 | mode | SHA-256 |
| --- | --- | --- |
| ssh.sh | 0700 | aed91e80483d4df103f95c1d4cd5bf9bd18720f4dc51720702c329c937f93c63 |
| start.sh | 0700 | 1acc8c4cb09bc5b14c32adc35e87d8500098cbf3968d53f406269e96df30f96a |
| user-data | 0600 | 5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523 |
| 公钥 | 0600 | e67e15549d3e8586af936108f666612841d31612705236dd8ce265a3da18b25c |
| known_hosts | 0644 | d1025c074e532f29534fcab1d10ec1bc2f38d2137173c74d0bc921bbab420bbd |

本地沿用 root-owned executable O_PATH 固定、管理文件 O_NOATIME/no-follow 稳定读取、
私钥关联的有界 `ssh-keygen -y` 核验和原受保护 capture parent。
私钥不输出、不打包；不运行原 wrapper、不试连接。既有四个 core capture 与已消费 sshd capture
按 `128f72d0864dd631df4941c1a453ef436221f3db` 下相应 review 的准确固定索引绑定；缺失、
身份/摘要矛盾即阻断。保留原件、完整承诺和未闭合状态，不要求其存在业务成功结果。

O2 允许只读使用既有准确 plan 与既有六份固定 ZIP 的 26 个固定 member，沿用已发
`657b1bcd749cb4281b0193b2bc9430b0662faf98` 的 archive/member、容量分量和关系 pins。
不扩大历史搜索、不重建整个 approved-input/package，不重新解析 sshd 私有快照。
plan 与容量分量各自稳定读取和核验；从五条固定映射派生私有路径描述。
如采用现成离线审计产物，必须重新验证其来源分量，不能只信任报告中的汇总数字。
O2 在内存生成五路径描述与 15 分组门槛表；O3 在同一进程使用冻结值，绑定摘要，
重新校验必要持有 fd/名称身份和管理入口，不使用可替换的未核验临时中间文件。

## 一次连接与受保护回收

SSH 使用显式固定 argv：`-F /dev/null`、原 IdentityFile/UserKnownHostsFile、
StrictHostKeyChecking=yes、UpdateHostKeys=no、CheckHostIP=no、GlobalKnownHostsFile=/dev/null、
VerifyHostKeyDNS=no、BatchMode=yes、IdentitiesOnly=yes、IdentityAgent=none、仅 publickey、
ConnectionAttempts=1、ConnectTimeout=10、ControlMaster=no、ControlPath=none、ControlPersist=no。
禁用 proxy/jump、转发、PTY、LocalCommand 和主机名 canonicalization；无 agent/certificate sidecar。
所有选项支持、argv+env 字节数和执行文件身份在 marker 前核验；stdin 为 EOF。

remote command 只携带准确 reader 的固定编码和已验证描述，使用原有
`exec /usr/bin/sudo -n -- /usr/bin/env -i HOME=/root PATH=/usr/bin:/bin LANG=C LC_ALL=C /usr/bin/python3 -I -B`
方式。固定引用/编码，无自由 shell 文本、动态命令或 guest 临时文件。
源码、描述、argv 的摘要绑定准确 D 与 R/A/B/C；endpoint/runtime 信任范围遵守需求。

同一个既有 capture parent 下仅创建四个 0600、single-link、O_EXCL 文件：

- `.lhqcap-20261006a.consumed.json`，最多 4096 B；
- `.lhqcap-20261006a.stdout`，最多 65536 B；
- `.lhqcap-20261006a.stderr`，最多 65536 B；
- `.lhqcap-20261006a.receipt.json`，最多 65536 B。

采用原 no-follow、parent/held-fd/name 复核、持久化和实际分配上限检查。所有本地准入先于 marker。
marker 创建后任何失败均已消费；不删除文件或使用新名字。双流分别限额，55s 开始停止，
只信号本调用拥有的 SSH，余下原窗口 wait/封存；无法完成不伪造 receipt 或成功。
receipt 保存 D/输入摘要、发送/消费、原时间、字节/摘要、exit/EOF/超限及远端状态证据边界。
完整 stdout 后的最多一次 5s 本地条件计算可在传输窗口后进行；不回写已封存原件，
结果进入脱敏 review，不新增现场 capture 文件。

## 五路径 reader

先核验 euid=0，设置需求中的 CPU/AS/NOFILE/FSIZE/CORE/alarm 和 monotonic deadline，再进行数据操作；
任一限制无法设置即失败，无弱化 fallback。
严格解析唯一固定描述：拒绝重复 key、多余角色/字段、非法编码、路径别名、相对路径、
`.`/`..`、重复分隔符和尾斜线。每个路径 ≤16 组件，五条路径连根最多 81 个组件 fd；
共享组件可去重，保留所需身份并在 NOFILE=128 内留出 proc/io/解释器空间。

逐组件 `O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC|O_NOATIME`，不允许弱读 fallback。
祖先 root 所有且 group/other 不可写；五个最终 parent 必须 uid/gid=0、mode 0700 或 0755，
最终 parent 与 core 的该项条件一致；本诊断的祖先 root-only 条件更严格，不宣称完整准入等价。
不得 listdir/scandir 或打开其子对象。

有界读取 mountinfo 与五个 held fd 对应的 fdinfo，核对 mount id、st_dev、ext4、mount root `/`
及 rw；仅对 held directory fd 使用原只读 `FS_IOC_GETFSUUID`（`0x8008662c`）。
每角色一次 `fstatvfs`，记录原值，bytes=`f_bavail*f_frsize`、inodes=`f_favail`，
不以 f_bfree/f_ffree 或 root 保留空间替代。负值如实记录并参与缺口，非法值停止。

采样后再次沿原名称链逐组件打开/比较身份，复核 held fd、mountinfo、fdinfo、UUID，
检测重挂载或路径替换，不能仅 fstat 旧 fd；逐条重开并及时关闭临时链，不同时保留两套全部组件 fd。
复核必要元数据而不要求容量计数不变；
不把父目录 mtime/ctime 当作业务静止证明。所有数据操作前后检查同一 deadline。
任何 identity drift 或状态不符失败，不采用新对象、续时、增加读取或刷新快照。

stdout 为单个严格 JSON `lhq-core-capacity-observation/v1`，固定五角色；含 source/描述摘要、
起止与逐角色时间、目录/挂载身份和容量原值。长度、唯一字段、数值界限及固定角色在 host 再校验。
原始路径/设备身份只留私有 capture；stderr 仅有界固定原因与非秘密诊断。

## 条件计算与事实边界

完全是本地纯函数：**不得调用** `FieldEffects.admit`、`_capacity_admission` 或任何真实 helper；
不得构造假 current inventory/path_pool 后调用 live `_cap_charge` 并称准入通过。
以冻结分量独立计算需求，用已发 05c 的纯算术作离线对照即可，不运行其业务流程。

五角色按当前 `(st_dev, fs_uuid)` 分组；state/install 必须共池，同一设备 UUID 矛盾则失败。
同池 AVAILABLE 取各角色观察的最小值。同一义务在每个不同设备完整计一次、同池去重；
snapshot+delta 各计一次，不再次加 effective；configured quota 保留全额；03a/05a/05b 各全额，
05c 也全额。`REQUIRED=HISTORICAL+05C`，`DEFICIT=max(0, REQUIRED-AVAILABLE)`，
bytes/inodes 分开列。此处 05C 是历史比较列，不是新执行预算；不计入或授权第五次 core。

回归锚点：四池分离时 required bytes 依次 1535905792、521142272、299892736、553648128，
inodes 87281、57600、25472、28160；全共池 2172391424 B /124017 inodes。
其它 13 分组必须由原分量去重计算，不能简单相加分离表。当前分组与历史 placement 的关系
仅作假设，未扫描历史子项/配额故不能报告已复验；任何现成证据表明假设矛盾则停止计算。
完整采集仍不能关闭原业务 UNKNOWN、证明核心门槛全部满足或自动释放旧承诺。
