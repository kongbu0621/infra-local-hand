# Q1 实机结果与出口收口清单

日期：2026-09-25。状态：**机制实测结果已返还；容量来源待核对；Q1 出口尚未通过**。

本记录承接 [Q1 fixture 交接](E3_QUOTA_Q1_FIXTURE_HANDOFF.md)和
[单次实验交接](E3_QUOTA_Q1_EXPERIMENT_HANDOFF.md)，不改变批准 A
`415327ebdcc251bb055da9931a7a88990f750b7a`、独立 C
`5a4ea852091db06549a876e42bbd5f95d5869d3b` 或三份权威文档。
Q2 的接口准备见 [Q2 接线设计草案](E3_QUOTA_Q2_INTEGRATION_DRAFT.md)。

## 证据来源与准确范围

已返还结果来自 Owner 在私有隔离 KVM fixture 中执行固定脚本后的终端截图。
当前开发环境未连接该 VM，也未直接取得全套现场原件。下面的“已报告通过”指已交付脚本的
实机输出所报告的事实，不宣称本开发环境重新执行了该实测或独立导入了全部私有封存文件。
源码核对基准为 `32852f28b4edefb7acd1b5c6562cecc29524637d`；VM 修正候选源码为
`45ebc2fd1fe70cfa4680f6ad71f0badc2a4ec0a3`，tree
`d82ec1c3194bb39da07545fff0429e4466abc68e`。

本文件只保存脱敏结果与交付摘要。主机路径、账户、boot、InvocationID、FS UUID、
inode、请求原件与原始日志继续私有保留。以前的 NOT_PREPARED 文档描述当时的交付状态，
不覆盖或删除；本记录提供后续进展。

## 一次汇总的验收矩阵

| 验证项 | 已返还结果 | 当前判断与保留条件 |
| --- | --- | --- |
| 固定源码、原生构建、ABI 和配置绑定 | 修正候选完成独立安装和实际管理查询，ABI 与冻结输入匹配 | 已报告通过；不外推其他内核、架构或 FS |
| 原普通身份权限对照 | generic 状态/额度查询均返回 ENOENT；FD 状态查询成功，FD 额度查询返回 EPERM | 保留真实 rc/errno，不把 ENOENT 改写为 EPERM |
| PrivateUsers 下权限对照 | 同一对照在私有 user namespace、零 capabilities 下完成 | 已报告通过；不能据 FD 定位宣称无需管理权限 |
| 管理查询 | 新对象报告 OBSERVED / PINNED_FACTS_MATCH | 只属于各自原请求；不替代旧 UNKNOWN |
| 写入强制 | 64 MiB 限额实验在 67,104,768 字节处收到真实 EDQUOT=122 | 私有 user namespace 下的新独立实验已报告通过；不以 ENOSPC 代替 |
| project/继承/域外边界 | 七项固定边界检查通过：创建继承、两类无变化操作、三类变更拒绝、域外写入拒绝 | 原首次准备失败与后续恢复记录分别保留 |
| 退出与采集 | 新实验完整 client exit、stdout/stderr EOF、原 deadline 内停止；退出复核报告三棵父树为空 | 已报告通过；不将旧缺 EOF 的采集修补成成功 |
| 历史保留 | 第一查询 UNKNOWN、早期 EXEC 失败、一次 INCOMPLETE 采集、原 payload 和永久意图仍保留 | 已报告保持；没有释放、清账或重放 |
| 合并配额域 | 四个独立域的硬限额为 64 + 64 + 4 + 64 MiB = 196 MiB | 包含原 UNKNOWN 全额；共享域按 FS UUID/project 去重 |
| 全部记录与封存容量 | 已报告五个保留范围的当前占用和 FS 容量；历史峰值未测量 | **原始容量依据待核对**；当前占用不是历史峰值或事前预留 |
| Q1 / E3 / 生产资格 | 所有相关报告仍保留 q1_accepted=false | Q1 未收口；E3 与生产支持未通过 |

## 当前唯一待补的实机输入

已交付 `q1-read-capacity-origins-20260925.sh`，SHA-256：

`02256c8250f47df38e37811d6f6dc94a163bbce870a173a05ef0ae63456795d1`

一次只读执行取得：已完成退出复核的摘要锚点；四域及五个保留范围；原始和修订配置中
authority/storage/manifest 的摘要与容量字段；首个 allocation 原件；当前虚拟盘容量与可读序列号。
执行不创建 VM 内文件，不启动查询或 writer，不改限额、权限、配置、意图或历史判定。
输出上限 32 KiB，保护输入单文件上限 2 MiB，外层有限超时。

本地已核对实际固定 reviewer 字节及 collector 封存格式，包括同一 jobs.after 被显式参数与
通配符重复列出的情况：相同摘要可读，冲突摘要拒绝。真实读取函数在隔离临时文件树中完成
全部读取；输入内容、inode、权限和修改时间保持；配置变更、冲突摘要和 boot 变化反例被拒绝。
这是读取逻辑验证，不是 VM 的容量验收。

## 容量结论只作一次完整判定

收到上述输出后，对照已有创建记录、固定源码、退出复核和原件作以下判断，不再逐项要求
重复配额查询、超限写入或边界实验。

1. 明确计费范围：哪些域、账本、原件、日志、构建产物及封存副本属于这次 fixture；
   同一个底层 FS 或同一个配额域不能重复增加可用预算。
