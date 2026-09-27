# Q2 历史未来安装承诺对账：架构提案

- Authority：Owner；状态：**PROPOSED / Gate OPEN / BLOCKED ON HISTORICAL INPUTS**。
- Scope：`LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`。
- [需求](REQUIREMENTS.md)只允许终止已鉴证历史尝试的未消费未来安装义务；[实施方案](IMPLEMENTATION_PLAN.md)要求先补真实输入，再形成新 A/B/C。

## 对账对象与责任

本变更对账的是安装义务，不是释放物理文件、配额或原始证据。每一项义务的身份
由原 reservation 摘要、原尝试、目标安装、费用类别和原授权组成，不由当前目录名
或新 epoch 自行生成。最初 192 MiB 与恢复阶段声明必须证明属于同一原候选/目标；
第二次 64 MiB 独立列项。其他原记录中的全局 ceiling、累计 actual 或嵌套义务不
重复当成独立额度，也不能在不知来源时认定其已经覆盖。

| 责任 | 输入与输出 |
| --- | --- |
| 历史来源核验 | 原 raw、原计划/回执摘要、历史树 manifest；输出可复算的来源链及缺项，不授予新的历史可信性 |
| 现场联合鉴证 | 同 guest/boot、准确 FAILED/Invocation、无 job/PID、空树、两旧 ledger、七根与保护配置；输出有界状态观察 |
| 义务分类与账单 | 独立承诺、嵌套承诺、实际覆盖和未来剩余；分别处理 bytes/inodes，保留原 source/记录 |
| 新追加记录 | 仅在准确新 A/B/C 和全部前置条件成立后，create-only 记录本次有限 supersession |
| 原 startup 准入 | 用旧实际加全部剩余义务和新峰值重新核算；成功对账不等于发行、停止证明或 Q2 acceptance |

所有原始机器路径、账户、unit/进程标识、私人计划和 raw 留在私有交付。公开只
发布协议、负例、脱敏来源和验证边界，不把 Private source 内容复制进 Public。

## 历史输入的可信性

可接受两种路径：

1. 原执行时保留的 raw，与既有可信回执或 Owner 提供的真实留存来源绑定，验证
   其全部引用、准确计划/候选、发行和原摘要。
2. 在既有历史树摘要已经可信的前提下，完整展开原路径、类型、身份、大小和内容
   摘要等原算法输入，重算后必须匹配该历史摘要，再由已匹配 manifest 证明成员。

第二种路径不能把一个历史根摘要当成“任意当前文件都可信”的通行证。只提供单个
成员或遗漏原算法字段不能证明树。第二 staging 目前缺历史树锚，不适用自行展开
并给当前树新签名的做法。无法取得可信原始来源时保持 INPUTS_BLOCKED。
新的 Owner 计费决定不能补造旧字节；若需要采纳新的事实来源，那是另外明确记录
的证据来源变更，不能由本提案自动推出。

历史文件逐段 no-follow，实际读取/枚举使用 O_NOATIME，核验 held fd 的身份、
权限、单链接和读取前后摘要；读取被拒不放松保护重试。SQLite 从固定原 fd 读取
有界 bytes，在 RAM 副本按已批准规范检查，不让 SQLite 打开旧路径、创建 sidecar
或恢复数据库。任何 metadata、成员、boot、unit 或内容变化使本次鉴证失效。

## 终止条件与追加记录

所有原 preparation、recovery、CPUQuota retry 外层和监督器的已知失败实例，均
绑定准确历史身份与退出证据；原未创建的监督器/target 仍按各自失败阶段核验。
当前没有 job/PID，相关父树为空，manager 配置与能力集合未变；七根身份/限额/
成员和两旧 ledger/generation/空表满足原复用条件。不得 reset-failed、stop/restart
或删除历史对象来制造准入状态。

拟新增的追加记录同时绑定：本 scope R/A/B/C/D、原 startup A/C、唯一尚未发行的
startup 计划摘要、准确 runtime、两项原安装义务及其 raw/历史树证明、嵌套关系、
现场观察摘要、对账前后 byte/inode 账单、终止的未来剩余量及继续保留的实际量。
只终止明确属于两次已终止尝试的未来安装部分。capture/runtime 等其他类别及
quota 的 before/after 必须完全相等；原文件摘要与原结论也必须相等。

记录有独立身份，排他创建、完整写入并 fsync 后才可被本次容量计算采用。记录
部分写入、缺 seal、摘要不符或 concurrent loser 均不能继续安装；保留中断材料，
不删除后重做。不得原位写入旧 reservation 的 released 字段。后续重复调用只能
验证同一个已存在记录与原请求是否完全一致，不能发出第二条释放或第二次运行。

本 amendment 对象使用独立版本和明确 authority；旧 schema 与旧 CPUQuota 入口
继续按原规则解释。不能给现有 startup v1 偷加一个免检开关。新实现只在本 scope
C 后产生，并将对账后的受限准入明确绑定到原未发行 startup 批次；原 C 仍是
其余运行行为的授权来源。

## 容量与期限

对账后的准入必须逐类、逐设备核验：去重后的全部历史实际分配 + 尚未终止的
独立义务 + 本次新增峰值及最终证据余量。原树与安装文件一直计入实际分配；没有
消费的 future 才可在明确授权和证明下由追加记录终止。bytes 和 inodes 分别计算，
不得按比例推算 inode，也不得把同一份 actual 拿去覆盖不同独立义务。

安装总上界仍 256 MiB/原 16384 inode；state/journal/capture 原 ceilings、两个
owner/runtime 承诺、七个 quota 根和 Q1 承诺保持。原有剩余空间/设备容量检查
仍执行；历史实际增长、新安装峰值、对账记录/日志/封存开销使总量超限就 BLOCKED。
不借用其他类别、回收文件或扩容。

现场鉴证、追加记录和安装准备都必须发生在原 startup 唯一新 300 秒窗口内，
并消费原准备阶段与管理 CPU/输出预算。关闭本 amendment 不是另开一个管理窗口
或第二次批次；已经开始的窗口不能延期。源材料的会话内只读审阅不是 guest
运行，不声称完成现场鉴证。

输入状态、Gate 状态和现场对账状态分别记录：输入未验证时为 `INPUTS_BLOCKED`，
Gate 保持 OPEN；准确 B/C 后才能进入 `ATTESTED → RECONCILED`，其后仍须
通过原 startup 准入才能发行。`RECONCILED` 只表明新的计费记录成立，不证明 Q2
运行、原停止、EOF 或验收；新成功永不补判旧 INCOMPLETE。
