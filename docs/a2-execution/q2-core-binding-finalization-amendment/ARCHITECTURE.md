# Local Hand 核心输入绑定与结果收回修订：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER DECISION**。
- Scope/R 与[需求](REQUIREMENTS.md)一致。只有准确 Owner B 和独立 bookkeeping-only CLOSED C 后才实施。
- 本文是文档方案，不创建实现、测试、package、release digest 或现场执行许可。
- 精确 schema、keyset、摘要 preimage、角色限制和状态定义以需求为准；本文不另复制第二套键定义。

## 1. 本次边界

核心目标仍是一次受理后完成 H01 正常执行与结果收回、Q4 取消、H11 原任务恢复查询。
原 candidate、wheel、harness、guest 隔离/凭据/配额、900/800/750 秒 deadline、一次 marker/request、
原历史义务、执行顺序及 production guard 不变。namespace/watchdog 和其它支线保持暂停。

本 A **改变 host capture 资源验收语义**：应用写入上限加已创建文件的实际分配采样，不再声称
共享文件系统及瞬时分配的严格物理峰值上界。保留 64 MiB/16 的数值不等于保留旧保证。
该改变须由 Owner 明确接受，不能通过改名、测试通过或宽泛“继续”推定已经批准。

采用 c83dad1 的[本地回传](../Q2_CORE_LOCAL_HANDOFF_RESULT_20261004.md)作为历史事实：准确 anchor
与另一旧 parent 不同，且同目录保留 VM 镜像；没有已证明的 host hard-limit 机制。
不再索取相同 R3/K4 材料，不把历史记录或本工具容器当成当前管理机准入。

| 内容 | 本方案 |
| --- | --- |
| 输入和当前 guest 绑定 | 保留 approved-input、package/HELLO/marker/session v2 及 post-entry JIT 校验 |
| 本地结果图 | 恢复六个固定文件；receipt 和 capture manifest 使用原 v1 |
| 最终成功 | 仅同一 live finalizer 完成全部检查后返回含原 receipt 的结果与明确 capture 计费说明 |
| 磁盘 receipt | 保存事实，不自证自身最终 fsync/回读或最终 deadline；不提供 restart COMPLETE |
| 本地资源 | 写前应用限额；写后/fsync 后六文件分配采样；明确没有全文件系统物理峰值证明 |
| 不进入本方案 | attestation、derived/restart 验收、内核源码证明、loaded-module 证明、raw-device/superblock 资格路线 |

## 2. 输入、版本和摘要关系

需求第 3 节定义唯一 root-only `private/approved-inputs.json`，固定 source horizon、policy、
36-row historical obligations、46 configured-quota liabilities、retained preparation 和 zero-release。
原始私有资料只由 held descriptors 读取；先校验字节数/摘要，再按固定 selector 生成关系。
两次独立构建须得相同 canonical bytes；不得用 caller 自报值、邻目录扫描或 current guest 读数补历史空项。

36 行总计和 46 项总计只作各自完整性校验；live admission 按设备/义务关系计费，不相互替代。
没有 eligible release seal 时 release 为零；旧 raw 的来源等级、历史 atime 和失效执行权仍保留。
approved-input 只留在 root RAM/package 校验范围，不进入 ordinary projection、runtime import 或公开证据。

需求第 4 节的版本关系保持：field package v2、locator relation v2、carrier consumption v2、
HELLO v2、dispatch session v2，以及 approved-input/source-relation/local-management-binding v1。
local management binding 只含当前 local facts 与 static remote expectation，不预先声称当前 remote preimage。
marker v2 **没有 `capture_resource_preflight` 字段**；不得接受旧七对象方案的额外键。
package/marker/session 的 amendment 逐字段一致；集成 D 同时绑定 package implementation 和 amendment implementation。
locator relation 的摘要与 approved source relation 的摘要分别按需求的不同 preimage 计算，不互相复用。

