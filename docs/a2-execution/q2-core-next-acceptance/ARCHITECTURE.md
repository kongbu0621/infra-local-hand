# Local Hand 下一准确单次验收：架构

- Authority：Owner；状态：**DRAFT / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-NEXT-ACCEPTANCE-v1`；R、准确 A/B/C 顺序见[需求](REQUIREMENTS.md)。
- 本文件仅提出新批次设计；旧 `lhqcore-20261003a` 已消费，本文不授予实现、连接或执行权。

## 1. 组件与信任边界

复用现有 host builder/parser、entry、三文件 field 程序、冻结 installer/harness、capture/finalizer。
候选、wheel、projection、H01→Q4→H11 顺序及既有账号、权限、来源与身份检查不改变。
新批次只有一个 carrier；旧状态收口位于该 carrier 收包后的 dispatcher admission，业务安装前完成。
不新增 probe、SSH 请求、现场服务、独立管理 unit、恢复入口或后台等待器。

| 组件 | 拟承担的增量职责 |
| --- | --- |
| 两个独立 host builder/parser | 从受保护原件构造并交叉验证旧 attempt 闭包、独立增量承诺及新固定 namespace |
| entry / 原 capture | 新 writer/window、一个新 marker/request；保留旧五文件及原消费状态 |
| bootstrap | 原 HELLO/BIND/package 顺序、大小与双时钟；不接受 caller 提供任意命令 |
| dispatcher admission | 复核旧原件、两次当前静止观察、全部历史与新承诺；通过后才准入安装 |
| host finalizer | 从绑定的 session admission 复验两次观察及容量账；旧 UNKNOWN 与新事实分别报告 |

## 2. 唯一新 namespace

session 固定 `lhqcore-20261005a`，carrier 固定 `lhqcore20261005a-carrier.service`。
install/staging 固定 `local-hand-core-acceptance-20261005a` / `.local-hand-core-acceptance-20261005a.staging`。
新六个 host 文件沿原六种后缀使用 `.lhqcore-20261005a` 前缀；旧 marker 不删除、改名、覆盖或重用。
三个 case basename 与 role/path 映射不变，只置于新 session；五个 parent 仍只取当前鉴证 locators。

| case | preparation ID | operation UUID | controller prefix | projects |
| --- | --- | --- | --- | --- |
| H01 | `lhqc05a01h01normal` | `97d5ce56-e176-47c8-88eb-ff81242bfcfd` | `lhqcore20261005a-c01` | `12201..12207` |
| Q4 | `lhqc05a02q4cancel` | `bb46ffb2-187e-48a7-8c2d-f548dd576fa6` | `lhqcore20261005a-c02` | `12208..12214` |
| H11 | `lhqc05a03h11recovery` | `7fa6d9d2-812f-45a4-8027-4cfb183aa862` | `lhqcore20261005a-c03` | `12215..12221` |

UUID 仍取原 SHA-256 前 16 bytes 并设置 UUIDv4/variant bits；URN 的 scope 换为本 scope。
`installation` 对应 `6fd82898-ae68-4a5c-bce5-65f06e86580c`；case 用原完整 case name 派生。
identity seed、authority/profile/principal/ledger/node、epoch/slot/session 均按原规则使用新 session。
execution ID 与全部 `lhj-*` 从新 operation UUID 派生，不能只替换目录日期而复用旧 operation/install UUID。
任何新固定对象已存在、project 已占用或保护不符均停止，不找替代名；旧对象不作为新安装/ledger 使用。

## 3. 唯一私有输入中的旧 attempt 闭包

`approved-inputs/v1` 顶层字段、`private/approved-inputs.json` 唯一 member、package/v3 与 HELLO/BIND 不增字段。
`reconciliation` 原本无 schema；本次明确为 `local-hand-q2-core-reconciliation/v2`，exact keys 为
`schema,state,applied,released_bytes,released_inodes,record_basenames,prior_core_attempt`。
原 `NO_ELIGIBLE_RETAINED_SEALED_RECORD_SOURCE`、空 applied、零 release 及原五个 seal basename 原样保留。
新 `prior_core_attempt` 是 `local-hand-q2-core-prior-attempt/v1`，exact keys 为
`schema,scope,session_id,implementation,package_sha256,manifest_sha256,files`；历史元数据严格绑定原 F1。
`implementation` exact keys 为 `commit,tree`，值分别固定为
`605a2a38d1db5ef85c961b4d357cafa157bdd7d5`、`ced38519fe6e3b86973de5ccf0dff60fc62322e4`。
原包与 manifest 摘要逐字等于[需求中的固定原 F1 表](REQUIREMENTS.md)，不随外部报告更新。
`files` 按 basename ASCII 严格升序恰含原五文件，每项 exact keys 为 `basename,bytes,sha256,raw_base64`。
各长度/摘要逐项等于本 A [需求中的五文件固定表](REQUIREMENTS.md)，无额外文件或缺项。
base64 严格解码并回编码相等，原 bytes 总和恰 9318；保留原字节而非重新序列化 JSON 代替原件。
host 以原受保护 parent、O_NOFOLLOW/no-atime、held fd/name 前后身份及 single-link regular 检查读取。
旧原件只作历史 source，不重新运行旧 live-finalizer、不要求旧 writer 仍存活，不刷新旧时钟。

host 两个独立 parser 与 guest 分别核验五个摘要、原 schema、旧 scope/session/package/manifest/marker 关联，
以及 stdout 的完整 HELLO frame；无追加 frame、重复 JSON key、未知字段或不完整原始字节。
核对原 `hello_valid=true`、输入发送 0 bytes、BIND/package 未写、原 STOP_AND_RETAIN 和缺失 remote-result；
receipt/capture/marker 中同一身份、摘要、计数或时间关系矛盾即拒绝，不用摘要相同掩盖结构不符。
旧 HELLO 须通过旧冻结契约的 loader/bootstrap、root UID/GID、程序、管理入口与 carrier 限额校验。
旧 unit 名、InvocationID、ControlGroup、boot ID、PID 只从该 HELLO 取得；不接受新 caller 覆盖。
HELLO 没有 guest PID starttime/cgroup inode；不得补造，也不得将后来同号 PID 视为旧进程。
原五份 raw 只内联于私有输入并留在 guest RAM；不新增 guest 证据目录、不进入公共仓库。
新输入仍 ≤1048576 B，原包总输入 ≤33554432 B；扩充超限即拒绝，不扩大 framing 预算。

## 4. 当前静止观察与历史结论分离

新 HELLO 与旧 HELLO 的 boot ID 必须相等；不同 boot、不完整或来源关系不符即停止。
dispatcher 验证当前 policy/program/guest 后，使用已鉴证 systemctl 与 protected cgroup parents 观察旧 scope。
顺序固定为：原 guard → held ancestor/parent 身份 → unit SHOW-A → cgroup-A → 原 guard；
随后完成原当前 filesystem/quota/retained/manager/absence/capacity 准入，再执行
原 guard → 同一 held parent/name 身份 → unit SHOW-B → cgroup-B → parent/name/boot 复核 → 原 guard。
只有 A/B 两次均满足同一分支且事实一致，才发布完整 admission，继而创建新安装或 case 对象。
两次不是失败重试、轮询或等待；A 失败立即停止，不为取得成功样本执行 B。
SHOW 每次仍最多 5s wall、2s CPU、32768 B combined output，且受原外层剩余时间约束；不新增 unit。
固定 `show --all`，`--property` 恰列 `Id,LoadState,ActiveState,SubState,MainPID,InvocationID,ControlGroup,Restart,KillMode,ExitType`。
unit record exact keys 为上述十项；值为原 ASCII string，MainPID 必须为 `"0"`；每项恰出现一次，无缺项/额外项。
`InvocationID=`/`ControlGroup=` 的空值须显式出现并保存为 `""`，不能把遗漏字段补成空值。
官方 [systemd v255 show_one](https://github.com/systemd/systemd/blob/v255/src/systemctl/systemctl-show.c)
（git blob `963ba69ab6e339ee8e1df7d90d8857d2879daf14`）中 show 对 not-found/inactive 仍打印属性并返回 0；
返回 4 的未知状态规则属于 status，不能套用到 show。本合同据此要求 SHOW exit=0、stderr 空、完整结构化属性；
任何 nonzero/信号/缺项/超时均停止，退出码本身不能证明 unit 存在或不存在，不现场探测其它兼容分支。

| 分支 | 两次均必须满足 |
| --- | --- |
| `LOADED_TERMINAL` | 精确旧 unit；LoadState=loaded；InvocationID 等于旧 HELLO；MainPID=0；ActiveState/SubState 恰为 inactive/dead 或 failed/failed；Restart=no；KillMode=control-group；ExitType=cgroup；ControlGroup 为空或等于旧值 |
| `COLLECTED_ABSENT` | 精确旧 unit 的 LoadState=not-found、ActiveState=inactive、SubState=dead、MainPID=0、InvocationID/ControlGroup 空；旧 HELLO 精确 cgroup 路径两次均不存在 |

collected 的 Restart/KillMode/ExitType 仅为当前 not-found stub 的属性，原样保存并要求 A/B 一致；
不得将其视为旧 invocation 配置，也不要求默认 `ExitType=main` 等于旧 HELLO 的 `cgroup`。
loaded 分支也必须检查旧 HELLO 的 cgroup 路径，不能把 systemctl 的空 ControlGroup 当作空树证明。
该路径两次均不存在，或两次为同一 held cgroup 身份且 `cgroup.events populated=0`、`cgroup.procs` 空。
present 分支两次 fd/name 的 dev/ino/mode/uid/gid 与父链相符，完整有界读取原 kernel 文件，不递归业务目录。
absent 分支须从 held、nofollow 的父目录观察精确 basename 缺失，前后父/name 身份不变；不跟随 symlink。
不得在两次间从 loaded 改判 collected、换 InvocationID、换 cgroup inode，或将 active/populated/不明状态接受。
`--collect` 可以卸载原 unit，因此允许 collected 分支；其含义仅为当前旧固定 scope 不活跃。
原冻结 bootstrap 在零 BIND 下未进入 dispatcher/业务，结合固定 Restart=no 与完整父链才能采用该推论；
不声称能排除任意未授权迁移，或补回原 exit code、stdout/stderr EOF、guest CPU/memory/pids。

## 5. 观察 record 与严格消费

session admission 原八字段 `guest,programs,policies,parents,filesystems,capacity,absence,binding` 保留，
仅加 `prior_core_attempt` 成为九字段；新、旧 scope 的 exact parser 分开，旧 shape 不发行新包。
此新 observation record schema 为 `local-hand-q2-core-prior-quiescence/v1`，exact keys 为
`schema,prior_attempt_sha256,boot_id,branch,observations,current_scope_quiescent,historical_remote_exit,historical_usage,released_bytes,released_inodes`。
prior 摘要是第 3 节旧 attempt 对象 canonical/no-LF SHA-256；observations 恰两项，顺序为 A、B。
每项 exact keys 为 `ordinal,boottime_ns,monotonic_ns,unit,cgroup`；unit 保留表中全部结构化属性；
cgroup 保留 `path,state,parent,identity,populated,procs_bytes`，state 只能 ABSENT/EMPTY。
parent/identity 用 `path,dev,ino,mode,uid,gid`；ABSENT 的 identity/populated 为 null，procs_bytes 为 null；
EMPTY 的 identity 为实际对象、populated=0、procs_bytes=0。ordinal 恰 1/2，双时钟单调且属于新窗口。
完整记录必须 current_scope_quiescent=true；historical_remote_exit/historical_usage 仍为 UNKNOWN；release 两值为 0。
record 由原 session/output manifest 摘要链绑定；原九项 admission binding 仍重算含新组件的完整摘要。
独立 host consumer 重算所有原件/观察关联，不只信 true；缺失或失败不能造完整 record，也不能 COMPLETE。
这一固定旧 historical UNKNOWN 不自动阻断新批次，是本 A **拟请 Owner 接受的边界调整**；
不放宽新批次自己的当前准入、账号、权限、stop、双 EOF、收回或 H01/Q4/H11 成功标准。

## 6. 非退款容量与停止

`historical_capacity_obligations` 显式升 `local-hand-q2-core-historical-capacity-obligations/v2`；
原字段、source horizon、24 snapshot + 12 delta 行、原 totals/placement/quota 来源完全保留，另加 `prior_commitment`。
prior_commitment exact keys 为 `scope,session_id,source_attempt_sha256,logical_bytes,logical_inodes,cpu_seconds,host_capture_bytes,host_capture_inodes,released_or_refunded`，
固定旧 scope/session、同一 prior 摘要、289406976/16512、2090、67108864/16、false。
该旧 276 MiB/16512 按旧固定 32 pool 的 parent-role 映射，在每个实际 `(dev,fs_uuid)` 各计完整 pool；
同池同设备去重，跨设备重复，另将三个 32 MiB/1024 management headroom 计入 state 设备。
原同设备条件保持；旧 namespace 与已绑定 locators 关系须完整，不能假装取得原失败批次未做的 filesystem 观察。
`_cap_charge` 与独立消费者必须把此项计入 historical，再加全部更早义务和新一轮 276 MiB/16512；
原 totals 不加写成伪造新历史行。旧新同设备逻辑基准 552 MiB/33024，跨设备合计可更高。
旧实际 9318 B/5 inode 不替代旧完整承诺；原私有 anchor 先核对旧 64 MiB/16 保留义务，
同设备再为新 capture 保留 64 MiB/16（合计至少 128 MiB/32，另加更早义务）；不以五文件小而退款。
旧 2090 CPU-s 承诺保留，新一轮仍最多 2090；每 unit 限额、800s remote、750s guest、900s host 不变。
旧静止核对前最多旧新两个 carrier 并发：2048 MiB/256 pids；不得提前进入安装/case。
核对通过后新批次原峰 2624 MiB/1160 pids；旧 usage UNKNOWN 不能填零，此并发推论只依赖零包与原 bootstrap。
原 45s remote/15s local reserve、32 pool 保证与 `full_guest_filesystem_peak_proven=false` 保持。
任何原件/身份/容量/时钟不明、超限或观察失败均 STOP_AND_RETAIN；不清理旧现场、不重连、不自动重试。
若本轮失败，新 marker 仍消费；回退仅保留失败证据，不能再用旧契约、旧组件或新名字绕过停止。
