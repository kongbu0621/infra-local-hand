# Q2 历史未来安装承诺对账：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；采用、来源可读性、完整性与变更规则沿用根 `AGENTS.md`。
- 本文与[架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)共同构成待审文档；准确 A 为包含这三份确定字节的提交。尚无本范围的 Owner B、关闭记录 C 或实现 D。

## 本次请 Owner 决定的事项

在准确 A 上一次审阅以下三个相互绑定的有限变更：

1. 将本次 Owner 回传的第二 bootstrap 两份准确原始值，作为**今后对账的新来源输入**采纳；第二 staging 的准确当前完整树及相邻 intent 另作为后续保持性比较起点。两者都不补判与历史时点的字节相等。
2. 保留五项已披露的 atime 变化，允许本 scope 采用回传中准确的 post-read 元数据作为后续比较起点；不恢复时间戳，不声称旧采集保全成功，不放松之后的 O_NOATIME 和元数据拒变检查。
3. 在全部现场前置条件成立时，只追加终止两项已终止尝试中未消费的未来安装义务；实际存量及所有其他承诺继续计费。对账后仍不满足准入即 BLOCKED。

该决定服务于既有 startup A `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`、C
`d4a925c883672fadc7d1b10a8dfe58df18b922cd` 批准的**唯一尚未发行新批次**。
本回传与离线审阅没有发行该批次、没有消费其运行授权。更早两次已发行失败和
INCOMPLETE 结论永久保留。既有 C 不替代本次 B/C；在本次关闭前不实现对账行为。

## 现有证据足以形成准确提案

本次回传包 SHA-256 为
`869a859fcbe7a952d11e22db6f6534c9b9a3025cec27471fe3e2a054a6a96018`。
[独立复核索引](../evidence/q2-readonly-return-20260927/README.md)与其 manifest
保存准确材料、验证范围和私有原件定位。此前六份缺失原始值与 preflight 均已取得；
12 个历史树摘要、15 个历史单文件摘要复算一致。preflight 原字节还通过历史
准备树成员证明，与此前推导的预期字节一致，不再列为缺失原件。

仅下列两项缺少既存独立历史整文件摘要或完整历史树锚。本次当前 hash 不能冒充
历史 pin；本提案明确请求把它们标记为 `CURRENT_OWNER_SUPPLIED_RAW`，仅支持
今后的有限对账。原动态时间、当时空间观察和历史成功性仍不由此证明。

| 新采纳输入 | 字节数 | 当前 SHA-256 |
| --- | ---: | --- |
| 第二 bootstrap intent | 556 | `58992ee2ff0d66fec5e10c7e138e8de4529089ca35d76f71200db1a05ac160b6` |
| 第二 bootstrap attestation | 7766 | `cfc6c07265b4edc6d0b26e67a6ca9cfc19c652b4d011a2386b9bd95e945a34cb` |

同一 guest manifest 中，逻辑角色“第二 bootstrap staging 根及相邻 intent”的
完整成员与实际现状仅被请求采纳为 `CURRENT_PRESERVATION_BASELINE`。其
610 条目（staging 树 609 项、准确相邻 intent 1 项）被精确固定于
`forward-baseline-index.json`（239944 bytes），SHA-256
`9b5b5ec8dd1516cb8807bf26f657c652079843a3669783db215a4f9c5dd5852e`。
固定范围为准确第二 bootstrap intent 对应的 staging 根及完整后代、相邻 intent，
不含其他旧根；绑定上述包 SHA、下述 manifest SHA 与初次无保护 hash 探测后、
guest-inventory 记录时点。该 manifest 不是全部归档读取后的完整二次 stat 鉴证。
该索引保持 `proposed_only=true`、`historical_identity_claim=false`。第二 staging 与原交付
545 文件对比有 544 个字节相同，唯一不同为 Git index；独立解析其 505 条路径、
blob OID、flags/mode 及扩展相同，仅 stat 缓存的 ctime/mtime/dev/inode 改变。
新 index 的真实 bytes 纳入此当前基线，不能据此称整棵 staging 历史字节不变。
包整体只是载体，不能把所有包内文件泛化为历史权威；原 12 个历史树锚仍原样使用。

五项 atime 变化涉及原 bootstrap intent、第二 bootstrap intent、恢复 intent、
恢复 stage、第二 bootstrap attestation。准确项目与 post-read 值由私有元数据说明
SHA-256 `5a99256c38bb28b9188114f47763f7cc5d54b4b90f52fc01f2c7ad44cd68a1e6`
及 guest manifest SHA-256
`82c8c13e250ac0be0957b766e84827514dd50cc5cc53d461c126d6dd0523f735`
共同固定。原准备 intent 和 preflight 不在这五项之中。采集前原始 stat 转录未留存，
故“变化仅为 atime”的采集者声明不能扩大成全部元数据保全证明；历史树不含 atime，
其匹配也不能证明 atime 未变。新决定只接受明确的已记录现状，不追认该声明。

## 两项可终止义务与完整计费

对 bytes 和 inodes 分别计算。令 `C_i` 为准确义务原上界，`A_i` 为**该义务准确
安装目标树内、按设备/inode 去重并可归属的现场实际分配**；`U_i=max(0,C_i−A_i)`。
只可令下表两项的未来余额 `U_i` 归零；全部 `A_i` 继续保留在账单。