BIND、remote-result、output package、case/phase/evidence、local receipt/capture manifest 保持原版本。
所有 strict object 拒绝缺失/额外键和版本混拼；v1 receipt 不接受已撤回 proposal 的 v2 或 attestation 替代品。
完整 package 的独立 build/parse、真实效果实现和 release 验证完成前，allowlist 保持空，package 不可发行。

## 3. 本地消费与唯一 carrier

顺序固定为：离线 source/D/release 静态检查 → 原双钟 origin/+900 秒 → held local binding/writer 和
ARG_MAX 检查 → 完整 package build/parse 与最终 release 检查 → 六个固定 basename absence →
排他创建并持久化 marker → 唯一 carrier request。

所有当前 local 读取、身份绑定与 origin 顺序按需求；原 no-follow/O_NOATIME held-path 约束保留。
pre-marker 不写入、创建或 fsync。已有 marker 表示已消费；marker 缺席但其它输出存在表示冲突，
不清理、不覆盖、不以新名字另发。guest absence 只能在同一 carrier 内取得，不能提前另连查询。

marker 的 O_EXCL 成功瞬间消耗唯一执行权；记录持久化失败时不发 request，现场保留。
六文件的创建与验证都使用同一 held parent；同一 writer 的身份、文件权限、nlink、inode 与路径绑定不放宽。
受信单 writer 前提只承接本地同等权限并发写入风险，不伪装成技术上禁止所有其它进程写入。
它不授予 host sudo、配置变更、安装、迁移、挂载、清理或增加任务次数。

bootstrap 在唯一 root 进程中先取得当前账号/登录 shell 及固定五个程序 alias 的有界实体关系，
按需求输出 HELLO v2。host 验证完整 HELLO 后，才发送 BIND、同一个 package 和 stdin EOF。
实体读取上限、alias→resolved/Python 关系、HELLO 长度、UID/GID 与所有摘要仍按需求严格检查。

post-entry JIT 是进入后的 guest self-observation；不证明最初 SSH/sudo 已载入映像与事前 containment。
需求规定的该治理前提必须经准确 B 接受；实现、诊断与报告不得升级其证明能力。

## 4. 同一 carrier 内准入与核心执行

package 校验通过后，dispatcher 在首次 guest mutation/H01 intent 前完成：固定 sudo/sshd semantic
helper → HELLO/account/program 交叉绑定 → retained path/domain → reconciliation 与对象 absence →
当前 filesystem/quota/usage → 历史、configured-quota 和新 core 的逐设备容量账 → 原保护与时间检查。

sudo/sshd 各最多一次；argv、clean environment、stdin/cwd、双 EOF、输出合计、超时和 reap 取自
需求的 policy profile。它们不是新 SSH/carrier/unit/request；incidental effects 仍计入原预算。
历史 snapshot/delta 的设备映射、义务去重、项目不存在条件和未知即停止按需求第 3–5 节执行。
任一准入失败发生在已消费 marker 后，只可保留并停止；不能退款、重连或补采。

H01 先完成 intent/plan/empty-ledger gate，再真实执行并闭合 exit/tree/writer/collector/result/evidence。
只有 H01 semantic PASS 才进入 Q4；Q4 必须取得 RUNNING 证据后恰好 cancel 一次并闭合。
只有 Q4 semantic PASS 才进入 H11。H11 恢复自己的 origin 原 ledger/unit/request/execution/grant/deadline，
不复用 Q4 ledger，不重启业务，不重新 submit/start，不读取或封装原业务 result，不刷新 deadline。

session admission 原文由 output manifest 绑定；remote-result 保持原 shape，不能以摘要布尔值替代 raw 证据。
FakeEffects、mock pipe 或静态 PASS 只能是代码验证，不能填写真实业务执行/结果收回真值。

## 5. 六文件应用限额与分配采样

