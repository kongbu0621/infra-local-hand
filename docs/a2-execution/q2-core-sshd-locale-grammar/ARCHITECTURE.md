# sshd locale 参数准入修订架构

Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-v1`，仅 G1–G3；服从[需求](REQUIREMENTS.md)，原 R 不变。

## 修订位置与责任

consumer 仍是核心 dispatcher 的既有 policy admission。唯一行为变化位于
`tests/e3_host/q2_core_delivery_dispatcher.py` 的 `_admit_sshd_source`：
在原文本、参数、keyword、Match 和固定 Include 检查之后，对非 Include 行实施通配符判断时，
识别需求定义的主文件 locale 特例。其它路径和检查保持原顺序，不绕过后续文件或 closure-wide Include 计数。

输入仍是完整有序 path→raw bytes 映射，输出仍是无返回值的接受或原 `DispatchError`。
局部状态最多增加当前 closure 内特例出现次数；每次调用独立，不持久化、不读外部环境或配置。
只比较固定 keyword、位置、token、空白形式和次数，不产生路径展开、子进程或额外文件读取。
不在 collector、privileged reader 或 host capture 中去掉配置行，也不建立第二套替代解析器。

其它带 glob 的行仍走固定 `GLOB` 拒绝，包括该声明的位置、次数或参数不合条件的情况。
原诊断机制继续计算完整未修改文件的摘要和既有行号；不显示被拒绝的参数值。
原 `.splitlines()` 对既有输入和诊断行号的行为不变；新例外自身的空白检查只接受空格/Tab，不藉此重构整个 lexer。
新例外必须核对去除 strip/分隔符之前的原始片段，来自单个 LF 物理行（末行可无 LF）；
不得因为 splitlines/strip 已吞掉 VT、FF 或其它控制分隔符而误接受。其它旧行不借此改变词法行为。

## 信任和保证

这只是源码文法的窄兼容性例外，不证明该环境变量配置在所有会话中无风险。
不得将 AcceptEnv 当成控制文件 Include、文件系统 glob 或脚本执行；也不得因它是合法 OpenSSH 语法就接受全部环境模式。
未来核心流程仍应独立检查已固定的五项 sshd 有效策略及所有 sudo/key/rc 条件。
保留既有受控 C locale、固定环境以及 post-entry 信任边界，不新增系统配置或登录前安全保证。

policy basis 的 `sshd-fixed-closure-v1` 描述读取范围，`sshd-T-c-v1` 描述五项有效策略；两者及其参数不变。
原合同把源码文法版本绑定在 package 的准确 dispatcher D blob 中；本修订同样用准确新 D 和源码 SHA-256
区分旧拒绝与新例外，不静默改用旧发行 digest，不发放新 package 或解除空发行 allowlist。
旧 runtime candidate/wheel/harness 不被本地测试 wheel 或新 dispatcher 提交替代。

## 离线证据路径

本地执行者复用已保存私有 capture 的稳定读取、schema/hash 验证，取出全部三个原文件的有序 bytes，
一次性传入已冻结 D 的真实 `_admit_sshd_source`。不复制原文到仓库 fixture，不导入配置、不调用整个现场 dispatcher。
读入只限原固定 capture，O_NOATIME/no-follow、文件上限与 SHA pin 保持；不扫描旧材料或重新取得 guest 输入。
在独立本地进程中限时最多 5s，只运行准确 D 的已有纯解析函数及其必要纯计算依赖，
不调用 `analyze_snapshot` 的历史双版本流程。公开输出仅含 D、输入摘要、文件数、成功或固定脱敏错误码。

数据原件与传输 receipt 保持原位不变，新的脱敏验证结果写仓库 review，不新增现场 capture、账本或消费身份。
即使本地解析接受，证据也只说明这份保存快照符合新源码文法；不证明 guest 当前状态、有效策略、业务任务或历史 05b。

## 取舍及停止条件

采用固定参数组合，是因为真实已保存输入足以确定这一最小需求。
不采用通用 `AcceptEnv` glob 支持：它会引入任意变量名、模式及额外环境风险，超出本次必要范围。
不采用修改 guest 配置或过滤原行：前者未授权，后者会破坏证据完整性并隐藏拒绝。
不采用注释 whole-file hash 白名单替代解析：摘要只绑定证据，不能替代其它安全检查。

预算不新增远端资源；dispatcher 仍限 524288 B，无新现场模块、依赖、schema、migration 或持久状态。
失败保持 fail-closed。撤回此例外可恢复原源码拒绝行为，不需要迁移或现场动作；不得删除新旧验证失败证据。
若后续完整输入出现另一种文法/信任冲突，报告准确条件，不将本例外扩成宽松通用 parser。
