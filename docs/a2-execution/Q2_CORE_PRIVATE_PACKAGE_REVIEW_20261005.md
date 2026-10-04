# 核心私有包复核与固定授权来源冲突

2026-10-05 +08:00。本机已从 `44b801365d68157a675422ff5ad612d1b3175249`
快进到 `e2a40bd4b0e0b17ebe2a2ad3f533bdace318cc05`，tree
`34c331870a909330d00407e1bde568822eb29c0e`。
本轮推进至真实私有 approved-input 聚合，发现固定 cloud-init 与批准字面前提不符。
**包未完成，release allowlist 仍空，未发 carrier、未创建 marker，未运行 H01/Q4/H11。**

## 已完成的实际核对

- 直接读取原 R。三个修订准确 A/B/C 文档、决定、tree 与 C→D 祖先核对通过。
- [准确 D 的 CI 37212666821](https://github.com/kongbu0621/infra-local-hand/actions/runs/37212666821)
  三个 jobs 均 completed/success；本机现有 core tests 为 **953 passed / 35 skipped / 17.18s**，
  未把 skip 或 CI 当现场通过。
- 从原 clean candidate checkout 复核 845 worktree、9 Git metadata、3 field、wheel 和 projection：
  **859 members / 100 derived directories / 17452254 logical member bytes**。
  runtime candidate `4b6e4a7c403362358192086b88679e1326dcb2e1` 及原 wheel/projection SHA 均匹配。
  dispatcher **412466 B**，SHA-256 `06f5e5b659967a5a8375d981fe6e58401bba65b29054df50be363501f98ce79f`。
- 使用既有受保护历史原件重算 locator carriers、原 42-file Git-pinned verifier 与 legacy frame、
  六份 horizon archives；原 12 trees、7 obligations、610-entry forward baseline 等严格核对通过。
  这些仍是历史来源，不是当前 guest 事实。
- 静态 source/template 检查之后，按 BOOTTIME-first 原 900 秒时限调用现有只读 local anchor verifier。
  固定 wrapper/start/cloud-init/public key/known_hosts、私钥与公钥关系、原本地依赖、writer/cwd/argv
  和完整 local-management binding 均通过；未执行 SSH wrapper。只调用本地 ssh-keygen 做已有 key relation。
  每次只读检查关闭其 held fd，不把已结束 caller 的窗口或 writer 借给后续执行。

这一步确认已有真实管理入口可供原流程继续，不对 guest 当前是否运行、PID 1、systemd、quota
或 marker absence 作未经观察的结论。本轮没有 probe、远程重连、安装、清理或系统配置变化。

## 保留的失败与直接原因

最初寻找历史 policy raw 时，普通 host-return archive 没有三份控制原文；随后从固定 R3 原件取得
public key/known_hosts，cloud-init 则在上述现有 local binding 中取得并核对原 pin。没有拿空值替代。

第一次聚合尝试取了最新同路径的 nonissuance 文档，被 `CORE_APPROVED_INPUTS_LATER_SOURCE_PIN` 拒绝。
实际合同固定的 core 文档原件在 `9a87df50c51d863014723aa6c3c3584077429fd3`，SHA-256
`e64f1be1287ac8bed5f582b01e179b66dd79ead0eb91e8ccf1c71d3ea0095da0`，已从历史 Git object 复核并改用。
这是本地审查输入选择错误；没有改合同 pin 或发行第二请求。

随后两次只读核对一致阻断于 **CORE_POLICY_BASIS_SOURCE_GRANT**：
whole-file SHA-256 `5b81deabefb7bc70aa6ee13b72053d65556fac1e400b5a37919ca1f90e4b6523`
通过的 cloud-init 使用同一 users mapping 的 `name: q1admin` 与
`sudo: ["ALL=(ALL) NOPASSWD:ALL"]`；完整 `q1admin ALL=(ALL) NOPASSWD:ALL` 原文字面计数为零。
当前 `q2_core_policy_basis.py` 第一个 source-grant 检查要求计数为一。
现有合成测试把完整 sudoers 行直接当 cloud-config，再替换 source pin，因此没有揭示这个原件形状冲突。

原绑定修订 A 的 REQUIREMENTS §3.2 也明确采用该完整字面前提及计数，不能仅改源码将其归一化，
也不能删除校验或改现场 sudo。依据 R，只重新打开这一来源转换范围；既有不受影响的核心批准保留。
精确最小提案是 [固定 cloud-init 授权绑定需求](q2-core-cloud-init-grant-binding/REQUIREMENTS.md)，
连同其架构和 G1–G3；本轮只形成文档，不实施该新转换或测试。

## 交付状态和剩余步骤

本轮没有完整 package SHA、两次准确包 build/parse PASS 或 release 批准；静态成员冻结不等于完整包。
真实任务执行 **0**，新业务结果与证据收回 **0**。原条件单次 F1 未由本轮消费；当前现场 marker
是否存在仍待原 live caller 检查，不能从本报告推断不存在。

后续仅需先批准准确来源转换 A、独立 C，再实现并验证转换，完成准确包和原 release checks，
条件满足后按原一次 H01→Q4→H11。修复这个 blocker 不保证后续所有现场门会通过。
原版本、权限、预算、时限、无重试规则、production E3 和 namespace/watchdog 暂停保持。
raw machine evidence、控制文件、私钥及临时审查脚本未进入公共仓库。
