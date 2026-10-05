# sshd locale 参数准入修订提案基线

- Authority：Owner；状态 **OPEN / NOT APPROVED**。本记录不是 Owner B 或 CLOSED C。
- Scope：`LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-v1`，仅离线 G1–G3。
- 准确 A：`25e8d6cb015b619d8a55b6157a9454501b1c5f2e`；tree `3fe2510fd8ba012fe7a733300e1c3d8afdfca9bd`。
- 原源码/记录基线：`921c5120824093ad7385c191c6a6a71a43bd9cc4`；尚无本新范围 D。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；[直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)本轮已完整读取。
- 原规则 SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；Owner mandate、no exceptions 和 change control 保持。

| 准确 A 的权威文档 | SHA-256 |
| --- | --- |
| [REQUIREMENTS.md](../a2-execution/q2-core-sshd-locale-grammar/REQUIREMENTS.md) | `228983fc431418a74a4813f5e27a7f99c0993c1ba0199f15d721f2868c7ebc7d` |
| [ARCHITECTURE.md](../a2-execution/q2-core-sshd-locale-grammar/ARCHITECTURE.md) | `0c003aae0578064e72486c44c517fcd55b97701a1d7de1b826f22802703a2eab` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-sshd-locale-grammar/IMPLEMENTATION_PLAN.md) | `fc23b1ed7a6be70f438bdd3c07fbd7534c615626a7a0abfd862ab9239cfeb4d6` |

## 已完成的输入确认

2026-10-05 的 Owner 截图要求查看已保存原件、判断真实指令和触发字符；若改变批准文法，先列准确变更。
本轮仅离线读取固定私有 stdout，验证原摘要、schema 和三文件关系，并作脱敏字符分类。
第一次本地检查误把已解码 dict 传给要求 bytes 的现有 validator，返回 `RESULT_SIZE`；
修正调用参数后验证通过。没有改 validator 或原件，该调用错误不是现场采集失败，也没有新增连接。
未重放已消费的一次历史双解析器流程，未重跑本地全量测试。

已确认第 1 文件第 121 行是 AcceptEnv 的 locale 二元参数，星号触发旧 GLOB 拒绝。
完整三文件字符检查没有发现除固定 Include 之外的其它活跃通配符行；这不是新文法已通过的证据。
配置原文及私有路径未公开，原证据索引和消费状态仍见[单次采集记录](../a2-execution/Q2_CORE_SSHD_SOURCE_CAPTURE_REVIEW_20261005.md)。

dispatcher SHA-256 仍为 `10839026bd841024ab9e3be35793a0d779cba1e1d6794f0dd1c41434e1868078`。
本轮没有运行代码/测试源码变更，没有新 marker、SSH/carrier、采集、helper 或业务执行。
已检查文档边界、链接、摘要与 `git diff --check`；未把文档准备或既有 CI 记作修复验证。

## 最小待决范围

原合同明确拒绝此 glob，拟只对主文件中最多一次、准确有序参数 `LANG` 和 `LC_*` 的声明增加例外。
仅空格/Tab、keyword 大小写不敏感、参数大小写敏感；其它位置、重复、额外词、模式和控制字符仍拒绝。
这是固定 token 例外，不是通用 AcceptEnv 模式支持；不改变五项有效策略、Include/Match/引号规则或 SSH 配置。
接受该声明也不是对会话环境无影响的保证。全部其它数值预算、时限、candidate/wheel/harness、历史 UNKNOWN 和完整承诺保持。

G1 只改原源码准入函数；G2 合成窄回归；G3 准确冻结 D 后，在本地对原完整三文件作一次最多 5s 的新版本解析。
不启用核心发行，不新增现场批次。原三个核心机会和一次诊断机会均已消费，不能重试、重连、补采或清理。
没有批准前实现，截图和本提案不能作为新 B。获得准确决定后才独立登记 C。

## 建议决定文字 尚未收到

> 按原 R，批准 A `25e8d6cb015b619d8a55b6157a9454501b1c5f2e` 的 `LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-v1`，接受仅主文件一次固定 locale 参数组合的文法例外及其环境保证边界，关闭该范围 Gate，执行离线 G1–G3；先独立 C 再实现。允许一次已保存完整三文件的新版本本地解析，不新增现场请求、marker、采集或批次，不重试、不重连、不清理；其它预算、时限、历史 UNKNOWN 和承诺保持，支线暂停，生产 E3 限制保持。
