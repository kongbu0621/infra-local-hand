# Q2 旧生产者准入单次替代批次：离线实现复核

2026-10-02 +08:00。本轮按 Owner 对
`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1` 的准确决定完成 P1 离线实现与验证，
并形成 P2/P3 允许的不可执行部分合同原型。P4 合同/资格复核结论仍为
**BLOCKED**；没有连接 host/guest、没有 SSH、没有生成 `TASK.txt`、没有消费
`20261002a`，也没有发行或执行现场 ZIP。

## 批准链与实现身份

| 层级 | 准确记录 |
| --- | --- |
| R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| A | `68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`；[三份准确文档](q2-old-producer-admission-retry/REQUIREMENTS.md) |
| B | `LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-CLOSURE-20261002-01`；[Owner 决定](../governance/Q2_OLD_PRODUCER_ADMISSION_RETRY_OWNER_DECISION.md) |
| C | `179652cb9487163d83c004d358e4d4b49409694c`，独立 bookkeeping-only CLOSED 记录 |
| D | `4b71824a4660723d064969cbf0c39cd4325dd62a` |
| D tree | `1fe7a678ce857611b617ba2429a8298da2cc6141` |

Git 核验确认 D 的直接父提交就是 C，且 C 是 D 的祖先。产品提交
`1a900e4a38e9567655f21cbf3c3f17941de1a8d5` 仍是固定产品身份，不冒充本范围 D。
A 的 trusted-storage/no-same-UID-tamper 前提按 Owner 决定记为已接受的治理输入；
`technical_rollback_proof=false` 保持，不把治理接受写成技术证明。

## P1：两项窄实现

### 四字段解析采纳

公开实现只固定私有 repair ZIP、原 helper、修复 helper 与精确插入段的大小和
SHA-256，不提交、回显、导入、编译或执行私有 helper。组合校验实际得到：

- 原 helper：39,623 bytes，SHA-256
  `4014a80998469607f8a279a4fc7b7abbeff61e349657b7d8224429d142dfa8db`；
- 修复 helper：39,976 bytes，SHA-256
  `3e6521f6065a3bb61e12b0f2cdcbf1c7f2d40e138269bf85d386aeb2741ab21a`；
- 唯一变化：offset 28,558 的 353-byte 插入，SHA-256
  `0fc6d020b99346e159de5496b82f1c5dbd268bae179d1f7934545aaf4511c39e`；
- 28,558-byte 前缀与 11,065-byte 后缀逐字保持，最终状态
  `OFFLINE_REPAIR_ADOPTION_VERIFIED`。

解析模型保持原 `strip().split("\n\n")` 分段、仅含 `=` 的行、首次 `=` 分割和
后键覆盖语义；只为 `ExecStartPre`、`ExecStartPost`、`ExecStop`、`ExecStopPost`
对结果映射中的每个字段名执行 `mapping.setdefault(name, "")`（局部变量名不作为合同）。
其它属性不合成，非空 hook、关键字段缺失、重复/缺失
unit、非零命令、UTF-8 错误以及 stdout/stderr/timeout 超限均 fail closed。
archive-only API 只报告 `OFFLINE_REPAIR_ARCHIVE_PIN_VERIFIED`；只有同时固定原
helper 并证明精确插入的组合 API 才报告 adoption，避免把“包摘要匹配”写成“修复已采纳”。

### 两项固定内核视图 consumer

consumer 在任何 proc 内容读取前严格互绑 `MANIFEST.json`、`host-locator.json`
和 `host-context.json`，并要求调用者从外部提供 D/tree pin；manifest 自报不能
替代 Git/CI 证明。随后核验 real/effective/saved UID 与 GID 三元各自全等、非 root，
完整 groups 稳定排序且保留重复项，并在读取前、读取中、两读之间和读后重复核验。

双钟初始顺序固定为 BOOTTIME→MONOTONIC，后续 guard 固定为
MONOTONIC→BOOTTIME；150 秒 preparation、300 秒 outer、回退及 2 秒双钟偏差
任一不符即停止。consumer 源码只有两次字面固定 K reader 调用，顺序为 `boot`
和 `mountinfo`；同一份 mountinfo 用于两个 parent 的包含挂载定位。没有任意路径/PID、
fallback、`O_NOATIME`、subprocess、sudo、SSH、写入或持久化路径。

真实普通身份同场测试先对原 `/proc/sys/kernel/random/boot_id` 请求旧
`O_NOATIME` 路径并得到 errno 1（EPERM），随后两个固定 K reader 均成功。
这证明批准的窄读取边界，不证明原 PRO6000 的 namespace、boot 或现场资格。

