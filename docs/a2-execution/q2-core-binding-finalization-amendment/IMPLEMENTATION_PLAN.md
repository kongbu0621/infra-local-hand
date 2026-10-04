# Local Hand 核心输入绑定与结果收回修订：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope/R 与[需求](REQUIREMENTS.md)一致；[架构](ARCHITECTURE.md)规定实现边界。
- 本文是待批准的实施计划；准确 A 的 Owner B 与独立 CLOSED C 前，不实施本修订。
- 唯一目标：正常执行、运行中取消、同一任务恢复查询、结果收回。namespace、watchdog、旧版扩建、
  内核证明、专用存储建设与生产切换暂停；不为本核心批次创建旁支项目。

## 1. 批准链、分工和交付顺序

三文档形成准确 A 后另作 OPEN 登记，保留 Owner 对准确 A/R 的原文 B，再建 bookkeeping-only C。
首个 implementation D 以独立 C 为 direct parent；后续实现提交须保持该血缘。冻结的 candidate、wheel、
原批准链、对象、H01→Q4→H11 条件顺序和一次性规则不变。B 必须准确接受需求列出的 JIT/source-horizon/
local single-writer 前提，以及应用级 capture 计费边界；不得写成已证明全文件系统瞬时物理硬上限。

| 步骤 | 云端完成 | 本地 Codex 完成 | 完成判据 |
| --- | --- | --- | --- |
| D1 | approved-input builder/parser、package/binding、HELLO JIT 与 live admission 实现 | 只提供既有私有源的绑定和受保护复算 | 消除三组 UNBOUND 输入；拒绝缺源或错源 |
| D2 | dispatcher 真实效果、三个 case 与 usage/失败返回 | 提供已有安装/机器准备的准确来源关系 | 下列八组入口都有真实实现和必要测试 |
| D3 | 六文件采集、原 receipt v1 与 live finalizer | 复算准确 host anchor/writer/私有包输入 | 无伪成功；写入与采样边界可验证 |
| D4 | 定向回归、规定的 source/installed 验证、独立复核 | 双 build/parse 独立复算准确 private package | 固定 D/tree/package/dispatcher release digest |
| F1 | 审核任务与回收结果，不代造现场事实 | 唯一 marker、唯一 carrier 内条件执行 H01→Q4→H11 | 前项 PASS 才进入下一项；真实结果闭合 |

云端先完成可用仓库和合成输入完成的实现与测试，不把代码占位留给现场执行。私有原件、准确 host
binding、私有 package 独立复算和唯一现场运行由本地 Codex 负责；公开仓库只保存脱敏结果与来源摘要。
两端推送前检查当前 main 和未提交改动；保留并发工作，不 reset/clean/覆盖。测试通过不算现场完成。

## 2. D1：输入、package、HELLO 和准入

approved-input 的两个独立 builder/parser 只接收需求固定的 held source，不接受 caller 自报 approved rows：

1. 核对 locator 四 carrier、两个 member 与 16 个固定 mapping，得到 locators、retained paths/domains。
2. 复算 20260927 的七行及固定 producer/source pins；两项 CURRENT_OWNER_SUPPLIED_RAW 使用需求的
   exact path/class/proof 关系，不继承旧 run permission。
3. 校验五个 normal batch 和 20261001e 的固定 archive/member；从 24-row snapshot 与固定 transform
   得到 12-row delta，合并为 36 rows（765202432 B/40177 inodes），前七行不重复计费。
4. 校验 placement 的原始/归一化 vectors；snapshot 按每 row 的 distinct live pool 计费，delta 只用
   固定 selector；不同 row 不相互去重。另加入 46 configured-quota liabilities（249561088 B/17792
   inodes），按 live `(fs_uuid,project_id)` 只计一次，不与历史义务或 current usage 混淆。
5. 固定三个 later-nonissuance、zero-release reconciliation、policy predicates 和 retained preparation；
   未知 consumer、矛盾来源、缺原件或假定释放一律失败。

package v2 绑定原 core A/B/C、本 amendment A/B/C、同一个新 D、candidate/wheel/projection、唯一
`private/approved-inputs.json`、local binding 和 locator relation；使用需求逐项定义的 digest preimage。
私有 member mode 0600，仅 root package/bootstrap 读取；不能进入 ordinary projection、install、sys.path、
remote output 或 public evidence。旧新 schema 混拼、额外字段、别名路径和错误 origin 必须拒绝。