2. 找到在相应实验启动前已存在的有限容量依据。storage.json 的 statvfs total/available
   只直接证明记录时的容量状态；allocation 的摘要只证明绑定，不能自行增加未声明的预算。
3. 对照保留域总硬限额 196 MiB，并核对账本、证据、控制记录和安装产物的范围。
   Q1 journal 最多 32 个意图、每意图三份不超过 4096 字节的记录，仅给出其文件内容上界，
   不能代替 inode、目录、FS 元数据、其他日志和封存副本的总占用。
4. 容量证明可以是原预算范围内的可信峰值记录，也可以是启动前固定的强制容量上界加上
   完整写入范围证明。后者必须证明相应硬边界在整个被评审期间成立、没有扩容/迁移到未计费位置，
   并计入全部保留与同时存在的封存副本。不能仅用现在的盘大小倒推过去。
5. 若采用整个独立 guest 的硬容量作为保守上界，必须明确其原始交付来源和覆盖的对象；
   guest 虚拟容量不自动证明 host qcow2/backing/metadata 的物理预留。结论不得超出已证明范围。
6. 原容量依据确实缺失时，明确记录 CAPACITY_PROVENANCE_UNPROVEN 和缺少的最小字段。
   不追加重复只读盘点，不补写历史授权，不扩大旧预算，不创建新 slot 把旧失败变成成功。

可复核的关系为：原 UNKNOWN 仍全额占用；唯一计费域硬限额合计不超原域预算；
全部保留及封存的可信峰值或强制上界不超同一范围的原容量预留。
只证明其中一个关系，不足以证明其他关系。

## 本轮同时完成的共享退出监督修正

在核对后续接线时，发现既有 `runner._inspect_unit` 会将“叶 cgroup 不存在且 unit 为
inactive/failed”作为树已退出的证明。实际 manager 转移的回归测试复现了两个状态下
都可能继续交付 helper 的问题。

本轮本地修正为：cgroup.events 缺失或不可读时，不授予递归退出证明；保留 UNKNOWN，
按原身份请求停止，并阻止下一阶段交付。已读取到 `populated=0` 的现有路径保留。
这属于既有 E1–E3 监督失败处理的保守修复，不添加 Q2 quota 接口，也不向 VM 安装源码。
它不代替完整父树身份、原启动围栏、launcher/EOF 和 deadline 的后续整合证明。

- [修复前复现](validation/e3-missing-cgroup-20260925/pre-fix.log)：1 项测试的两个子场景均失败；
  [原命令记录](validation/e3-missing-cgroup-20260925/pre-fix-command.json)保留预期失败。
- [修复后定向验证](validation/e3-missing-cgroup-20260925/targeted.log)：bootstrap、runner、
  result-reader runner 和 bootstrap broker 共 75 项，74 通过、1 跳过、0 失败；
  [命令与源码摘要](validation/e3-missing-cgroup-20260925/targeted-command.json)记录准确环境与字节。
- 新回归实际调用 `manager.inspect`，核对无第二次 launch、无 helper、UNKNOWN、
  tree_exited/effects_checked 均为 false，且仅向原 bootstrap 请求停止。

这些结果是本地隔离逻辑验证，未运行实际 systemd/quota。唯一跳过项为真实委托 cgroup 集成：
本执行器 PID 1 非 systemd，且没有委托准入和专用非 root 账户。跳过项不记为通过；生产支持封堵仍在。

## 通过后连续推进的工作批次

| 批次 | 一起交付的内容 | 放行条件 |
| --- | --- | --- |
| Q1 收口 | 容量来源判定、完整验收矩阵、准确实机证据锚点、历史失败保留清单 | 上表待补项取得可核验依据 |
| Q2 接口与预算 | 协议/peer、严格绑定、管理额度、持久防重、bootstrap 消费、恢复语义及对应测试 | Q1 出口通过；先审阅接线差异，不静默继承 Q1 假设 |
| Q3 正常链 | 同一核心的真实 bootstrap/helper/reader、H01–H05、完整采集和独立退出 | Q2 身份、预算、响应丢失和阻塞负例通过 |
| Q4 故障矩阵 | H06–H13 的有限注入、停止/保留、恢复和共享核心回归 | 正常链通过，且对应故障有明确解除入口 |

每个开发批次同时完成实现、必要定向验证、差异审阅和记录；需要机器配合时先交付整个可执行批次。
批处理按依赖顺序停止，不在错误或 UNKNOWN 后自动补投下一实验。互不依赖的只读取证可以一次完成。
文档草案不等于提前进入 Q2 实现，运行完单个脚本也不等于整个阶段通过。

## 已成功交付的关键脚本摘要

| 私有交付文件 | SHA-256 |
| --- | --- |
| q1-enforce-userns-slot004-20260925.sh | 9fbfb82a461e6e5da710dd77e457a22cd207e4f3b789aad7c5fce8a23ce951a5 |
| q1-review-exit-evidence-fixed-20260925.sh | 7415c0c5ae89ed88835733c6fda8721896da3d2fc0e8d98c850494f4bf27ffd8 |
| q1-read-capacity-origins-20260925.sh | 02256c8250f47df38e37811d6f6dc94a163bbce870a173a05ef0ae63456795d1 |

前两份已经运行过，不重放。本次源码仓保存共享监督修复、合成回归证据和脱敏进度/设计记录，
不收录这些私有脚本或现场日志。
