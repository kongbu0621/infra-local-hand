# Q2 唯一窗口的 host 持久消费记录：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-HOST-WINDOW-CONSUMPTION-v1`；R 与[需求](REQUIREMENTS.md)一致。
- 本文仅补充固定 host 消费顺序；旧 startup v1、对账合同及冻结 runtime 的其它语义不变。

## 组件与输入

| 组件 | 责任 |
| --- | --- |
| 离线校验器 | 固定本 scope R/A/B/C/D、旧 startup/对账批准链、唯一计划/manifest、host 定位、wrapper 与完整工具闭包 |
| host 窗口所有者/记录器 | 首次现场读前固定双钟，核验 host 小额记录费用，排他持久消费后才远端探测 |
| 原联合鉴证与对账链 | 完整现场事实和 host/guest 共同账单通过后，才追加原 guest 五文件并继续原一次交付 |
| host 封存器 | 联合准入后对实际原流/结构化材料逐件核验并封存，独立于 guest stop/EOF/seal/验收 |

host 适配入口必须同时验证三条准确批准链。旧解释器不接受 release/retry 或
忽略消费的开关，不把新记录变成可在旧 v1 独立运行的新授权。公开只保留合同与
摘要；真实 host/boot、路径及身份在准确私有输入内。需求中的原 carrier 与当前
host attestation 摘要/长度是固定输入，不由调用者新配置选择。只读 AST 常量
解析复算唯一父目录和固定 startup C 消费名；只读严格 JSON 取得预期 host boot。
该当前 host 事实是本 scope 的明确采用，不属于历史复原或原对账两项 raw。

意图严格字段包括：独立 schema/scope、三条批准链、准确编排 D、唯一 attempt/
计划/对账 manifest、wrapper/工具摘要、固定 host/预期 boot、原 startup C 消费键、
准确父目录来源与规范派生定位、目录身份、
双钟 issued/deadline、host 预检查证据与子预算，以及 `window_consumed=true`、
`owner_issued=false`、`run_permission=existing_startup_once`。原有严格 JSON、
重复 key、字段/整数/路径/长度上限拒绝规则继续适用；不得把未来状态回填原意图。

## 原点、竞争与同步顺序

离线只校验已持有的确定 bytes，不读取新现场事实。每次 `LOCAL_PREFLIGHT` 在新的 host stat、文件系统预算或 boot 查询以前先取
MONOTONIC/BOOTTIME 临时采样和各自 `issued + 300s` 上界。此阶段只读本地，
无远端调用或主动新持久对象，尚未消费批次；失败可重新完整验证。成功排他创建固定
目录的赢家把同一对采样固定为唯一批次原点，目录创建不重采样；所以赢家的
前置检查耗时也全部计入 300 秒及准备 140 秒。之后所有 guard 同时检查较早余量。
准确 host/预期 boot 从已固定来源核对；host 重启或身份不符始终拒绝，不在
重新本地检查时接受新 boot。该变化明确改变取得标记以前的重试语义。

1. 只读完成 host 记录预检查，在 RAM 准备确定字段。费用包括实际分配/目录/
   部分写入和同步峰值；host 文件系统不能证明 ≤64 KiB / 4 inode 就创建前拒绝。
2. 沿 held no-follow 父目录 fd 排他创建固定消费目录。目录出现即消费；并发
   败者及任何既存对象均停止，不自动接管、删除或换路径。
3. 同步必要父目录，目录身份确定后在 RAM 完成编码；用 `O_CREAT|O_EXCL`
   创建唯一 `host-window-intent.json`，完整写入、fsync 文件和消费目录/必要父目录。
4. 重新核验实际固定成员、bytes、SHA-256、权限/链接数、设备/inode 及分配峰值。
   只有全部成功才能首次远端探测；任一步失败都保留部分材料且不远端调用。

实际读/枚举使用 O_NOATIME，不降级重试或恢复时间戳。祖先固定身份、保护及名称
到 inode 绑定；叶项与旧证据完整树仍比较全部所需元数据/内容，避免新兄弟目录
合法创建误触祖先时间比较。symlink、hardlink、未知 ACL/权限或路径替换均拒绝。

