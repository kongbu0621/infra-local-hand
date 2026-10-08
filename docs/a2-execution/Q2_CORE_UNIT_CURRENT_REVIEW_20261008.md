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

## 唯一针对性处理点及剩余缺项

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
