# SC1 固定新代次实现与验证

最终准确冻结与单次返回见[现场记录](Q2_CORE_SERIAL_CONTINUATION_FIELD_20261007.md)：
SC1 完成，SC2 已消耗且失败，SC3/H01/Q4/H11 未执行。以下保留各阶段当时状态。

范围 `LH-Q2-CORE-SERIAL-CONTINUATION-v1`，准确 A
`7869bbcaeb1dad3a1736131a3ff2e225ddf5e7cc`，独立 C
`91c706b52dbc70498d5d872f59874c002cef23db`。准确 Owner B 见
[决定记录](../governance/Q2_CORE_SERIAL_CONTINUATION_OWNER_DECISION.md)。A 三文档保持原字节。

维护固定为 `lhqjgrow-20261007a`，原 06a 消耗和失败不变。按已公开现场索引保护读取
旧五原件、校验内部关系，并核对旧四后续名缺席；新九名全部要求 create-only。
普通预检、消费前复核、核心源读取均绑定旧失败摘要。manifest/receipt v3、preflight v2
携带严格 resume；旧授权作为历史保留，新顶层授权绑定 SC 的 R/A/C/D。

核心仅接受新完整维护原件构建的 journal-transition v2。host 和独立 dispatcher
分别验证新旧代次、准确授权、原件摘要和 boot 关系；reconciliation/history v6 保留
两代完整承诺，capacity v5 要求每相关设备 2656 MiB / 756 inodes。维护门槛为
2592 MiB / 740 inodes；单次动作、期限、CPU/RSS、capture/stream 和镜像限额未改。
原 runtime/wheel/projection/loader、任务身份、四旧批、sudo/sshd 规则保持。

开发树受影响 core/journal 回归 **2179 passed / 35 skipped / 38.88s**。
跳过条件保持原 root/环境要求。新固定代次测试 84 项覆盖保护读取、旧原件缺失/
内容/模式/链接异常、旧后续名、错误旧 D/nonce/事件顺序/失败关系、跨代摘要和两侧
消费者、原件复核拒绝后零 marker/SSH、旧交接/计量重置及准确授权来源。
原完整合成贯通和真实 JournalDevice 构造器测试仍执行。
首轮 2177 passed / 35 skipped / 2 failed 为待更新发行摘要及合成夹具绑定顺序；
修正后上述完整相关组通过，未降低准入条件或删除检查。

本次审查登记 dispatcher SHA-256
`bfa38a11b5b277c41c3ef0091e86a9a01462bed748baf0321ce7679cd63047af`。
旧 dispatcher 不在发行集合。该登记不等于现场准入：准确候选独立安装、既有私料
离线核对、发布、准确 CI 和最终冻结仍须完成后才能开始 SC2。
SC2/SC3 当前 NOT_RUN；未生成真实核心包，也未消费新维护窗口。
原失败原件和私料留在本机，公开代码只使用已公开原件索引的固定 pins。

## 离线读取复核修正

初始 D `b33bb2a5119cf4bfdfa85c38d004efd18a7c1f24` 的离线既有原件核对发现：
保护读取函数使用顺序读取，同一 held FD 再读前没有归零偏移，导致误报 LOCAL_FILE_DRIFT。
现改为在同一 FD 上 seek 至零再有界读取，原身份、元数据、摘要及缺席检查保留。
新增真实临时文件测试覆盖已到 EOF 的 FD 重读和重读前字节变化拒绝；合并协调器验证
**123 passed**。该发现发生在 SC1，未观察 VM、发起 SSH 或消费维护窗口。
准确候选身份以后续冻结记录为准，不能把初始 D 视作已获现场验证。

## Systemctl 单元名参数修复

依据 `acd62cb` 的 SC2 返回，只针对 `PRE_QUIESCENCE / GROWTH_SYSTEMCTL_STDERR`
处理核心阻塞。现有公开及已捕获诊断没有具体 command、returncode 或 systemctl stderr，
因此保留现场原因的不确定性，不放宽原失败条件或猜测为权限/缺失单元问题。

发现确定的参数错误：`show_many` 将单元名直接拼在选项后，缺少 `--`；
`startup_manager` 枚举可包含根单元 `-.slice`，该名称本身通过原 UNIT_PATTERN，
却会被 systemctl 当成选项并报 `invalid option -- '.'`。
在云端仅使用 `--root=/nonexistent-local-hand-offline-fixture` 的参数解析验证：
旧参数报选项错误；加 `--` 后通过该解析，停在 show 不支持 `--root` 的明确拒绝。
该对照没有连接任何 systemd manager 或现场 VM。

修复在属性选项与单元名之间插入 `--`，其它参数、单位身份和返回检查保持。
同时重置每条 ctl 的 context，失败时只复用该次 collect 的结果，记录命令序号、manager、
verb、单位数量、参数SHA-256、returncode、both_eof、PID、失败条件列表、双流长度/摘要、
最多512 B stderr的hex及截断标志。没有第二次查询，不输出stdout正文、环境或私料；
原错误码仍为 `GROWTH_SYSTEMCTL_STDERR`，三种失败条件仍停止后续动作。

本修复属于已批准 SC1 的离线修正，没有重新打开全宿主扫描或新增功能。旧 SC2 已消费，
SC3/H01/Q4/H11 仍未执行；不以本地或CI通过宣称现场成功，也不重放旧caller。

新增18项测试包含上述 native CLI 对照、真实 show_many 构造、三种失败条件的全部组合、
单次collect/成功verify、system与user manager、上下文替换、stderr截断边界，以及真实
GuestMaintenance.failure 的诊断透传和stdout/环境不泄露。
journal 全组及 minimal/serial 核心接续定向验证 **428 passed / 2 skipped / 4.14s**。
SKIP为当前环境原生PID/proc映射不一致及缺少合成qcow2/ext4工具；不计为现场通过。
`git diff --check`通过，维护host/guest源62998/55793 B，原源码与bundle上限检查通过。
新提交完整CI另按准确提交核实，不沿用旧执行候选的绿灯。
