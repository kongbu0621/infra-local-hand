# sshd locale 参数准入修订需求

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-SSHD-LOCALE-GRAMMAR-v1`，仅离线 G1–G3；不包含现场请求。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；原 Owner mandate、完整性、无例外和 change control 不变。
- 本文、[架构](ARCHITECTURE.md)和[实施方案](IMPLEMENTATION_PLAN.md)组成待批准 A。准确 Owner B、独立 bookkeeping-only C 必须先于新实现 D。

## 已确认事实与核心目标

目标是解除核心准入对一个固定 locale 参数组合的文法拒绝，同时保持其余身份、安全和有效策略检查。
当前仓库基线为 `921c5120824093ad7385c191c6a6a71a43bd9cc4`；实际诊断采集 D 为
`bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891`。本提案不是又一次采集、业务验收或管理入口建设。

[单次采集记录](../Q2_CORE_SSHD_SOURCE_CAPTURE_REVIEW_20261005.md)已证明当前快照成功回收；
固定 `.stdout` 为 7028 B，SHA-256 为 `7c22202275cc851bac0707c7a630a4b302d7d347de087b2705af2289ab4a5dcc`。
2026-10-05 本轮仅在本地按此摘要稳定读取原件，复用现有 schema/hash validator；不调用取证 runner、双历史解析器或 SSH。
三份原配置共 3569 B；文件 1 为 3517 B，SHA-256
`64325541513d33ea1d2ccd19c77750d458e67e7967fd2e7ef81d92f0aa2ffe21`，文件 2/3 各 26 B，
SHA-256 均为 `474ef6932d6b998ec97b122a9d86af024b988d64c243f3caf01dd9e5ed41618e`。
这两个相同内容摘要不代替各自路径/实体身份；原快照仍完整保留。

本地脱敏分类确认文件 1 第 121 个既有解析器行是 `AcceptEnv`，参数语义为 locale 固定二元组合，
其中一个参数带末尾星号。全三份文件的非空非注释行分别为 7/1/1；除原允许的固定 Include 外，
这是唯一活跃通配符行。未发现其他活跃引号/扩展字符或 Match。
这里报告语义分类和摘要，不公开配置原行、注释、私有路径或其它参数值。
静态字符检查不是修改后完整解析通过，也不能证明有效 sshd 策略或 05b 历史触发行。

[OpenSSH 官方文档](https://man.openbsd.org/sshd_config.5#AcceptEnv)允许 AcceptEnv 中的星号和问号，
并警告环境变量可能影响受限会话。这是上游语义，不自动授权本仓库支持全部模式。
原批准 A `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c` 的
[需求](../q2-core-binding-finalization-amendment/REQUIREMENTS.md)保留 sshd glob 拒绝；
当前 `_admit_sshd_source` 和负向测试与此一致。因此这是**有证据支持的窄合同修订**，不是可以直接放宽的实现笔误。

## 唯一拟新增的文法

在所有现有检查仍成立的条件下，只增加以下一个例外：

- 只允许主文件 `/etc/ssh/sshd_config` 中最多一条新增通配符声明。
- keyword 按原大小写不敏感规则识别为 `AcceptEnv`；有序参数恰为 `LANG`、`LC_*`，参数大小写敏感。
  这些是拟批准的固定协议词，不是配置原行的公开副本。
- 该声明只允许 ASCII 空格/Tab 作首尾及词间空白，不接受其它控制字符、换行拼接、额外词或行尾注释。
- 不允许省略、交换、重复参数，也不允许单独 `LC_*`、其它星号模式、问号、方括号、否定模式或任意变量模式。
- 相同带通配符声明在 drop-in、第二次出现或任何其它指令中仍拒绝。原先无 glob 的合法输入行为保持，不新增对其它旧合法行的收紧。

这是数据 token 的准确比较，不作 glob 展开、变量求值、配置裁剪或通用 OpenSSH 文法解释。
不得为让测试通过删除/改写私有原行，或把其它指令中的通配符一起放行。
发生范围外拒绝时保留准确诊断并停止，不能在同一修改中继续扩张语法。

## 保持的安全和版本边界

固定 Include 路径、仅主文件出现一次、closure 顺序、65 文件/1 MiB、路径/owner/no-follow/no-atime/稳定性保护均不变。
active Match、引号、反斜杠、扩展、其它 glob、编码异常仍拒绝；源码诊断仅输出固定码、序号、计数和摘要。
`_admit_sshd_output` 的五项有效策略谓词、sudo/key/rc 检查、受控环境和持有 executable 身份不变。
不新增 `sshd -T` 调用，不运行任何现场 helper。将来有效策略验证仍必须由另外获批的现场流程完成，不能用本地文法通过替代。

接受这一 locale 声明不证明 SSH 登录前后环境无影响；既有 post-entry 治理前提和限制保留，
不把后续 `env -i` 描述为进入会话之前的完整保护，也不把文法白名单称为环境安全证明。
原 candidate/wheel/harness、package/schema/profile、数值预算、时限、历史账本与 UNKNOWN 均不改变。
文法版本沿用原合同的 **准确 D dispatcher Git blob 绑定**，没有运行时开关、用户可选模式或新依赖。

## 验证与完成标准

G1 在独立 C 后实现唯一例外；G2 用合成 fixture 验证例外和全部相邻拒绝边界；G3 冻结准确 D，
只对已保存完整三文件快照作一次新版本本地源码解析（最多 5s），输出脱敏结果和准确版本。
这是本新离线范围的验证，不重放已消费的取证流程或原双历史解析器对照。
若不通过，保留首个拒绝，不修改输入、不自动重复私有回放；后续处理按实际缺陷和 scope 另作判断。

必须提交窄测试的真实结果、skip/失败、准确 source digest、相关 CI 和完整私有输入的解析结果。
不重复无关全量本地矩阵，不把源码测试计数或文法接受记成 guest PASS。
本范围可以完成源码兼容性修订，但不能声称核心功能已可用。

## 明确不授权

不新增或重用 marker、SSH/carrier、采集、重连、清理、安装、系统/SSH 配置变更、业务执行或批次名称。
三旧核心请求及 `lhqsshd-20261005a` 均保持已消费，全部历史 UNKNOWN、原件和完整承诺保留，不退款。
没有第四次 H01/Q4/H11 权限；未来现场验收仍需准确独立批准。
支线继续暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。

Owner 本次需决定的只有这一固定 locale 文法例外及离线 G1–G3 范围；不是新的现场资源或请求授权。
