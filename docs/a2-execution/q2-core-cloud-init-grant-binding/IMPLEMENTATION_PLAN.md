# Local Hand 固定 cloud init 授权绑定实施方案

- Authority：Owner。状态：DRAFT / Gate OPEN / NOT APPROVED。
- 本方案仅 G1–G3；继承 [需求](REQUIREMENTS.md)全部固定输入、预算、时限及排除项。

## 批准顺序

先提交本三文档准确 A；Owner 基于原 R 明确批准唯一来源前提修订和 G1–G3。
准确 B 原文连同稳定 event/reference 保留于独立 bookkeeping-only CLOSED C；
然后实现 D，不能把 C 与代码或测试压成同一提交。不重新批准既有不受影响范围。

## G1 固定来源转换

修改 `tests/e3_host/q2_core_policy_basis.py` 的 raw source 验证，
用同一 users mapping 的唯一 name/sudo 结构投影代替完整 sudoers 行的 substring count。
保留原 whole-file pin、账号、grant、predicate、所有 source/identity 检查；不引入依赖或宽松 YAML fallback。
在 `q2_core_approved_inputs.py` 的独立 source-aware consumer 中核对同一关系。
`q2_core_delivery_freeze.py` 及必要 contract constants 加入本准确 A/B/C→D pin 与继承校验。
不改变固定 runtime 或 field protocol，也不修改 guest sudoers。

## G2 回归和准确私有包

测试覆盖实际形状的脱敏 fixture，以及错误账号、重复 users/name/sudo、跨 mapping 拼接、
额外 sudo 项、RunAsGroups 变化、锚点/alias/merge/tag、多行歧义、源摘要错误和 source 替换。
fixture 刻意替换 pin 只验证 parser 分支；真实 whole-file/source 比对单独保留。
独立 consumer 必须拒绝 builder 输出被篡改、摘要重算或 source-less 验证冒充 raw 关系。

运行定向、完整源码与独立 installed verifier，按准确 D 保存结果。
测试 wheel 不替换原现场 wheel。复核原三文件大小、全部 authority 文档/决定/祖先、保留历史输入与
当前源码关系；原 `core_20261003a` nonissuance source 必须使用固定摘要对应的历史
`9a87df50c51d863014723aa6c3c3584077429fd3` 文件，不以已更新同路径文件替代。

先完成 offline source/package-template review，再在同一原 900 秒窗口内取得 held local anchor/writer、
policy raw、ARG_MAX 和准确包，做两次独立 build/parse。原完整 approved-input aggregation 必须通过。
原 key relation、当前原件和静态 approved source 必须一致。所有门通过后才登记 exact release digest，
冻结实际 D/package；原静态/当前门任一失败均保留未发行与原因，不先放白名单。

## G3 原单次验收交接

只继续原未消费的条件 F1：先原唯一 marker，再原唯一 carrier，依次 H01 → Q4 → H11。
当前 marker 与所有 output 名的 absence 必须由原 live caller 验证，不由历史报告推断；
存在或部分 marker 均停止，不改名、不删除、不重试。只允许原新批次 create-only 安装，不重复历史安装。
H11 复用它自己的 origin 原 ledger/unit/grant/deadline，不从 Q4 借身份或启动第二次业务。

最终明确代码/包/实际请求和每个 case 的状态，H01 是否执行、结果和证据是否回收。
本修订不承诺实际 guest 准入必过；任何剩余 UNKNOWN 均停止并保留现场，production E3 与暂停支线不变。
