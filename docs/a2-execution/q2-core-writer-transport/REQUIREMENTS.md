# 核心 host writer 传输：最小协议修订需求

- Authority：Owner。Scope：`LH-Q2-CORE-WRITER-TRANSPORT-v1`。
- 状态：PROPOSED / Gate OPEN；没有本 scope 的 B、C 或实施授权。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，沿用根 AGENTS 的直接来源、完整性和变更规则。
- 前置合同：核心 A `74366b3fe41e675b1aa2d677228714a5606c275c`、修订 A
  `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c` 及各自 B/C。其原字节及不受影响的 CLOSED D1–D4 保留。

## 1. 问题、目标和唯一变更

原修订要求 marker v2 包含真实 host writer，但 package.entry 只传 local-binding 摘要；
BIND 和 approved-input 均没有 writer 原文。guest 不能由摘要恢复 marker 的准确字节数/摘要，
也不能拿 guest root/PID 替代 host writer。因此当前 `CORE_DISPATCH_HOST_WRITER_UNBOUND` 正确拒绝。
本修订只补这个核心协议缺口，不增加现场探测、请求、文件、权限或执行机会。

field package schema 从 `local-hand-q2-core-field-package/v2` 改为
`local-hand-q2-core-field-package/v3`，magic 仍为 `LHCFP1\n`。
manifest 顶层键不变；entry 在原 11 个键外只增加 `writer`，exact key 为：

`loader_path,loader_bytes,loader_sha256,bootstrap_path,bootstrap_bytes,bootstrap_sha256,`
`dispatcher_path,dispatcher_bytes,dispatcher_sha256,carrier_argv_sha256,local_management_binding_sha256,writer`。

writer 是原 A §4 已定义的 `local-hand-q2-core-local-writer/v1` object，不是新观察源。
其完整 canonical no-LF bytes 须 ≤4096 B；超过则 marker 前拒绝，不截断 groups 或增加上限。
freeze 必须逐字段、逐 canonical bytes 等于同一 held local-management-binding.writer；
local binding 摘要仍摘要整个原 binding 的 canonical+LF bytes，没有更换 preimage。
writer 禁止从 caller 默认值、HELLO、guest 或另一次进程采样回填。原 release 前后和六文件 I/O
的 writer/anchor 重验保持。v1/v2 package 和缺少/额外/类型错误的 entry 一律拒绝，不作兼容补值。

guest 从 v3 entry.writer、manifest 原字段、BIND 的原 host clocks 和实际 package 描述重建
原 canonical+LF marker v2；必须满足原 marker 16 KiB 上限，并使重算 SHA-256 等于
BIND.consumption_sha256。session.consumption 的 basename/bytes/sha256/state 从这个准确
重建值派生。host 再与本次实际已持久化 marker 逐项核对，不能把 guest 重建当作 host 写盘证明。
这里只传已批准的 writer；不传完整 local binding、凭据、private key 或 raw policy。

## 2. 准确对象、版本与预算

候选仍为 `4b6e4a7c403362358192086b88679e1326dcb2e1`，其 wheel
`infra_local_hand-0.2.0a1-py3-none-any.whl` 仍为 288375 B、SHA-256
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`。
候选内的固定 harness 与 projection 不变。delivery implementation D 须在本 scope 独立 C 后冻结；
manifest.implementation、amendment.implementation、marker/session 的 D 继续完全一致，
且须同时为本 C 与原修订 C 的后代。批准不把当前未完整 D 或旧 package 变成 releasable。

HELLO/session/marker v2、BIND v1、approved-input v1、receipt/capture manifest v1 不变。
原 amendment 仍准确引用原 A/B/C，不改写为本 A。本 scope 的 R/A/B/C 和 final D/tree
由独立 closure、验证记录及 release 的 source-lineage 检查绑定；不新增 wire authority 对象。

物理 180 MiB/13440 inode、admission 276 MiB/16512 inode、2090 CPU-s、peak 2624 MiB/1160 pids，
input 32 MiB、outer output 60 MiB、capture 64 MiB/16 inode、原 900/800/750 秒均不变。
writer 的新增编码计入既有 manifest/package/input/RAM 限额，不从别处借额度。
bootstrap 49152 B、dispatcher 262144 B、loader 8192 B、HELLO JSON/frame 4096/4112 B 保持。
六文件逐角色限额、两流合计 52 MiB、实际 allocation 观测与
`full_filesystem_peak_proven=false` 保持。三项原治理前提及资源保证没有新增或放宽。

## 3. 一次性执行及成功条件

本次授权请求为 T1–T3 实现/验证/重新冻结，仅支持原尚未发行 F1 的条件继续，不新增 F1。
最多一次 O_EXCL marker、一次 carrier；无第二 request、重连、重试、改名、旧批次重放或 deadline 延长。
已有或 partial marker 继续消费唯一机会；本修订不能使其失效或退款。
仅完整 D1–D4、独立审查、双 build/parse 和当前准入全部通过后，才沿原授权条件
H01_NORMAL → Q4_HELPER_RUNNING_CANCEL_SUBSET → H11_SAME_LEDGER_RECOVERY。
H11 仍使用自己的 origin 原 ledger/unit/request/execution/grant/deadline；不重启业务、不重读结果。

验收必须覆盖 writer 替换、缺键/额外键、类型/排序错误、超限、marker 原文或 clocks/package 漂移、
v2/v3 混拼及真实 host-marker 回传不匹配；所有失败保持 fail closed，不发额外 request。
源码测试不证明真实任务执行。namespace/watchdog 暂停，production E3 限制保持，
系统配置、生产启用、E4–E6 和把 UNKNOWN 提升为成功均不授权。
