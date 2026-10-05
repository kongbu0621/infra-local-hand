# 核心下一次验收：实现与本地包核验

本轮已登记独立 CLOSED C，并提交核心实现 D。**现场新批次未消费；N1 尚缺完整 host 历史义务接线，N2 未全部完成，N3 未执行。**
下文的合成测试、安装验证和本地私有包检查均不证明真实 H01、Q4 或 H11 已通过。

## 准确版本与授权顺序

| 记录 | 固定身份 |
| --- | --- |
| 原 R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 已批准 A | `0b0f445a36232f6bcd32c395b642f9a6b259d2db`，`LH-Q2-CORE-NEXT-ACCEPTANCE-v1` |
| Owner B | [原文记录](../governance/Q2_CORE_NEXT_ACCEPTANCE_OWNER_DECISION.md)，事件 `LH-Q2-CORE-NEXT-ACCEPTANCE-CLOSURE-20261005-01` |
| 独立 C | `7ac69c0bd4401812b782b75005d8b63936d90a77`；仅 AGENTS 登记与 B 原文，无实现 |
| 实现 D | `27928b35e4406f7cfbbd360bccf0e0a8c4d7ea03` |
| D tree / parent | `c987b03a1ef516dce8aecc0f7791dafbb0053f3f` / 上述 C |