| 安装义务 | C bytes | C inodes | 固定关系 |
| --- | ---: | ---: | --- |
| 原安装目标 | 201326592（192 MiB） | 8192 | 恢复阶段同额声明属于这一笔，不再计第二次 |
| 第二独立安装目标 | 67108864（64 MiB） | 4096 | 第二 bootstrap 的 113274880 = 46166016 旧 actual 基数 + 67108864 新峰值，不能把总值另列一笔 |

两目标不得交叉用 actual 覆盖。不得用整个旧批次 `costs.installation`、source/
staging 或原 ceiling 代替 `A_i`。实际超过承诺时也全额保留，不截断实际量。
原 staging/retained-delivery 18788352 bytes、第二 staging 11071488 bytes /
608 inodes、恢复 stage 290816 bytes / 17 inodes 不在终止范围；实际 inode 高于
旧预留时仍按全部实际计入。两 owner 各 20971520 bytes / 384 inodes 的
capture/declarations/journal 共池及其他承诺不变，不给各子目录重复套同一池。

严格原规则下，已知安装类下界已达 **365694976 bytes / 17599 inodes**，高于
268435456 / 16384 上界，且未计本次新 staging 等费用。此处是原规则的拒绝下界，
不是可释放金额，也不是对账后的完整账单。本包缺第二安装与部分第二 capture/
state 当前完整树，不能给出准确静态 after 或承诺“批准后必能发行”。

## 验收要求

| 编号 | 要求 | 通过条件 |
| --- | --- | --- |
| I01 | 来源分类准确 | 既有历史锚继续用旧证明；仅两项新 raw 作义务来源，准确第二 staging 当前树仅作保持性起点；所有引用、原计划、候选、义务和 raw 摘要一致 |
| I02 | 五项元数据偏差有界 | 仅准确五项采用上述 post-read 基线；永久保留偏差说明；未来逐段 no-follow/O_NOATIME 与读取前后身份、内容、元数据拒变 |
| I03 | 两项历史尝试确已终止 | 同 guest/boot、全部已知历史实例身份和退出、无 job/PID、完整相关 cgroup 空树、配置与保护检查联合成立 |
| I04 | 仅终止准确未来余额 | 两项 `C/A/U` 可复算，恢复同笔去重、目标归属互斥；全部实际、其他类别与其他承诺原样保留 |
| I05 | 追加且不可重放 | create-only 意图、记录和 seal 绑定准确 R/A/B/C/D、既有 startup A/C 及唯一计划；部分写入保留，不能删除换 ID 重试 |
| I06 | 前后均有界 | 首次持久写入前验证全部现场事实、state 新开销和拟采用后账单；发行前再核验来源、状态、期限和全部容量；任一未知/漂移/不足均 BLOCKED |
| I07 | 运行权限不扩张 | 旧 startup v1 继续严格失败关闭；新 amendment 仅在本次 C 后实现，运行候选和唯一批次的其他限制不变 |

现场前置必须补齐第二安装目标、两批次全部计费树、完整 Q1 保留树、两 ledger、
七根真实 project/inherit/UUID/硬限额/usage、完整相关 cgroup、账户/能力/manager/
namespace 和双次 boot 观察。本包中七根 project_id 是采集器常量，不是配额实测；
它及离线快照均不能直接充当现场准入。上述检查统一放进原唯一窗口，不再要求
Owner 手工重复寻找已取得原件。若窗口内无法完成，就保留失败且不发行。

## 固定预算与排除项

运行候选保持 commit `b49d3df3d1e76813faf08e59ab4975e25279c2fc`、tree
`2d957ccf1d9cbdf5e538189c6b68d56f34590a42`、wheel SHA-256
`c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b`。
任务仍仅为原 `host.inspect`、空 inputs 和固定三阶段，业务能力集合不变。
安装/source/build 总类 256 MiB / 16384 inodes；state 32 MiB / 4096 inodes；
journal 与 capture/declarations 分别 64 MiB / 4096 inodes。七个项目各
1 MiB / 128 inodes、Q1 四域 196 MiB 保留承诺不变；唯一硬限制按原规则只计一次。

新增对账材料在 state 类内显式保留 **1 MiB / 16 inodes**，含五个固定文件、
一个新目录、实际块取整和封存峰值；它不是新增总额度，也不能从外部输出池抵扣。
超过该子预算或使原类别超限即拒绝；具体文件上限见架构。

原唯一 300 秒窗口、guest ≤270 秒、全部准备鉴证/对账/安装/装配 ≤140 秒、
owner ≤120 秒、stop ≤3 秒保持。管理 CPU≤300 秒、512 MiB / 64 tasks；独立
运行域 CPU 合计≤400 秒、内存合计≤1536 MiB、tasks≤1024；外部双流所有阶段
合计≤2 MiB，内部原更小限额保留。写记录和现场核验消费同一绝对期限，留足
stop/EOF/fsync/seal，不能加窗口或重计时。

不删除旧文件、不恢复时间戳、不 reset-failed、不停启历史服务来制造终止状态、
不改变 quota/账户/挂载/权限/能力、不增加依赖、不替换候选。不包含 Q3、H06–H13、
production、GX10、真实 NAS 或 E4–E6。准确 B/C 前仅文档与证据审阅，不生成实现、
测试脚手架或 READY 实机入口。
