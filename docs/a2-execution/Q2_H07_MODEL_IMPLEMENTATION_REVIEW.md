# Q2 固定监督域与队列证据一致性组件

2026-09-29 +08。接续[现场资格复核](Q2_FIELD_QUALIFICATION_NEXT_REVIEW.md)，
本轮在原 CLOSED H1/H3/H4 内实现离线域清单及有限队列状态校验，
并在 H2/H4 内补齐 ext4 EA_INODE 的拒绝条件。
实际首次远端监督尚未实现；原 startup batch 仍 NOT ISSUED，完整 Q2 未验收。

## 准确实现与授权

| 项目 | 准确值 |
| --- | --- |
| 实现 D | `293cb51f2318ebd82761f8f7855ba8bbc945d3c3` |
| D tree | `3c70536fc75625228ebbcaf097c586198038d14f` |
| Parent | `3a328aa159e96f1a96dcd8cec1e013b7473d59d0` |

原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 已复读，直接原件 SHA-256
为 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
H A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37`、独立 C
`271c07cd16140aa5942dcf3fad468003c58b6b0e` 和三份批准文档保持。

本轮不新增来源采用、现场读写、监督设施或批次。审查的数据输入是确定 bytes；
既有 Python helper 仍可能在 API 调用过程中动态加载受信仓库源码。
因此“无现场读取”指不沿输入路径取得新事实，不是整个调用完全没有文件访问。

## 具体问题与有限交付

旧启动链的 probe 先于 anchor 和 outer；collector 是另一条调用。
冻结 owner→supervisor、supervisor→target 两条请求边都可能在已提交、尚未取得
original 实例时失败。旧 finally 的 stop_original 仅处理已取得的 original。
这些来源不支持“没看到实例即没有待启动工作”或“一个目标树空即全部工作终结”。

本轮离线组件将固定来源、准确计划、配置与模型窗口关系纳入校验，
按计划列出 36 个域角色及两条内部请求边，其中五类 parent、两个 controller
和九个 ordinary 预期单元名可准确推导；12 条未建模请求边独立列出。
仍不能由固定材料派生的首次会话、
动态管理实例和完整收尾边界明确保留缺项。
有限模型只检查已提交、排队、绑定、停止请求与观察顺序的一致性；
它不创建实际 fence、不发 systemd 请求，也不生成可被执行入口接受的准入凭证。

`review_h07` 接受 config/manifest bytes、严格的 `dict[str, bytes]` 内容映射、
预期 D、固定 carrier/host attestation，以及可选历史 anchor 和模型 trace/window。
它重新调用既有来源验证并核对 config/plan/location，不接受调用者构造的
VerifiedSources token 或任意域清单。新接口额外要求本模块出现在声明的源码闭包；
原 v1 必需名单不变，实际 Git 字节与来源采用仍不由声明摘要自证。

模型的两条请求边分别保留状态、Job、实例、取消/停止应答、空树及双流 EOF。
模型窗口需要满足原 300 秒双钟结构并与 trace 摘要一致；这不证明调用者提供的
原点来自实际消费意图。`original_window_proven` 与所有实际准入/停止结论保持 false。
2 秒双钟差额沿用已有 host guard 的诊断限制，不证明跨机映射或整个窗口的速率/暂停边界。
没有支持的 fence/CLOSED 事件；模型一致性不会变成实际未来激活已被禁止。

## EA_INODE 漏拒修复

`q2_host_window_record._geometry` 已从 superblock offset `0x60` 读取
`s_feature_incompat`，但旧拒绝 mask 漏了 `INCOMPAT_EA_INODE=0x400`。
补丁只在原 mask 加入这个特征，不增加读取或扩大支持范围。

[Linux 官方 EA inode 文档](https://docs.kernel.org/filesystems/ext4/eainode.html)
说明大属性值可占用不出现在目录项中的 inode 与数据块；
[superblock 表](https://docs.kernel.org/filesystems/ext4/super.html)
固定此 bit 的 namespace 与数值。特征可用不等于原机已经产生这种分配。
正反例使用完整 1,024-byte 合成 superblock，分别改变三个 feature 字段，
确认只从 incompat 判定 EA_INODE，未把 compat/rocompat 的同值 bit 混为一谈。

这只排除一种目录成员之外的分配路径，不证明普通属性、创建配置、目录/extent
峰值或持久性。父目录旧基数 B 仍 UNPROVEN，首次净增长 G 仍非因果/峰值证明，
现有 12 KiB/indexed parent 仍超出窄 profile，完整账单和现场入口保持未准入。

## 验证与后续

本地 Python 3.12.14 / pytest 8.4.2，13 文件定向回归为
**391 PASS / 22 SKIP**，16.23 秒，exit 0。
新增 H07 83 项及 EA_INODE 1 项全部通过；EA_INODE 的四组 subTest 不另计用例。
22 项跳过是云端 root 下既有真实普通身份用例，未当作通过。
独立测试作者的 83 PASS 是最终回归的子集，不重复累计。

模型反例包含两条边独立未决、取消/停止后激活、一次无 Job 后才入队、已知 Job
更换/再现、同 unit 换实例、错误边/身份/字段、重复提交、缺流、越界/倒退/漂移双钟，
以及自报 CLOSED/FENCE 和调用者准入开关的拒绝。域清单使用既有严格 plan decode/bind；
公开正向组合测试明确隔离并 mock `offline_inputs`，不冒称完整来源验证。
阻断系统调用的测试也只证明这个隔离层没有现场操作，不证明动态模块加载没有文件访问。

独立复核另外从既有私有材料复用 48 份原件，共 5,686,734 bytes，逐件长度/摘要通过。
历史准确 config/manifest 原字节的 `offline_inputs` 通过；RAM 中仅增加新模块的声明摘要，
并同步重绑 manifest/config 摘要后，新 API 无 trace 及两条边已提交未绑定两种路径均通过，
没有 mock 完整来源验证。该 RAM 派生物仍声明历史 D，**不是准确新 D 的可执行交付包**，
不证明新 Git 来源采用、实际原窗口或现场资格。私有原件未修改，载荷未执行。

最终独立源码审查 must-fix 为空，四件字节与准确 D 匹配。
根审确认 18 项固定文件比较、8 个关键函数 AST、H C 祖先关系、Python 3.10 语法及
whitespace；独立审查另确认 record 除 `_geometry` 外 21 个顶层函数不变。
冻结 runtime 两文件直接对照原 `b49d3df3d1e76813faf08e59ab4975e25279c2fc` 字节相同。
旧交付包、源码闭包规则、deadline/field 拒绝入口均保留。

准确 D 的原生 [CI 36540605278](https://github.com/kongbu0621/infra-local-hand/actions/runs/36540605278)
已完成，整体 **SUCCESS，3/3 jobs 成功**。

| 原生 CI | 准确结果 |
| --- | --- |
| Linux | 源码 **2668 PASS / 51 SKIP**；强制 root collector **16 PASS / 0 SKIP**；wheel **94 checks / 292 commands PASS**；Plugin、smoke、重复 bootstrap smoke 与归档成功 |
| Windows | 源码 **636 PASS / 995 SKIP**；wheel **10 checks / 10 commands PASS**；服务场景检查与归档成功 |

Linux 相比前一准确 D 增加 84 项 PASS、SKIP 不变，新增 H07 83 项与 EA_INODE 1 项均通过。
Windows 新增 1 条 H07 整模块 Linux guard 的跳过，未当作通过。
准确 job/step、源码身份及完整日志长度/摘要见
[native-ci.json](evidence/q2-h07-model-20260929/native-ci.json)。
后继纯文档提交不冒领源码 D 的测试，历史失败 SHA 的红叉保留。

机器证据见 [verification.json](evidence/q2-h07-model-20260929/verification.json)、
[independent-review.json](evidence/q2-h07-model-20260929/independent-review.json) 和
[frozen-boundary-checks.json](evidence/q2-h07-model-20260929/frozen-boundary-checks.json)。

下一步是选择并证明一个在首次远端之前已生效、能终结所有待启动请求且覆盖完整
固定域的机制。现有材料没有证明这样的设施已存在。若必须新增准备动作、
设施或来源采用，应先将准确对象、时间语义、预算、终结和回执界面写成受影响范围的
三层文档 A，再按原 R 处理决定；本组件不能替代该工作。
同时继续闭合当前文件系统资格、完整费用和工具/环境来源。
本轮没有新的主机操作要求，不需要重复固定 11 项采集或权限维护。