## 验证结果

项目专属环境为 Python 3.12.14、pytest 8.4.2。

| 验证 | 准确结果 |
| --- | --- |
| 新增 parser/contract/consumer 定向测试 | **86 PASS** |
| K reader + consumer，umask 0002 | **61 PASS** |
| 本范围及 host-window/ordinary/parent 相关回归，umask 0002 | **478 PASS / 21 SKIP** |
| 标准全库，umask 0022、`TMPDIR=/tmp` | **3415 PASS / 89 SKIP / 2 FAIL** |
| 诊断全库，umask 0002、`TMPDIR=/tmp` | **3347 PASS / 89 SKIP / 70 FAIL** |

标准全库两项失败为既有、非本轮文件：

1. `ProtectedFiles.test_content_and_mode_drift_after_read_are_rejected`：实现返回
   `RECONCILIATION_CONTENT_CHANGED`，旧测试仍断言 `METADATA_CHANGED`；
2. `ResultReaderTests.test_same_inode_same_size_rewrite_and_name_replacement_during_read_are_rejected`：
   `same_inode` 子例未抛出 `JobError`。

umask 0002 的额外全库失败集中于既有夹具创建的组可写目录/文件被保护检查正确拒绝，
以及后续依赖用例；本轮 K 合成夹具已显式固定 0755/0644，并在同一 umask 下通过全部
相关回归。没有把全库失败隐藏或改记为 PASS，也没有越过本范围修复其它模块。

## P2/P3 不可执行部分原型

生成的新私有原型仅用于合同 fixture 和离线验证：

| 属性 | 准确值 |
| --- | --- |
| basename | `local-hand-old-producer-admission-retry-20261002a-PARTIAL-NON-EXECUTABLE-4b71824.zip` |
| bytes | 9,516 |
| SHA-256 | `fd83b6a2fd8eed3a8bb4b5372c12c100652d6d37a1529d52504f592e009ae1f7` |
| 外层属性 | regular、0600、UID/GID 1000/1000、nlink 1 |
| 成员 | 5 个平铺 0600 数据成员；无 `TASK.txt` |
| 验证状态 | `OFFLINE_PARTIAL_PROTOTYPE_VERIFIED` |

原型固定 `field_ready=false`、`allow_run=false`、`guest_executed=false`、
`future_package_contract_complete=false`、`p4_contract_qualified=false`。它明确带有
`P2_FUTURE_PACKAGE_CONTRACT_INCOMPLETE` blocker，不能被称作完整 P2/P4 合同，
也不能由 basename、ZIP 存在或测试通过推导为现场包。

私有固定输入仅以 basename、大小和摘要登记：原 corrected ZIP 为
`local-hand-system-manager-1a900e4-20261001e-corrected.zip`，3,887,651 bytes，
SHA-256 `5805dcd2a45f150f0e5b7062a17b46137d53e889e1ea160601d7c75fb529e886`；
repair ZIP 为 `local-hand-system-manager-1a900e4-old-producer-parser-fix-20261002.zip`，
12,864 bytes，SHA-256
`2ddb55db15f73738116377de6fb8fa8fba9c5cc2cf23f1f59e2dc112ce63be70`。
两者均实测为 0600、UID/GID 1000/1000、nlink 1。仓库未记录它们的本机绝对路径，
也未收录私有成员字节。

## P4 合同/资格结论

下列硬门继续存在，故 P4 为 **BLOCKED**：

- `P2_FUTURE_PACKAGE_CONTRACT_INCOMPLETE`；
- H07 全运行期 rate/pause 与独立远端 stop 未证明；
- consumption parent 的文件系统、峰值与持久性未证明；
- evidence parent 的文件系统、证据上限、峰值与持久性未证明；
- 原 host 终端与 proc/PID namespace 对齐仍为
  `EXTERNAL_ASSUMPTION_NOT_PROVEN`；
- 独立稳定 P4 event/ref 未发行，可执行包、`TASK.txt`、现场执行和重试均未授权。

因此本轮完成的是准确 D、P1 隔离验证和 P2/P3 不可执行部分原型；没有完成
完整 future-package 合同，也没有通过 P4 资格。后续若要进入现场，必须先以准确受影响
批准链补齐合同与全部硬门，再由 Owner 另发逐项绑定准确 A/C/D、包、evidence 上限和
once/no-retry 条款的稳定 P4 event。当前 B、D、测试结果或本原型均不能替代该事件。

机器可读摘要见
[validation.json](evidence/q2-old-producer-admission-retry-20261002/validation.json)。