执行者本轮直接读取固定 R，正文 SHA-256 为
`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
A 的三文档字节和历史 OPEN 标签未改；C 与 D 未合并或 squash。
原固定 runtime candidate `4b6e4a7c403362358192086b88679e1326dcb2e1`、现场 wheel 与 projection 不变。
本轮改动均为 core harness、host 验证器及回归测试；没有改变 production E3 或支线实现。

## 已交付的代码

- 固定新 session、carrier、安装身份、三组 operation/preparation 身份、21 project IDs 及包名。
  host 与 guest BIND 均拒绝旧包名和其它形式合法但未经批准的替代包名，拒绝发生在现场 marker 之前的 host 检查中。
- 从同一受保护 held anchor 以 no-follow/no-atime 读取旧五原件；校验固定长度/摘要、单链接、权限、同设备及前后身份。
  晚返回的 open 也关闭其 fd。旧 writer 无需仍活着；不重放旧 runner、不刷新旧时钟。
- `reconciliation/v2` 内联五份原字节；host builder/parser 和 standalone guest consumer 检查原 HELLO、marker、capture、receipt 的关系，保留历史 UNKNOWN。
  source-aware API 必须提供 `prior_core_files`，不能以空缺省冒充来源核验。
- 原 guest 24 snapshot、12 delta 及 quota 义务不变；加计旧完整 276 MiB/16512 承诺，再计新批。
  原旧 namespace 的当前设备映射也检查；跨设备保守重复、同设备去重，不把原失败的未知用量写成零。
- 原准入中加入两次固定 unit/cgroup 观察，严格先 A、原容量/manager 检查、再 B，安装在两次通过之后。
  loaded 同 InvocationID terminal/空 scope 与 collected/not-found/精确 cgroup absence 是不同分支；
  截断、超时、晚返回、boot/父身份变化或 populated 均停止，失败 A 不执行 B，没有轮询、stop 或重试。
- 独立返回消费重算观察、旧承诺和本次 BIND deadline。H01→Q4→H11 顺序、82 output members、原 six-file capture 不变。
- host 增加旧新两批 128 MiB/32 inode 的最低可用量观察。它明确返回
  `earlier_host_obligations=NOT_BOUND`、`complete_host_admission_proven=false`，**不是完整 host admission**。
  `RELEASABLE_DISPATCHER_SHA256` 保持空，未发布可执行现场包。

三份 field 源码大小分别为 2160 / 49031 / 436933 B，均在 A 的 8192 / 49152 / 524288 B 上限内。

## 验证与真实私有输入

核心定向回归：`tests/test_e3_q2_core_*.py`，**1108 passed、35 skipped**。
新增用例使用明确标注的合成原件和边界替身；生产固定 pins 不接收这些合成字节。
SKIP 是本地权限或能力未覆盖，不转为 PASS；本机工具环境不用于推断实际 guest 或宿主是否支持 systemd。

准确 D 在独立 clone 构建测试 wheel，安装到全新临时 venv；installed verifier 为
**PASS，94 checks / 292 commands**。报告绑定 implementation `27928b35e4406f7cfbbd360bccf0e0a8c4d7ea03`；
报告 SHA-256 `320ec91fecaa8e5365e89ca9363d2d544d311410d2165108e94b89ea580d5027`。
测试 wheel SHA-256 `7e0e17e38a01f807db9ea47a1efa38a1ec91abccfbba1f0855413b676135cd19`；
它不替代现场固定 wheel，后者仍为 `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`。
该安装验证是 isolated fixture-only，不是本 A 的 guest 现场验收。

准确 D 的独立 clone 完整源码测试：**5019 passed、126 skipped**（481.55 s）；
JUnit 报告 SHA-256 `1f33255a5b97af5796c0d308a47a76f821d5738f79b52de3184974ad1ef7436e`。
完整命令为 `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -rs --tb=short`，另将 JUnit 写入隔离验证目录。
本地 SKIP 涵盖 root 保护 fixture、未提供的实机 cgroup fixture 和未安装的可选 MCP extra 等；均保留原原因。
实现冻结前另有工作区预验 5014 passed / 126 skipped，不用该变动中工作树结果替代这里的准确 D 结果。
[准确 D 的 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37252121252)
已 **3/3 success**：classify-change、Windows semantic-core、Linux semantic-core，
2026-10-05 09:51 +08:00 从 jobs API 核对终态。CI 也不替代本 A 的实机单次验收。

本轮只读私有检查沿既有固定来源读取 cloud-init、历史 carrier/义务及旧 F1 原件，未执行原旧脚本。
旧五文件逐项匹配 A，合计 **9318 B**。真实完整 `approved-inputs` 为 **325117 B**，source-aware 双端验证通过。
在同一个 900s 本地观察窗口、同一 held anchor/writer 中，两次独立构造/解析所得包逐字节一致：

| 本地检查产物 | 值 |
| --- | --- |
| 包长度 | 18149805 B |
| 包 SHA-256 | `c0374b8724f2ae4636ca8ac20fb77ea098d60cd1c38d5d84cc75d18b36979489` |
| approved-inputs SHA-256 | `c74eff7c40d4812f1315cf05be96e83591d854c47c6f5197756e4cbb1548cdac` |
| 旧新 core host 最低保留量 | 134217728 B / 32 inodes，最低可用量检查通过 |
| 完整 host 准入 / release | **未证明 / 关闭** |

这是 RAM 内离线检查产物，没有持久化为可发行包，没有发给 guest。
该 caller 已结束，其 writer/window 不能用于下一次执行；上述摘要不能授权复用这个包。
私有原件、实际设备/进程身份和可执行本地来源路径不进入公共仓库。

## 剩余直接阻塞与最小准备

A 的[架构第 6 节](q2-core-next-acceptance/ARCHITECTURE.md)要求 128 MiB/32 inode **另加更早 host 义务**。
当前已核验的 `historical_capacity_obligations` 24+12 行及 placement 是 guest 池来源；旧五原件只能新增旧 core 的固定承诺。
它们不能证明更早 host capture/未释放承诺的完整性，当前 filesystem 空闲量也不能提供这个历史结论。
既有 [host 收件复核](Q2_CORE_LOCAL_HANDOFF_RESULT_20261004.md)和
[异时计费来源记录](evidence/q2-cost-source-review-20260929/retained-input-check.json)亦未建立该完整历史账。
这不重新要求已经取消的共享文件系统全过程物理硬峰值、host quota 或内核来源资格化。

2026-10-05 后续本机自主检索已更正“只需要私有文件位置”的判断：**历史 host 归档的 44 份原件均已找到，
全部与固定归档逐字节相同，缺件、读取拒绝和漂移均为 0**。不是要求 Owner 再找这些文件。
最低缺项是这些已存在材料到**完整、更早 host 未释放义务**的覆盖关系及 byte/inode 账，详见下节。
不能从当前小文件、旧进程不活跃、传输输出上限或磁盘空闲推定退款或零义务。

上述关系有可验证来源后，在本批准范围内补齐 host-only 来源验证和逐设备全额计费，回归并冻结更新后的准确 D。
然后核对完整源码/installed/CI；在新的同一原 900s 执行 caller 内重新绑定 held writer/anchor、核对真实来源、双构包与所有输出 absence。
只有这些门全过才登记准确 release digest，创建一次新 marker、发一次固定 carrier；
在它的准入内完成旧 scope A/B 观察，通过后才 H01→Q4→H11。此处不是要求重复批准 A，也不是允许追加现场 probe。
若来源需要新的信任前提或改变 A 的保证，先按 R 处理准确变更，不能在实现中自行补一个成功条件。

## 本机自主检索与准确缺项

本节为 2026-10-05 对 `f591147548ad95796c1832e0607e6366fe998c9a` 的只读续查；
不改变 D `27928b35e4406f7cfbbd360bccf0e0a8c4d7ea03`、A、预算或执行权。
结果索引见[保存来源核验](evidence/q2-core-next-host-source-20261005.json)。
检查以固定 collection SHA → host manifest/archive → 每项原 bytes 为链；没有执行旧载荷。
53 次文件内容读取均使用现有 bounded no-follow/no-atime reader，并核对前后文件身份、大小、分配与时间字段；均未变。

| 已查材料 | 已证明 | 不能据此补造的事实 |
| --- | --- | --- |
| 固定 20260927 host manifest/archive | 49 entries、44 regular files、23569898 B；44 项本地原件均匹配 | 归档成员集合不是全部 host 义务集合的治理声明 |
| 原准备、恢复、CPUQuota retry 的脚本、intent、capture、report | 已恢复固定原执行关系；外层输出限额 2 MiB；原失败保留 | 输出字节上限不等于全部持久文件、父目录、inode、审计义务的承诺 |
| 六份后续 guest evidence ZIP | 全部通过现有 `build_horizon` 固定 pins/来源校验 | guest 的 24 snapshot/12 delta 不能充当 host 行 |
| normal 现场 launcher/settings 及一份 host launch meta | launcher 的 client-log、预算和目录是 guest 对象；host meta 只记起止、退出及双流长度 | 不能把 guest 的 20 MiB/384 capture 或 32 MiB/1024 管理池直接写成 host 承诺 |
| 保存的 R3、P/M/T、host attestation/comparison | 原来源及控制对象关系可定位；没有重读磁盘镜像或私钥 | R3 明示 full host inventory/历史成本采用/完整共同账单均为 false |

已检索本机下载目录中的 Q2/Local Hand 文件及解包结果、固定 fixture 管理目录的文件名、
相关本地临时运行/回传目录、此前 `/tmp` 回传复核目录、项目 evidence 目录和公开仓库来源索引。
另按名称在工作/下载/临时目录深度 5 内检索原 `q2-history-evidence-20260927.bundle`、
host-obligation 和 cost-source manifest/report；未定位独立私有 bundle 或完整 host 义务表。
这是所查范围内的结论，不声称其它私人存储不存在；未遍历 `.codex`、无关凭据或受限系统服务目录。
旧 K4 raw 本次未定位，仍只引用既有收件索引；不把索引写成重新散列原件的结果，也不因此要求重采 K4。

准确剩余关系为：

1. **覆盖集合。** 哪些已发出或 UNKNOWN 的历史 host capture/管理审计记录属于本次应保留集合，
   由什么既有记录证明没有漏项。binding amendment 的 source-horizon 前提明确是 **Q2 guest**；不能自行扩大到 host。
2. **每项保留金额与池归属。** 每项未释放的 byte/inode 承诺、原预算来源及覆盖对象，尤其原
   capture/journal 共享预算如何覆盖 host 记录、哪些与 guest 已计项目同池。
   把每次 2 MiB 当一份独立持久配额，或把原 64 MiB/4096 类上限复制成每批 host grant，均没有现成来源支持。
3. **当前设备映射。** 完整集合确定后，在原同一 live caller 内从受保护 parent/held fd 映射设备，
   保守计费再加旧新 core 128 MiB/32。当前只剩多少空闲空间不证明第 1、2 项。

旧 cost-source 记录的 `unknown_commitment_count=2` 是两项原文 null claim，
**不是两份已经识别但丢失的文件**。本轮不能将这两个 null 填成零，也不重新要求已取消的全文件系统物理硬峰值证明。
后续最小输入是一份能回到上述原件与原批准预算的 host 覆盖/保留额映射；原件本身无需重复提供。
若只能由 Owner 新确认覆盖完整性或另定保守保留口径，这是需要准确方案的新增前提，不能用本报告代作批准。
当前尚无依据填写该新口径的数值，故未伪造新的可批准 A 或发起笼统的“是否继续”。

本次仅修正检索与阻塞证据；没有核心运行代码变更、现场包发行或新的实机测试。
已有 prior-attempt 与 delivery-entry 两组回归 **126 passed**（4.22 s），只验证既有入口行为；
JSON 格式、diff whitespace 和 A 三文档原摘要检查通过，没有重跑或冒用上一节的完整源码/installed 验证。
以下原批次/新批次的执行状态不变；原批准有效，新的一次机会仍未消费。

## 本轮现场结果

| 项目 | 原 `20261003a` | 新 `20261005a` |
| --- | --- | --- |
| 单次机会 | 已消费，原失败保留 | **未消费，NOT_ISSUED** |
| HELLO / BIND / package | 原 HELLO 有效；BIND/package 0 bytes | 均未发送/接收 |
| 真实任务与结果证据 | 原 receipt 仍 UNKNOWN，未补造 | **未执行、未收回新任务结果** |
| 当前旧 scope 静止观察 | 本轮未连接核对 | 仅已实现测试，尚未实测 |
| H01 / Q4 / H11 | 原未进入业务提交 | 全部未执行 |
| 历史退出与使用量 | UNKNOWN，不退款 | 无新批次运行事实 |

本轮没有新增现场 marker、carrier/SSH request、重连、现场清理、旧批次重放或系统配置修改。
生产 `E3_SUPERVISION_UNVERIFIED` 保持；namespace/watchdog、E4–E6、生产切换及其它支线保持暂停/排除。
