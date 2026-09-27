# Q2 历史未来安装承诺对账：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；[需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。
- 本轮交付为准确三层文档和证据复核；不提前实现合同、算法、原型、测试脚手架、运行配置或 guest 入口。

## P0：提交准确 A，等待一次 Owner 决定

已取得此前六份缺失 raw 与 preflight；12 个历史树和 15 个旧单文件锚复算一致。
现有材料足以提出准确而有条件的变更，不再要求 Owner 手工重复补这七项。
两条第二 bootstrap raw 的来源采纳、准确第二 staging 当前完整树及相邻 intent 的保持性起点、
五项 post-read 元数据起点和两笔 future 的
有限终止必须同在准确 A 中审阅。现场完整性/时效性与容量仍是未来执行前置，
不把它们写成已经满足，也不以“原则批准”补造历史字节或授予无条件运行。

该保持性起点精确为私有 `forward-baseline-index.json` 的 610 条目（staging
树 609 项、准确相邻 intent 1 项）/ 239944
bytes，SHA-256 `9b5b5ec8dd1516cb8807bf26f657c652079843a3669783db215a4f9c5dd5852e`；
同时引用需求中的外层包与 guest manifest。其 proposed-only 与非历史身份声明
不原位改写；B/C 仅赋予本 scope 后续比较用途，不将该索引升级为历史树锚。

将这三份确定字节提交为 A，记录文件摘要。Owner B 必须明确引用 R、准确 A、
本 scope 及上述三项决定；保存准确原话、时间或事件 ID 和稳定来源。独立 C
只登记关闭与 R/A/B，不混入实现；D 必须从 C 继续。既有 startup
A `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc` 与
C `d4a925c883672fadc7d1b10a8dfe58df18b922cd` 及其原三文档字节保持。
未有新 B/C 时停在此阶段，旧 startup v1 对超限仍失败关闭。

## C 之后的实施阶段

| 阶段 | 交付与通过条件 | 需求 |
| --- | --- | --- |
| P1 输入合同 | 独立严格 schema 与私有 evidence-adoption manifest；旧 pin 原样保持，仅允许准确两项新 raw、一个第二 staging 当前树起点和五项偏差；全部引用可复算 | I01、I02、I07 |
| P2 只读鉴证与账单 | 复用受保护读取、RAM ledger 检查和有界观察；补齐七根实测及完整树；两目标 C/A/U 与所有未变费用明确，无未知量记零 | I02–I04、I06 |
| P3 追加记录与有限接入 | 固定五文件、state 1 MiB/16 inode；排他创建、fsync/seal；新 amendment driver 验证后衔接原唯一 startup 计划，旧 v1 不接受新记录 | I04–I07 |
| P4 隔离验证与准确 D | 定向负例、真实本地临时文件验证、相关已有测试与打包/编译检查；固定 D、树、工具摘要与未变 runtime；无 guest 运行 | I01–I07 |
| P5 原唯一窗口内执行 | 按下面的执行顺序联合鉴证、追加一次对账记录、重核准入；条件成立才继续原安装/装配/一次发行 | I02–I07 |
| P6 回传与核验 | 保留新旧 bytes、偏差、分类账单与分层运行结果；公开摘要/索引，原机器证据私有；不足明确保留 | I01–I07 |

实现落点限 `tests/e3_host/` 专用 amendment 合同、来源/计费适配、driver 与针对性
测试。不修改冻结 wheel/Plugin/runtime，不新增系统依赖，不让通用入口接受
release 开关。具体模块文件名可沿仓库惯例决定；schema、金额、来源采纳、
记录上限、状态与失败行为必须遵守本 A，不能以文件命名自由扩大语义。

## P5 的唯一执行顺序

1. host 离线校验准确 R/A/B/C/D、既有 startup A/C、私有 manifest、固定候选
   和唯一未发行计划；在首次 host/guest 现场探测前固定外层 300 秒绝对 deadline。
   一切现场核验与后续执行共享该唯一窗口，不能先查现场再开始计时。
2. 在首次新持久写入前，完成架构规定的全部现场联合鉴证，包括回传未覆盖的
   第二安装/capture/state 树、两 ledger、Q1、七根 ioctl/quota 与完整相关
   cgroup；准确 post-read 起点如已漂移立即停止，不能重新设基线。
3. 内存中形成完整 before/拟 after，分别校验 bytes/inodes、真实设备剩余容量、
   五文件实际分配峰值及日志/封存费用。所有类别、硬限制、CPU/内存/tasks/输出
   和剩余期限满足，才排他建立新 state 目录与固定材料。此时尚不安装或发行。