| 对象 | 固定逻辑字节上限 |
| --- | ---: |
| marker | 16384 |
| stdout | 54525952（52 MiB） |
| stderr | 4194304（4 MiB） |
| remote-result | 262144 |
| capture manifest | 262144 |
| receipt | 65536 |

stdout+stderr 另共同受 54525952 字节上限约束；所有对象共同受 67108864 字节应用累计上限约束。
逐角色未用额度不能转借。六个受控文件对应六个受控 inode，低于 16 上限；不得创建第七文件、临时副本或旁路日志。
原 outer-output/frame 拒绝线保持，不能借它放大此处 capture 接收上限。

每次 create/write 前按需求检查角色、单次长度、累计逻辑计费和原时间窗口；短写只计实际写入字节，
停止后的残留仍保留且不退款。复制 remote-result 是独立文件写入，必须再次计费。
每次 write 后及 fsync 后，对当时已创建的 owned files 采样并汇总 `st_blocks * 512`；
累计最大观测值仅增不减，超过 67108864 字节或采样/身份不确定时停止，不得 live 成功。

完整成功路径必须覆盖全部六文件及终结后的最后采样。capture manifest/receipt 的原 v1 字段含义
和其有限已知子集按需求保留，不填入未来文件、伪造采样或循环摘要。
parent、其它 writer、共享 journal、extent/xattr 及 allocator 未观测瞬时行为不因采样而获得全程上界。
检测到超限后停止也不等于从未超限；这里不声称已经建立 host filesystem 的物理硬隔离。

## 6. live finalizer 与停止

真实 wait 加双 EOF → remote-result/capture manifest 持久化及回读 → 形成原 receipt v1 →
receipt 排他创建、完整写入、file/parent fsync 与同 inode 回读 → 最终六文件采样和双钟检查 →
在全部成功时由同一 live 调用返回含原 receipt 的结果。
需求 §6.2 的 `capture_accounting` 仅附在 live 返回值，报告 logical 写入、实际最大观测量与
`full_filesystem_peak_proven=false`，不落盘、不修改原 receipt/capture schema，也不成为新的验收证明链。

每一步仍须满足原 900 秒窗口与 15 秒 finalization reserve 的前后检查；不增加尾窗或独立延长时钟。
阻塞调用可能晚返，但其后检查失败就不得返回成功，也不得继续持久化或重试。
所有 regular/0600/nlink=1、真实 writer UID/GID、no-follow、同 inode 回读及摘要条件保留。
只有原 H01 完整 raw 证据才可令 execution/collection 为 YES，Q4/H11 不改写其事实。

receipt 中 state 和 wait/capture 只能描述生成时已经取得的事实；盘上 `COMPLETE` 字面值不是
其自身写入/fsync/回读或最终 deadline 的证明。最终调用失败时可能保留完整 receipt，但仍无 live acceptance。
不再写 attestation，不生成 derived acceptance，不实现从盘上 receipt 恢复 COMPLETE 的入口。
失败时不改写/删除原 receipt；及时 STOP receipt 仅在原规则允许且尚未创建时生成一次。

marker 前失败为 NOT_ISSUED 或冲突；O_EXCL 消费后失败为 STOP_AND_RETAIN。
部分文件、未知 wait/EOF、fsync/回读失败、逻辑超限或实际分配采样超限均不成为成功。
旧批次不重放；退出后不另连补采、不自动重试，namespace/watchdog 与 production 激活继续排除。

## 7. 实现交接

本 A 批准及独立 C 后，D 按[实施计划](IMPLEMENTATION_PLAN.md)集中补 approved inputs、JIT 绑定、
真实 dispatcher 效果与上述 live finalizer。完整独立验证和 package 冻结后才条件执行一次 H01→Q4→H11。
本地 Codex 复用既有 SSH/安装完成只能本机取得的准入和现场步骤；云端完成代码、负例、审查及 CI。
不再把内核鉴证、存储重新搭建或通用自举平台作为本核心方案的前置项目。