先完成 offline source/D/package-template gate，再取得不可刷新的 BOOTTIME/MONOTONIC origin+900s。
origin 后复核准确 held anchor/writer、原 local 门与 ARG_MAX，完成 exact package 双 build/parse 与
final release digest，然后才检查 marker/output absence；HELLO 后不得重冻。不得提前连接 guest 取得“当前”实体或 absence。
marker v2 的 open/write/fsync/同 inode 回读/parent fsync 完整返回后才发唯一 request；partial marker
已经消费，只保留。marker 存在或五个 output 名冲突时停止；不换 anchor、不清理、不创建第七文件。

bootstrap 使用原 root Python process，收集 current q1admin account/login shell 与固定 alias/target。
保持 8-hop/64-component/4096-byte 路径限制、单项 16 MiB/合计 80 MiB、held identity 前后稳定和
O_NOFOLLOW/O_NOATIME 无 fallback；Python 两种 shape 按需求交叉绑定。HELLO JSON/frame 仍限
4096/4112 B；host 验证后才送 BIND/package/EOF。JIT 只证明 post-entry self-observation。

`admit()` 在任何本批 guest durable mutation/H01 intent 前完成：固定 sudo/sshd 两个 helper 各一次、
authorized_keys/rc/startup 关系、retained identities、existing account/manager、filesystem/quota、历史
义务、current capacity、全部本批对象 absence。helper 保持 fixed argv/clean env/cwd/stdin、no shell、
5s wall/2 CPU-s、并发双流限额与真实 wait/双 EOF；失败 kill+reap，绝不自动重试。
plugin/NSS/atime/journal 等 incidental effects 仍计原预算；不声称 pre-entry inode 或 TOCTOU 已被证明。
只有全部准入成立才进入 D2。session/admission sibling 与 remote-result v1 通过 output manifest 绑定。

## 3. D2：把 dispatcher 占位补成真实核心效果

按 `tests/e3_host/q2_core_delivery_dispatcher.py` 的真实方法分为八组；最后一组含两个方法：

| 组/方法 | 必须实现的行为 | 验收证据 |
| --- | --- | --- |
| 1 `admit` | 接入 D1 collector、strict predicates、逐 pool 准入及 absence，形成真实 admission | 原始事实和固定输入对应，失败无后续 mutation |
| 2 `install` | 核验包/候选来源后，按原 A create-only staging、native build、有限 projection 与隔离安装树顺序执行 | 成员/摘要/权限/容量/安装验证及 receipt 完整 |
| 3 `prepare_case` | 用现有 account/manager、retained paths/domains 和已持久化 intent 装配当前 case | 固定目录、authority、quota、ledger、fixture check 对应真实对象 |
| 4 `plan_case` | 调用已核验 candidate helper 构造并持久化准确 plan，在 owner/submit/start 前闭合 gate | 空账本、prepare/plan/fixture 三层关系与原 deadline 成立 |
| 5 `run_h01` | 运行正常 case，等待真实业务退出，收取 result/evidence 和监督闭合 | 真实 unit/InvocationID/wait、ledger、三份业务证据、结果与 seal |
| 6 `run_q4` | 仅在 helper 实际 RUNNING 后发一次 cancel，等待取消与监督退出 | 一次取消、真实 stop/EOF、ledger/control/evidence 闭合 |
| 7 `recover_h11` | 在 H11 自己 origin 的原 ledger/request/execution/unit/grant/deadline 上恢复 observation/control | 同 ledger identity，不重新 submit/start，不新 grant/unit，不延长期限 |
| 8 `phase_facts` + `usage` | 从真实 sources 提取 verdict 所需 facts；统计实际 CPU/memory/pids/streams/allocated bytes/inodes 与 unit counts | 无填零或 FakeEffects 替代真实计费，来源及超限失败可复核 |

第 2 组只执行原 A 已批准的**本批 create-only candidate 隔离 placement**；这不是重跑历史安装 batch。
复用现有 SSH、机器准备与既有配置；不得覆盖旧安装、改系统配置、释放旧义务、清理现场或另建机器。
prepared helper 只能来自通过摘要校验的候选；完整 checkout 保持 root-only，不进入 ordinary sys.path。
intent 早于 case 对象，plan 早于 owner/submit/start；前一 case 未 PASS 不创建下一 intent。
H11 恢复 H11 自己的任务，不借用 Q4 ledger；禁止 result reread、业务 result/evidence 重新封装。
通道可用时失败至多形成一个 bounded REMOTE_STOP_AND_RETAIN；断连可无 frame，host 不合成成功。

## 4. D3：六文件采集与 live receipt

