# sshd locale 固定例外实现与离线验证

2026-10-05，Asia/Shanghai。Scope `LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-v1`，仅离线 G1–G3。
准确 A 为 `25e8d6cb015b619d8a55b6157a9454501b1c5f2e`；[Owner B](../governance/Q2_CORE_SSHD_LOCALE_GRAMMAR_OWNER_DECISION.md)
之后，独立 bookkeeping-only C `86c5779f306d24756a8be383846e55afc0708b8b` 先提交，再开始本实现。
A 的三份文档及其历史 OPEN 登记没有改动；没有新增现场授权或批次。

## G1 精确实现

唯一运行代码变化位于 `tests/e3_host/q2_core_delivery_dispatcher.py` 的 `_admit_sshd_source`。
仅主文件内一次、keyword 大小写不敏感、有序参数准确、只含空格/Tab 的固定 locale 声明可以通过原 glob 检查。
保留原片段及 LF 边界，防止 strip/splitlines 吞掉控制字符后误放行；其他旧输入的行号和解析行为保持。
第二条、drop-in、额外/变形参数、其他模式仍拒绝。通过首条后继续检查所有后续行、文件和 Include 总数。
错误仍只有固定码、序号、计数和完整原文摘要，没有配置原行或私有路径。

对独立 C 与当前源码的 AST 比较确认，其余顶层节点完全相同；没有改变有效策略、collector、policy basis、
受控环境、capture reader、runtime candidate/wheel/harness、核心发行 entry 或生产 broker。
发行 allowlist 仍为空；五项有效策略仍各自要求准确值且只能出现一次。

| 源文件 | 字节数或摘要 |
| --- | --- |
| dispatcher | 449522 / 524288 B；SHA-256 `8a597dcd8b4ba1cd63d7b8dfc6b8f4a562960faf47afa7190ff876357205f871` |
| `tests/test_e3_q2_core_admission.py` | SHA-256 `e363f9a6bedf84d2c132ea16bae35c9961102dfe4e18f426d0557bfe3572acc7` |

准确 D 由包含本实现和本检查点的 Git commit 定位；后续只补登记结果，不混淆实际验证源码。

## G2 窄回归及行为差分

最终窄回归命令：

```text
python -B -m pytest -q tests/test_e3_q2_core_admission.py tests/test_e3_q2_core_admission_cross_binding.py tests/test_e3_q2_core_policy_basis.py tests/test_e3_q2_core_delivery_entry.py -rs --tb=short
```

结果 **359 passed / 2 skipped / 4.12s**。原第一轮三个模块为 317 passed / 2 skipped，是较早子集，不另加计。
两项 skip 要求 root 的目录 O_NOATIME 与 root-owned executable 检查；请求真实宿主视图补验这两项后，
实际仍为 2 skipped / 0.17s，没有记 PASS、使用弱读 fallback 或借 guest 补测，也不据此判宿主不支持。

回归覆盖主文件单次正例、重复/drop-in、词序/大小写/额外词、所有非允许 ASCII 控制字节及 DEL 的多个位置、
非 LF 分隔、引号/扩展/编码/拼接、后续拒绝及脱敏 bootstrap 传递、闭合集合 Include 检查、
262144 B 主文件与 65 文件、解析无文件/进程效果，以及五个有效谓词分别缺失/重复/错误时的拒绝。
测试只用人工 fixture；没有把私有配置复制到测试或把模拟策略结果冒充现场验证。

额外在内存中比较 C 的旧真实函数与新真实函数，3088 个合成输入中：3079 个结果完全相同，
8 个只因批准的准确 locale 组合从拒绝转为接受，1 个重复声明仍拒绝但错误位置从首条后移到第二条。
首次差分断言错误地要求所有拒绝码逐字相同，在这个预期后移上失败；核对后修正差分检查的预期，未因此改运行代码。
这只是有界兼容证据，不是所有可能输入的形式证明。`git diff --check` 通过。

## G3 实现提交时的检查点

此检查点尚未执行对已保存真实快照的新版本解析，次数为 0；相关准确 D CI 也须在冻结后核对。
不运行历史双解析器或取证入口。之后仅用已绑定的完整三文件，在准确 D 下作一次最多 5s 的纯本地解析，
不修改输入，不新增 capture/marker，不调用 SSH 或现场 helper。失败或超时不自动重复。

业务任务没有执行，业务结果/证据没有新增回收；H01/Q4/H11 和有效 sshd 策略均未实测。
三旧历史 UNKNOWN、全部承诺与原件、已消费诊断均保持；支线暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。

## G3 冻结后的最终结果

准确 D 为 **`d0c8749e47647264c14c406cd85c8c68006689a0`**，直接父提交为上述独立 C。
解析前核对 HEAD、干净 tracked 工作树、D 源码字节与 dispatcher SHA-256，以及 A 三文档未变化。
既有 capture reader/runner 也保持原字节；没有采用另一个文法实现或历史双解析器流程。

[准确 D 的 CI run 37305140260](https://github.com/kongbu0621/infra-local-hand/actions/runs/37305140260)
已完成，API 确认 head SHA 为 D，**3/3 jobs SUCCESS**：变更分类、Linux、Windows。
两平台源码测试及独立 wheel 安装验证通过；平台不适用步骤仍为 skip，不记为执行通过。
这些 CI 安装在隔离 runner 中完成，不是现场安装、原 runtime candidate 的替换或业务验收。

CI 通过后，G3 仅稳定读取原固定 capture 的 `.stdout`，保留 O_NOATIME/no-follow，
核对读取前后元数据（含本地 atime）、7028 B 长度和固定 SHA-256
`7c22202275cc851bac0707c7a630a4b302d7d347de087b2705af2289ab4a5dcc`。
复用原 schema/hash validator 核对完整有序三文件及各自长度/摘要，不筛选、裁剪或改写任何配置。
输入细节和原件摘要沿用[准确 A](q2-core-sshd-locale-grammar/REQUIREMENTS.md)；原文没有复制入仓库。

只将准确 D 的 `_admit_sshd_source`、原文本检查及必要纯计算依赖装入独立本地解析进程。
调用次数 **1**，完整输入 **3 文件 / 3569 B**，耗时 **139.679 ms / 5s**，解析进程退出 **0**：

```json
{"state":"ACCEPTED","code":"SOURCE_GRAMMAR_ACCEPTED"}
```

因此，**这份已保存完整快照的源码文法兼容性已修复，离线 G1–G3 完成**。
没有第二次私有解析、更新旧 receipt、创建 marker、连接 SSH、采集、现场 helper、重装或清理。
输入检查和纯解析不执行业务；业务任务执行及业务结果/证据新增回收均为 **0**。

这不证明 guest 当前配置、有效 sshd 策略、登录前后环境安全、历史 05b 触发行或核心链通过。
实际 H01 正常链 → Q4 取消 → H11 原账本/原单元恢复仍未执行；下一次现场流程须另有准确独立批准，
并保留全部身份/容量/策略/停止检查。旧批次不重放，历史 UNKNOWN 不升级，全部承诺不退款。
本次没有发放新 package/release digest，原 candidate/wheel/harness、预算及时限未变；
支线暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。
