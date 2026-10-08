# 指定单元当前读取：命中真实 Q1 业务路径

2026-10-08，完成提交 `38ff00109ee102c9530e6bac01c8baa705ab69ed` 的
[单单元只读任务](CORE_UNIT_CURRENT_TASK_20261008.txt)。本次唯一现场查询已执行，
完整返回；**当前原因已定位到真实路径引用未在清单中声明，维护及核心链仍未完成**。
这是 CURRENT_OBSERVATION，不回填 08d 当时的属性、退出或成功状态。

## 一次读取及离线处理

先核对已留存的原 stderr、consumed、execution-result 与 terminal gate 摘要关系，
以及冻结 manifest/pre_description。请求名称取自原 stderr；复用原 18 个服务、
6 个域和 230 个保护根，保持原顺序。通过已配置且摘要匹配的连接配置复用原 SSH
身份与目标，没有探测 boot、进程、目录或其他服务。

只建立一次 SSH，ConnectionAttempts=1；远端只执行任务规定的原生 systemctl show，
查询该准确名称的原 30 项属性。没有 sudo 或新增远端程序。复用仓库
`GuestCommand` 捕获组件，两流各限 1 MiB；本地原生 timeout 为 55 秒、终止宽限
1 秒，捕获总限 60 秒。实际约 **0.4 秒**返回，退出码 0、两流 EOF 完整、stderr 空、
没有截断。原响应、准确时间、连接来源、名称、参数和摘要索引仅存于新的私有位置。

返回后将同一 stdout 注入现有 `GuestInventory.show_many` 的内存 ctl，解析一次，
没有构造远端执行器或发出其他命令。保留全部 Exec 项、Id 和 Names，沿用原
`_business_reference_diagnostic` 与原子串谓词，并离线检查所有根和所有属性。

## 当前确定的命中条件

- 实际 Id 与原请求名称一致，当前为 loaded / failed / failed 的 transient 单元。
- 只有 **ExecStart** 命中 **一个**原保护根。worker 文件与 runtime 配置均是该根下的
  真实子路径；这一次响应中的命中不是相似路径前缀或 JSON 拼接误匹配。
- 该准确 Id 不在冻结 expected/domain 集合内，因此原未声明业务单元拒绝条件成立。
  没有证据支持放宽路径匹配或给整个名称前缀豁免。
- 已捕获状态字段通过现有 `validate_quiet_unit` 的纯数据检查；该项不查询或证明
  cgroup 身份/为空，也不证明持续静止、历史状态或完整维护准入。未调用
  `quiet_service`、`startup_manager`、维护入口或核心入口。

## 首次读取后的处理点及当时缺项

处理点是**补齐该准确 Q1 请求的来源绑定，再形成明确的业务单元声明**，而不是修改
当前路径判断。当前 ExecStart 保留 worker/runtime 路径、runtime 摘要和规范 base64
票据。票据可离线解码为原 ticket v1，包含生成单元名所需七项身份中的六项；它没有
`manifest_digest`。命令中的 runtime 摘要不能充当 manifest 摘要。因此没有声称已
运行 `decode_ticket`/`_validate_intent` 完整验证，或从单元 hash 反推出历史身份。

形成完整绑定仍需已有、可核验来源的对应 runtime/manifest，或包含完整七项身份及
unit/cgroup 的原 intent；需分别核对其摘要、单位名称重算、slot/generation 和原
域关系。若未来明确采用新观察作为前向声明来源，必须单独说明采用范围与缺失的
历史保证，不能静默冒充原件。补声明后仍须保留原 quiet、cgroup、启动边、writer、
持久数据及维护准入检查；当前属性通过不能跳过这些检查。

本任务不授权第二条现场查询、读取 guest 配置/intent、运行 quota worker 或启动
维护。没有重复检索旧归档、重试、清理、安装、关机、备份、扩容或重启。本轮没有
源码改动、新 reader、A/B/C、维护窗口或核心包。08d 与六旧窗口保持已消费，旧原件及
UNKNOWN 不变；GS3/H01/Q4/H11 仍 NOT_RUN。此单次查询交接已完成，不得重发。

## 后续源码复核：已有 C10 可提供配对摘要

公开历史索引已固定 C10/prior_input_report 的长度 9632 B 和 SHA-256
`0183b985fdab6a755e96c916617484e274f38e284e575dcb298349d44ccba1e9`，归档说明提供
私有 `evidence-index.json` 按摘要定位接口。无需再次泛查七份归档或读取 guest。
当前 `q2_host_export.py` 与固定 C11 字节完全相同：20208 B，SHA-256
`a5265e00222eb9cea4a9675627650c4a51adeac69c6383732a3aac0e3a3b8deb`。
其 config 先核对 runtime 的 manifest 摘要与原 manifest 字节，再将两者摘要写入
同条 `facts.files`；报告同时保留对应 original/revision 的 query_parent 来源。

