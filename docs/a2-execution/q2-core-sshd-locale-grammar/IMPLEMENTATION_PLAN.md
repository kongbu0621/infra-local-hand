# sshd locale 参数准入修订实施方案

Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-v1`，仅离线 G1–G3。
本方案落实[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)，不包含任何现场请求或新批次。

## 准确基线与开工顺序

现状基线 `921c5120824093ad7385c191c6a6a71a43bd9cc4` 已登记采集完成。
原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 已直接读取；source integrity、Owner-only authority、无例外规则保持。
先提交本三文档形成准确 A，另行登记 commit/tree/三文件摘要及 OPEN 范围。
只读输入确认和文档准备不构成 G1 实现或 Owner B；批准前不增加测试源码、修复代码或 executable prototype。
收到引用准确 R/A/scope 的真实 B 后保存原话，独立 bookkeeping-only CLOSED C；新 D 必须后继 C，不 squash。

## G1 实现唯一文法例外

只修改 dispatcher 的 `_admit_sshd_source` 及必要局部注释：
识别主文件、最多一次、keyword 大小写不敏感、参数顺序与大小写准确、仅空格/Tab 的固定 locale 二元组合。
所有不满足特例的 glob 保留拒绝，不改变输入、不跳过后续行/文件，不放宽 Match/Include/引号/扩展规则。
不改 `_admit_sshd_output`、policy basis、核心 entry/release、collector、capture reader、runtime wheel 或生产 broker。
使用原固定诊断通道，错误不输出原行。实现大小仍在 dispatcher 524288 B 内。

## G2 针对性验证

新增或调整 `tests/test_e3_q2_core_admission.py` 中的合成回归，不使用真实配置副本。
原固定 locale 组合的负向测试转为受约束正向测试，其它负向用例保持；至少覆盖：

- 主文件单次准确组合、大小写 keyword 和空格/Tab，完整 Include 与后续文件仍检查。
- 缺省、换序、重复或额外参数；单个 locale 模式、其它环境名/通配符、问号/方括号/否定模式仍拒绝。
- 相同声明在 drop-in 或第二次出现仍拒绝；其它指令的星号不能借特例放行。
- 引号/反斜杠/扩展、行尾注释、非 ASCII、CR/NUL、新特例控制空白、Match、非法 Include 仍拒绝。
- 第一处特例后出现另一拒绝时保留准确文件/行号，未跳过第 2/3 文件；摘要绑定完整原文且错误不泄露输入。
- 既有无 glob 成功输入不回归；五项有效策略缺失/重复/错误仍拒绝，语法通过不代替 helper predicate。
- 固定 closure 数量/体积边界和无现场调用检查仍成立；没有新发行 digest 或新批次。

最小回归命令针对 `tests/test_e3_q2_core_admission.py`、
`tests/test_e3_q2_core_admission_cross_binding.py` 和 `tests/test_e3_q2_core_policy_basis.py`。
按实际依赖影响补充现有相关测试，不为本修改重复无关全量本地矩阵。
记录真实通过/失败/skip 和环境限制，`git diff --check`、dispatcher 大小/摘要以及相关 CI 必须如实交付。
Windows 上 Linux-only 验证的 skip 不记通过；不以任何模拟结果宣称 guest 通过。

## G3 准确冻结与完整私有输入验证

G1/G2 完成后干净提交 D，核对独立 C 的祖先关系和源码字节摘要，相关 CI 失败未解决时不得宣称可交付修复。
只使用需求固定的已保存 capture，验证 stdout SHA、schema、三个原件的长度/摘要和有序映射。
对准确 D 的真实源码解析函数作 **一次**本地完整快照调用，最多 5s，捕获固定错误码，不运行历史双解析器或远端 helper。
该调用不得创建新 marker、更新原 receipt、复制私有配置到测试 fixture、修改输入或联系现场。
失败或超时如实结束本轮私有验证，不自动重复、不删证据；所有 unit 回归仍用独立合成数据。

交付新的准确 D、窄测试/CI、私有原件摘要引用和脱敏源码解析结果。
只有完整三文件真实保存输入通过时，才能称“这份快照的源码文法兼容性已修复”；
无法读取原件或仍被拒绝时明确 BLOCKED/REJECTED，不能以一行合成正例替代。
结果报告必须同时说明 H01/Q4/H11 未执行、有效 sshd 策略未实测、旧历史 UNKNOWN 未变化。

## 后续边界

本批准若取得，只允许这次离线文法修订与验证。原三次核心验收及诊断采集均已消费。
不生成下一批名称、marker 或 release；未来现场准入/正常链/取消/恢复需要另一个准确 Owner 决定。
原 candidate/wheel/harness、数值预算、时限及所有历史承诺保持；没有重试、重连、清理或系统配置授权。
如完整输入暴露其它合同变更，先报告最小差异并按原 R 处理，不边测试边扩大放行。
支线继续暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。