4. 按 append-only 顺序完整写入、fsync 并 seal；不改旧 reservation。seal
   完成后验证其引用和账单，才可采用只去除两项目标未来余额的计费结果。
5. 原 startup 准入再次核验所有可能漂移的来源/状态/费用及 deadline；任何
   缺项、超限或资源不足保留已写记录并 BLOCKED。通过后才继续原独立安装/
   装配与唯一发行；发行前最后检查没有 TOCTOU 身份、容量或期限漂移。
6. stop、双流 EOF、fsync、封存与回传按原独立证据条件完成。任何部分失败
   均保留真实结果，不删除重做、不换 ID、不刷新 300 秒、不自动再发一批。

全部准备鉴证/对账/安装/装配共同使用原 140 秒准备阶段，不另加前置 guest
窗口。现场项目多不构成扩时理由；无法在预算内取得全部事实就不发行。
本次离线审阅和 Owner 源材料采纳均不声称已经完成 P5。

## P4 的关键验证

| 负例或边界 | 必须结果 |
| --- | --- |
| 任一 raw/旧 pin/树算法字段改变，只有根 hash、不完整条目或未知来源类别 | INPUTS_BLOCKED，无对账记录、安装或发行 |
| 当前两项 raw 被冒称历史 pin、第三项新来源、没有准确 B/C、采纳摘要不同 | 拒绝；不得以源码预期值或新 hash 代替授权 |
| 整包或第二 staging 当前树被冒称历史证明，换 root/manifest，忽略实际 index 差异 | 拒绝；当前树只作精确保持性起点，旧 12 树历史证明不变 |
| 五项偏差加减项、post-read 再漂移、恢复时间戳、缺 O_NOATIME、父路径替换 | 拒绝；不保护降级，永久保留原采集偏差 |
| 同一实际对象覆盖两义务、恢复 192 MiB 重计、113274880 被当独立 future | 拒绝；按原引用与目标归属解释，不能猜测去重 |
| A=0、A=C、A>C，bytes/inodes 一维超界，原 staging 预留 inode=0 但实际非零 | U 分别为 C、0、0；实际全计；两维分别算，不能负余额/截断实际/漏 inode |
| 第二安装或其他当前树缺失、扫描截断、quota 常量冒充实测、任一 live 项未知 | BLOCKED，不以回传快照或零填充值通过 |
| boot/InvocationID/ledger generation/原 root 身份改变，job/PID/后代非空 | BLOCKED，不 reset-failed、不删除、不停启旧对象 |
| capture/runtime/staging/recovery stage/Q1 费用被减少，owner 共池重复覆盖 | 拒绝；只有两项目标 U 可变，其他义务不变 |
| 记录超字段/文件/实际块/inode 上限、parse 重复 key/未知字段/整数溢出 | 写前拒绝；不得新增文件绕过上限 |
| intent/record/seal 任一步短写或 fsync 失败、并发 loser、同 ID 异值 | 保留部分材料，拒绝采用和继续；不覆盖、删除或换 ID |
| 完整同值 sealed 记录重复提交、旧 v1 收到 amendment、新记录交给另一计划 | 只读校验不重复释放；旧入口拒绝；跨计划拒绝 |
| seal 后来源/容量/期限再漂移，after 仍超任何一项 ceiling | BLOCKED，已写记录不等于发行许可 |
| 对账成功而 runtime/stop/EOF/封存失败 | 各状态独立，历史 INCOMPLETE 不变，不自动验收 Q2 |

真实本地文件检查应覆盖受保护 fd、路径替换、regular 硬链接、原允许 symlink、
O_NOATIME 失败、SQLite RAM 副本无 sidecar、create-only 与真实 fsync 故障边界。
源码/打包验证只扩大到本改动实际影响的既有入口；所有结果绑定准确 D，不拿
先前 startup D 的通过结果冒充新实现验证。任何环境不支持的检查明确 BLOCKED。

## 收口标准

文档提交 A 不关闭 Gate；准确 B/C 不代表实现或现场成功；D 验证不等于发行。
完成 P6 后分别给出来源采纳、元数据偏差、两项终止余额、仍保留的全部实际与
其他义务、准入结果及 startup 各阶段证据。只有实际证据满足原验收条件才能
报告新的 Q2 结果。若不能发行，准确报告阻断并保留唯一批次的实际授权消费状态，
不把已开始但失败的窗口描述成仍可任意重启。