只使用固定 marker、stdout、stderr、remote-result、capture manifest、receipt 六个 basename。逻辑上限：
marker 16 KiB、stdout 52 MiB、stderr 4 MiB、两流合计 52 MiB、remote-result 256 KiB、manifest 256 KiB、
receipt 64 KiB。原 frame 58716144 B / carrier 合计 62914560 B 拒绝线保留，52 MiB 两流预算更早停止；缺席对象额度不转移。
所有受管文件实际分配按 `st_blocks*512` 采样相加，上限 64 MiB；固定六个文件不超过原 16 inode。
每次 write/fsync 返回后采样全部已创建 owned files，逐对象身份稳定且每次观察总额须在限额内；
预写检查逻辑长度、角色余量及容量，写后检查实际分配。超限/未知/身份漂移立即停止、保留且拒绝成功。
这是应用级已观测分配边界，不能宣称覆盖未采样瞬时峰值、parent 增长或共享 FS 的全部内核元数据。

六文件均使用 held parent、create-only、0600、single-link 和 bound writer；验证性回读遵循需求的
O_NOFOLLOW/O_NOATIME 规则。remote-result 是物理副本，manifest/receipt 也额外计费，不按内容去重。
marker/request 一次性保持；不足以安全创建下一对象时保留缺项，不删文件、不临时改名、不补采。

恢复原 `local-hand-q2-core-local-acceptance-receipt/v1`：先真实 wait/双 EOF，校验 frame 与语义，
完成 streams/remote-result/manifest 后，再写唯一 receipt。receipt 的 COMPLETE 字段本身不证明成功；
只有原 live caller 观察 receipt file fsync、同 inode 完整回读、parent fsync、实际 allocation 检查及
最终双钟采样均及时成功，才能接受 local COMPLETE。无 restart COMPLETE、attestation 或 derived 实现。
live 返回按需求附 `capture_accounting`，明确 full_filesystem_peak_proven=false，不增持久文件或 receipt 键。

所有可能阻塞的持久、终结和资源观察边界前后检查原双钟，不刷新 900s，也不扩大原 15s final reserve。
晚返只能失败；检查已到期后不再发后续持久调用。失败 receipt 只在预算/时间均允许时 create-only 写入；
创建后失败或晚返保留已有 bytes，不覆盖、删除、重试或补写成功。两项 truth 按已验证原始证据分别取
YES/NO/UNKNOWN；不因 Q4/H11 或 local STOP 改写 H01 已证明的事实，不因盘上字样提升 truth。

## 5. D4：必要验证和冻结

先按改动执行定向回归，再执行原发布门要求的完整 source/installed suite；只为具体失败扩大测试：

- 输入 canonical/摘要/placement/历史计费、私有信息隔离、schema/preimage 混淆与缺源失败。
- 一次性 marker/request、HELLO JIT/两 helper 边界、准入失败无 mutation、对象冲突与 deadline。
- 八组真实效果装配；H01 真实结果语义、RUNNING-only 一次取消、H11 同任务无重启，以及失败停止顺序。
- 六文件各逻辑边界、两流合计、remaining+1 sentinel 不落盘、每个 write/fsync 后实际分配超限，
  单对象身份漂移、真实 wait/双 EOF、部分 frame、fsync/回读失败、晚返与 receipt 不能自证成功。
- package/member/shared 预算、真实 usage、结果证据成员闭包，以及 production guard 和暂停项不被启用。

不增加内核源码/loaded-module/原始设备/专用存储的证明代码与测试。FakeEffects 用于确定性失败回归，
不能替代真实效果或现场 PASS。独立复核只确认实现满足准确 A；source/installed PASS/SKIP 如实保留。
本地按既有私有原件独立双 build/parse；任一输入缺失定位到具体原件，不重新采集 guest 或制造默认值。
只有完整 dispatcher blob、固定 D/tree 和唯一 package bytes/member inventory 验证通过才入 release allowlist。
实现或输入变化后重新冻结；不把后续代码冒充已验证包，不在首次 HELLO 后更新 package。

## 6. F1：一次现场执行与功能进度

本地用既有 SSH/准备环境执行冻结任务：完成 local held prechecks、O_EXCL marker 后发唯一 carrier。
guest current checks 留在该 carrier 内；依次 H01→Q4→H11，失败保留首个真实原因，禁止重连、重试、
旧批次重放或清理。原 candidate 的本批 placement 依 D2 执行，不因“复用安装”而跳过其隔离/来源验证。

最终报告按功能列 H01 受理/真实执行/退出、Q4 运行中取消、H11 同任务恢复、结果证据收回与 live
COMPLETE；同时列准确 R/A/B/C/D/package、marker/request/case counts、预算实测及所有缺项。
真实执行但缺证据写 UNKNOWN；未执行写 NO。报告区分应用已观测分配与未承诺的全 FS 瞬时硬上限。
文档、测试数量、CI 全绿、service active 或 package 构建不能替代这四项功能验收。
