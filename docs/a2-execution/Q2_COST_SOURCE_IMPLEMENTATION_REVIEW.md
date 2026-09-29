# Q2 离线费用来源与覆盖主张复核组件

2026-09-29 +08。接续[父目录分配组件](Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)，
本轮在已有 CLOSED H1/H3/H4 内增加独立的纯输入审查接口。
它发现引用与覆盖主张中的矛盾，不产生可供现场入口采用的完整账单。

## 准确实现与范围

| 项目 | 准确值 |
| --- | --- |
| 初次实现 D1 | `7e8026858962828102a6e3403edb3e43b82c1cee` |
| D1 tree | `b36bbf901fb03a4151e6188b8b838b4ceb62834d` |
| 初次 Parent | `65047d64934468acfca8e4f94aebe99ea56e6f93` |
| 最终候选 D2 | `24b5536ccf98c081212c7a05a6a883863d6f96fc` |
| D2 tree | `25f5b1fb1c0de29f5fd73df96a9af4fe06e51320` |
| D2 Parent | 上述 D1；仅修正两个 pytest 用例名称 |

原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 的直接原件已复读，
SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
原 H A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37`、独立 C
`271c07cd16140aa5942dcf3fad468003c58b6b0e` 及批准三文档保持。

新增 [q2_cost_source_review.py](../../tests/e3_host/q2_cost_source_review.py) 与
[独立测试](../../tests/test_e3_q2_cost_source_review.py)。既有 bill/v2、record/writer、
bootstrap、生产入口、workflow 和冻结 runtime 不变。
这是既有离线来源／费用核对实现；不新增来源采用、现场读取、批次或监督设施。

## 输入与输出语义

`review_cost_sources(manifest_raw, sources)` 只接受 manifest bytes 和原件 bytes 映射。
先核对全部声明来源的字节数及 SHA，再严格解析 JSON 和 RFC 6901 字段引用。
不执行载荷、不沿输入路径读取文件；模块加载后不动态加载仓库 helper。
重复键、浮点数、伪装整数的 bool、未知字段、越界大小、错误摘要和无效引用均拒绝。

manifest schema 固定为 `local-hand-q2-cost-source-claims/v1`，根键恰为
`schema,sources,objects,obligations,relations`；列表中每类 ID 唯一。

| 条目 | 准确字段 |
| --- | --- |
| source | `id,sha256,bytes` |
| object | `id,source,metadata_pointer,machine_pointer,boot_pointer,path_pointer,phase_pointer,role_claim,category_claim,evidence` |
| obligation | `id,source,commitment_pointer,kind_claim,category_claim,evidence` |
| relation | `id,kind,object_ids,obligation_id,evidence` |
| evidence 引用 | `source,pointer` |

object 的五个 pointer 和 commitment_pointer 可为 null 表示未知；证据引用的 pointer
不可为 null，但其原字段值可以为 JSON null。metadata 只提取 `device,inode,blocks`，
它们可为 null；已知 device/inode 必须正整数，blocks 必须非负整数。
已知 commitment 必须是准确的 `{bytes,inodes}` 非负整数字段。
role_claim 为 ordinary／parent_baseline／marker_subtree／unknown；kind_claim 为
historical／marker／capture／audit／unknown；category_claim 为
installation／state／journal／capture／unknown。relation kind 仅 coverage／credit。
结构或资源错误抛出 `ValueError("COST_SOURCE_...")`，语义冲突保留在 diagnostics，
不会自动修正原件或变更主张。报告 schema 为 `local-hand-q2-cost-source-review/v1`。

对象 metadata 中的 device、inode、blocks 必须取自同一个原字段对象，
引用分配量仅为 `blocks × 512`。机器、boot、路径、完成阶段及角色／类别依据
分别保留；能解析引用并不证明这些字段对应同一观察。
before stat、失败回执或 caller 所写 SUCCESS 不会升级成已完成的真实观察。

按原件摘要形成的 `source_groups` **只是来源容器分组，不是观察时点**。
同一个 JSON 可以包含多个对象和不同时间；重新打包也不会产生同步快照。
所选字段的小计只是带前提的引用算术，不是 actual 账单、真实下界或已采用的类别总额。
未知量保留 null；有身份别名或路径冲突时不生成小计，也不跨原件相加为总账。

| 主张／冲突 | 输出处理 |
| --- | --- |
| 同机器、boot、device/inode 字段碰撞，或同路径不同身份 | 显式冲突；不静默去重，不据此证明同一实际对象或同刻状态 |
| 同对象或其身份别名重复抵扣，或跨原件重复使用 | 保留冲突；不应用抵扣 |
| 同义务反复声明抵扣 | 保留冲突；不释放承诺 |
| 父目录旧基数 B 被声明覆盖／抵扣 | 保持未证；不放宽现 bill/v2 对 parent/ancestor 的拒绝 |
| marker 原承诺 | 仅引用准确 65,536 bytes / 4 inode；不计算 G/future，不二次扣减 |
| 未知费用、缺少角色或类别证据 | 保持未知；不以路径、文件名或缺字段推断为零 |

关系只覆盖明确列出的 object ID，不隐含目录后代或整个 scan。
`CROSS_RECEIPT_*` 诊断仅指不同来源容器之间的字段碰撞，并不认证它们是真实回执。
全部 `coverage_proven`、`credit_applied`、`release_applied` 均 false。
结果只有 `CLAIMS_REVIEWED`，来源采用、观察完成、B、完整账单、FS、现场准入、
Q2、allow_consume 与 allow_run 均保持 false。
本接口不实现特定 K4/L 回执的完整观察验证器，不能用字段引用替代它。

资源界固定为 manifest 256 KiB、单来源 8 MiB、来源总量 16 MiB、32 个来源、
512 个对象、128 项义务、512 个关系、每项 8 个证据引用、JSON 深度 64、
每件 100,000 个节点、pointer 4,096 bytes/64 段、输出 2 MiB；
整数、乘法与小计均检查上界。调用者不能改变这些限制。
关系选中对象的总次数另限 2,048，诊断条目限 2,048；单个引用值的规范编码限
256 KiB，不同引用累计限 4 MiB。关系检查使用身份索引，不扫描全部既有关系对象。

## 验证

本地 Python 3.12.14 / pytest 8.4.2，初次 D1 的五文件定向回归 **223 PASS / 0 SKIP**，
7.55 秒、exit 0。包括新组件和已有 host billing、普通身份账单输入、parent allocation
输入及 reconciliation billing。新文件的独立 **78 PASS / 0 SKIP** 是其子集，不重复累计。
这些纯输入测试没有 Linux guard，新组件会同时进入原 Windows/Linux 测试流程。

反例覆盖错误摘要、JSON／pointer／数量边界、整数溢出、部分 stat 不升观察、
同容器异时字段、身份别名、路径冲突、重复抵扣、义务重用、未知费用及输入不变。
系统操作守卫在正常导入模块后禁止输入路径读取、动态导入和执行；
该验证不声称 Python 的正常模块加载无文件访问。

审查修复了来源容器被称作观察 epoch、实际 sources 字典遍历前未限数、
关系对象全量重复扫描三项问题。冻结前一次关联回归为 222 PASS / 1 FAIL：
membership 测试先触发诊断上限，随后修正合成数据来隔离被测上限，源码未为此放宽。
该次测试 bytes 未独立封存，失败日志／JUnit 摘要保留；上述最终本地结果绑定 D1。
最终独立源码审查 must-fix 为空，22 项固定文件比较通过。
批准文档、旧 bill/writer、准入入口、workflow 与冻结 runtime 字节保持。

另将已经保存的 K4（34,013 bytes）和 rerun3（32,439 bytes）传入新接口，
实际核对 13 个条目：父基数在两个来源中的引用，以及 M7/T4 的 11 个文件引用。
两个 source group 的身份关联均未证明，13 项身份保持不完整；两个原文 null 义务
保持未知，两个组小计均为 null。没有跨来源总账、承诺释放或 G 调整。
这次离线应用通过只证明引用关系按合同处理；未执行原件中的载荷或取得新现场事实。
原始路径、身份、claims 和完整输出保留私有，公开只有脱敏摘要。

D1 的原生 [CI 36546965469](https://github.com/kongbu0621/infra-local-hand/actions/runs/36546965469)
暴露 Windows 测试兼容性问题：巨大 bytes 参数被 pytest 自动展开为用例名，
设置 `PYTEST_CURRENT_TEST` 超出 Windows 32,767 字符上限；该用例的 setup／teardown
各出一个 ERROR，测试体未执行。Windows 为 **713 PASS / 995 SKIP / 2 ERROR**，
后续 wheel／服务检查未执行，不能称整个 D1 通过。
首次运行的 Linux 为 **2746 PASS / 51 SKIP**，root collector **16 PASS / 0 SKIP**，
wheel **94 checks / 292 commands PASS**，bootstrap smoke 成功；整体仍为 FAILURE，
2 个 job 成功、1 个失败。

D2 只为这两个参数加短 ID，原输入和断言全部保留；去掉新增 ID 后两版 AST 完全相同。
费用组件字节不变，独立补充审查 must-fix 为空，本地新文件重新 **78 PASS / 0 SKIP**，
0.59 秒。D1 的失败记录保留，D2 的准确原生结果单独登记。

准确 D2 的原生 [CI 36548011444](https://github.com/kongbu0621/infra-local-hand/actions/runs/36548011444)
已完成，整体 **SUCCESS，3/3 jobs 成功**。

| 原生 CI | 准确结果 |
| --- | --- |
| Linux | 源码 **2746 PASS / 51 SKIP**，416.57 秒；root collector **16 PASS / 0 SKIP**；wheel **94 checks / 292 commands PASS**；Plugin、重复 bootstrap smoke 与归档成功 |
| Windows | 源码 **714 PASS / 995 SKIP**，354.80 秒；wheel **10 checks / 10 commands PASS**；全部 Windows 系统场景检查与归档成功 |

两平台相对上一已成功源码 D `293cb51f` 均增加 78 项 PASS，SKIP 不变；
新费用来源用例没有被跳过。平台不适用步骤与既有 SKIP 不计为通过。
准确 job／step、checkout 身份、完整日志字节数和摘要，以及首次失败记录见
[native-ci.json](evidence/q2-cost-source-review-20260929/native-ci.json)。
后继纯文档提交不冒领源码 D2 的测试，历史失败 SHA 的红叉保留。

可核对的机器记录：
[verification.json](evidence/q2-cost-source-review-20260929/verification.json)、
[independent-review.json](evidence/q2-cost-source-review-20260929/independent-review.json)、
[frozen-boundary-checks.json](evidence/q2-cost-source-review-20260929/frozen-boundary-checks.json) 和
[retained-input-check.json](evidence/q2-cost-source-review-20260929/retained-input-check.json)。
开发测试与私有原件引用检查都不证明原机当前状态或完整 Q2。

## 剩余工作

[H07 路线审查](Q2_H07_MECHANISM_ROUTE_REVIEW.md)确认：现有直接 `--system`
路径不受旁挂 broker 强制约束；首次探测、未决请求与独立域停止仍需实际机制证明。
当前没有可据此接入冻结链的充分方案，也不请求对模糊设施的提前批准。

[FS 与费用来源合同](Q2_FS_BILLING_SOURCE_CONTRACT.md)将剩余来源拆为 FS1–FS6、
父基数／marker 池、原历史义务和原生审计范围。
下一步应对这些准确缺项形成有依据的最小方案，而不是重复已有 11 项采集。
当前完整账单、FS、实际 H07 与现场资格仍未通过；原 startup batch 仍 NOT ISSUED。