因此下一步已明确为[固定 C10 的一次离线绑定核对](CORE_UNIT_CURRENT_TASK_20261008.txt)：
若当前 runtime 摘要唯一匹配 C10 的某条 config，取同条 manifest 摘要，与已捕获票据
六项身份重算完整名称；再核对同配置的 parent，形成准确声明候选和接线差额。
当前云端未持有该私有对象或当前 argv，尚未确认匹配成功。C10 存在不等于该条一定
对应本次单元，也不补齐原 Manifest 的全部 slot/deadline 校验或当前 cgroup 证明。
此处只提出有准确来源的离线核对，不改先前读取事实、路径判断、源码或维护准入。

## 本地 C10 核对完成：准确服务及父域均漏声明

本地已完成 `775de16a6a6c84d9c7e840c5c8c3aa542988ef78` 的离线交接。
未定位私有 bundle，但在已有交付目录找到 **C10 原始 report.json**；9632 B 及
SHA-256 与上述公开 C10 pin 完全相同。同目录 C11 exporter、当前仓库 exporter
均匹配原 20208 B / `a5265e…a3b8deb`。这是直接原始载体的摘要核对，不声称重新
验证了私有 bundle、其 Git 对象或全部归档。原件经既有有界 no-follow / O_NOATIME
reader 读取；没有运行 exporter、解包其他历史包或访问 guest。

使用既有 `q2_host_export.document` 解析 C10，schema、scope、EXPORTED 和
Q1_EVIDENCE_ONLY 均匹配。original_config / revision_config 各唯一且 OBSERVED，
配置关联状态及两项 false 保持。复核已捕获响应的长度/摘要、完整性及 prepared
绑定后，在内存复用原 show 解析器；规范 base64、ticket 字段类型及编码检查通过。

- 当前 ExecStart 的 runtime SHA **仅匹配 original_config**。manifest SHA 取自
  该同一行，未跨 original / revision 拼接。
- 该 manifest SHA 加票据六项身份，按 `supervision.bind_query` 的原数组顺序及
  紧凑 JSON 编码重算；结果与当前实际 Id、原请求名**逐字相同**。
- 同配置的 original_query_parent、original_source_head、original_current_boot
  均唯一且 OBSERVED；source_commit 和 declared_commit 相同，配置 boot 与报告
  guest 及冻结 original_boot 相同。父路径符合原严格 slice 格式，与原 exporter
  的 runtime → manifest → parent 关联一致。
- **父 slice 不在冻结的六个 domain_units / domain_cgroups 中**，也没有同名或
  同路径冲突。当前 ControlGroup 为空不能替代声明；服务候选使用历史逻辑父路径
  加准确单元名，保留非 null 的 control_group。

唯一声明接线差额是这条原 Q1 请求及其父域，须作为同一个来源绑定项处理：

| 字段 | 原数量 | 候选差额 | 候选数量 |
| --- | ---: | ---: | ---: |
| expected_units | 18 | 一个准确服务，带完整 control_group | 19 |
| domain_units | 6 | 对应 system slice，带逻辑父路径 | 7 |
| domain_cgroups | 6 | 同一逻辑父路径 | 7 |

准确名字、路径、C10 行、七项身份、原响应引用及三个字段的增量已保存为本地私有
声明候选。原冻结清单未改。后续接线应将这一个已核对的关联及其来源纳入新候选的
inventory/source binding，再冻结；仅把服务名加入集合、填 null 或放行 lhq 前缀
均不满足此差额。当前 `_growth_inventory` 的输入扫描未包含这条 C10/Q1 请求关联。

本次完成的是**名称关联、历史父域来源和准确声明差额**。C10 没有完整 Manifest / intent
原文；未伪造这些对象，也未运行完整 decode_ticket / _validate_intent 校验。其
independent_authority_proven、q2_reusable_allocation、q2_parent_admitted 仍为 false，
source-head 观察不等于全源码字节验证。当前 cgroup 身份/为空、持续静止、完整 slot /
deadline 和维护准入仍未证明；原 quiet、启动边、domain/cgroup、writer、数据及容量
检查全部保留。此次没有第二条 SSH、维护、源码/配置变更、新窗口或核心执行；七个旧
窗口及 UNKNOWN 保留，H01/Q4/H11 仍 NOT_RUN。该离线取件任务已完成，无需重复找原件。