持久性依赖已核验的 host 文件系统履行成功的文件/目录 fsync，以及父目录保护
不被范围外管理者解除。RAM、close 或外观完整文件不能替代同步证明。跨进程保证建立在同一 host boot 内已成功创建的目录不会被范围外删除/回滚的
可信文件系统假设上。进程崩溃不删除目录；断电/重启由固定预期 boot 拒绝。工具
不能声称能检测“同 boot 管理者回滚整个目录后仍显示不存在”；该行为违反输入
存储假设，不属于恢复授权。观察到错误、存储回滚或持久性不明时应 UNKNOWN/
BLOCKED，不能用此文字假装已经实现不可观察的回滚检测。

## 状态与计费

顺序为 `OFFLINE_VERIFIED → LOCAL_PREFLIGHT → HOST_RECORD_ADMITTED →
HOST_WINDOW_CONSUMED → HOST_INTENT_DURABLE → REMOTE_PROBED → JOINT_LIVE_ATTESTED`。
后续才进入原对账 seal、再次准入、安装/装配与 owner 发行。目录存在但意图不全为
`CONSUMED_PARTIAL / BLOCKED_RETAINED`；意图完整但预检失败为
`CONSUMED / BLOCKED_RETAINED`。同值记录只能只读核验，不从任何状态重新派发。
仅 `LOCAL_PREFLIGHT/HOST_RECORD_ADMITTED` 且固定消费路径尚未创建时，可以
重新完整本地检查；不能复用观察或产生远端/持久副作用。目录取得后的失败没有
返回这两个状态的路径；任何既存路径也不进入本地重试分支。

host 预检查只允许准确的小额提前记录，不能据此声称共同容量已通过。联合准入
按同一 capture 类和真实设备/inode 汇总 host/guest 实际、各自未用承诺及未来
封存；子预留已覆盖的实际只计一次。原 guest 对账 state 子预算独立。合计超限
即保留 host 消费记录、不主动创建 guest 业务/对账/state 对象。原已批准传输/
管理域的自然审计日志仅按需求中的明示边界、原预算计费；
不借此新增服务或日志设施。联合准入前不主动保存原流/结果/其它诊断；
失败只保留白名单记录和原有界通道结果，不另开窗口补收或补 seal。

## 交付和封存必须保持的原合同

wrapper/来源摘要、真实文件元数据/内容、完整成员 seal、有限收尾和真实远端
截止属于既有交付合同的必要修复，不由本提案授予新增运行或提前写入权限。

一次保守 host/guest 时钟映射必须包含 host 预检查/落盘已耗时间。派发时把
准确 guest 绝对截止落实为已有准许管理域的有效硬期限；不得向上取整越界或
在到达后刷新为 270/140 秒。排队、stdin 传输和初始化也计时，入口动作前再查
boot/期限；迟到或不足以容纳 stop/EOF/fsync/seal 的有限开销就拒绝。无法在
既有边界证明硬期限就不派发，不新增范围外持久监督设施或改系统配置。

杀死/关闭 SSH client 只证明本地状态；远端停止需要独立停止和准确身份/树空
证据。失联、不可中断 I/O 或缺 EOF 保留 UNKNOWN/INCOMPLETE，不重发。

联合准入后 host 证据目录仍 create-only。每件实际文件保持 held fd 与路径绑定，
按准确成员、长度、SHA-256、owner/mode/nlink 复核，读取 O_NOATIME；写入后及
生成 core/bundle 前后均核验真实文件，不能只核 RAM。最终 seal 逐件列出已有
材料，绑定消费意图、唯一配置/manifest、原时钟及各阶段事实/缺项；seal 不含
自己的摘要，避免自引用。未知项、同名替换、短写或 fsync 失败都不封存，不能
延长窗口形成外观完整材料。host seal 不替代 guest seal、stop、EOF 或 Q2 验收。
