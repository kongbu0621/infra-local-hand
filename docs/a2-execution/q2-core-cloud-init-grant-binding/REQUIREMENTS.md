# Local Hand 固定 cloud init 授权绑定修订需求

- Authority：Owner。状态：DRAFT / Gate OPEN / NOT APPROVED。
- Scope：`LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-v1`，仅 G1–G3。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，原直接来源与完整性规则不变。
- 与本目录 [架构](ARCHITECTURE.md) 和 [实施方案](IMPLEMENTATION_PLAN.md)共同构成准确 A；
  提交后由独立 baseline 登记引用。本文不是 Owner B 或 CLOSED C。

## 已验证冲突与目标

只解除现有核心验收包的一个静态输入冲突，不增加功能或现场次数。
[本地复核](../Q2_CORE_PRIVATE_PACKAGE_REVIEW_20261005.md)确认：准确源码
`e2a40bd4b0e0b17ebe2a2ad3f533bdace318cc05` 已通过 CI，但固定 cloud-init 原件的
SHA-256 `5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523`
包含同一 users mapping 中的 `name: q1admin` 和 `sudo: ["ALL=(ALL) NOPASSWD:ALL"]`，
不包含完整字面行 `q1admin ALL=(ALL) NOPASSWD:ALL`。

原输入绑定 A `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c` 的需求 §3.2 与实现
都要求后一完整字面行；真实输入在 `CORE_POLICY_BASIS_SOURCE_GRANT` 被拒绝。
原始 source hash、账号与 sudo 权限未发生变化；错误在于把 cloud-init 声明误当 sudoers 行。
不能仅删除 count 检查、伪造 raw、改 guest sudoers 或把当前已是 root 当作证明。

## 唯一拟修订语义

在保持上述**整个原件摘要不变**的前提下，仅承认以下确定转换：
固定 cloud-init 的唯一 `users` 序列项中，`name` 标量恰为 `q1admin`，同一 mapping 的
`sudo` 值恰为一个字符串的 flow sequence `["ALL=(ALL) NOPASSWD:ALL"]`。
将这两个相邻层级字段组合为唯一规范 grant `q1admin ALL=(ALL) NOPASSWD:ALL`。
这里的唯一性按该固定原件中的账号 mapping 和 sudo 声明核验，不从两个无关文本位置拼接。

只接受原件实际使用的有界 ASCII、空格缩进、单行字段形式；拒绝重复 users/name/sudo、
不同账号、额外用户或 sudo 值、YAML anchor/alias/tag/merge、多行标量或无法确定所属 mapping 的输入。
不新增通用 YAML parser 或依赖；不接受“等价但摘要不同”的其它配置。
whole-file pin 与结构检查都必须通过；测试替换 pin 的合成源不成为现场来源。

明确 supersede 原 A §3.2 的“cloud-config 中唯一完整字面 sudoers 行”前提，以及 §3.2
固定 sudo predicate 参数对该行的原文计数解释。保留 wire 字段名和值：
`cloud_config_literal` 仍是上述规范 grant，`cloud_config_literal_count` 仍是整数 1，
但分别表示**从固定同一 mapping 导出的规范 grant**及其唯一来源计数，不再声称原文件含此完整行。
原 A/B/C 与历史文件字节不改，不将修订倒签为旧事实。

其余 current held sudoers closure、同一 carrier 内唯一 `sudo -n -ll -U q1admin`、
RunAsUsers `[ALL]`、RunAsGroups `[]`、Host `ALL`、NOPASSWD、命令 `ALL`、
program/account/HELLO 和所有 identity/digest 校验全部保留。
静态归一化只产生预期值，不证明 guest 当前权限；未知仍停止。

## 固定范围和不变边界

G1 是上述固定来源转换与独立验证；G2 是失败回归和准确私有包校验；G3 是原条件单次 F1 的交接。
不是另开 F1，不授权重新创建已消费对象。实现 D 必须继承本范围独立 C 和全部原 C。
冻结 runtime candidate 仍为 `4b6e4a7c403362358192086b88679e1326dcb2e1`，
tree `4d4349580c9f4b67cc26f601126849c2bc8d76a4`；wheel SHA-256 仍为
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`；
projection SHA-256 仍为 `55f555fc225edca943b8c86cee8119c4878f5ec1e9503a084ba7a560cf2c991d`。
最终 delivery/harness D 随本次修复重新冻结，不替换该 runtime/wheel。

完成调整 A `851a1afe4e55196212aa6913e81e0722deed1032` 已接受的保证保持：
guest 应用/观察总账 180 MiB/13440；逻辑 admission 276 MiB/16512 及逐设备保守预留；
2090 CPU-s、peak 2624 MiB/1160 pids、input 32 MiB/output 60 MiB、host capture 64 MiB/16 inodes。
900/800/750 秒外层时限及原所有子时限不变。三份 field 源码上限 8192/49152/524288 B 不变；
package v3、HELLO/BIND/marker、approved-input v1、remote-result v2、82 output members 和六 host 文件不变。
不增加 wire 字段、权限、源文件、对象、连接或系统配置。

原一次 O_EXCL marker / 一次 carrier request、不重连不重试及
H01 semantic PASS → Q4 semantic PASS → H11 的顺序保留。H11 只恢复自己的原 ledger/unit/grant/deadline，
不重启业务、不延长 deadline、不读业务结果补统计。所有原 release 和 live admission 门仍必要。
namespace/watchdog 暂停；production `E3_SUPERVISION_UNVERIFIED`、E4–E6、NAS、生产切换均不开放。

## 完成标准和停止条件

真实固定 cloud-init 可与规范 grant 建立唯一可复核关系；错误结构即使测试重算 pin 仍拒绝。
准确批准输入、两个 package builder/parser、全部原源关系与授权链核验通过后，才可登记 release digest。
任何门失败保留 NOT_ISSUED 或实际已消费失败状态，不把 UNKNOWN、mock、CI 或包通过当真实任务成功。
若需更换源摘要、账号、sudo 权限、wire shape、预算或现场次数，停止并另按 R 决定，不使用本窄修订授权。
