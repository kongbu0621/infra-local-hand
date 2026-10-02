# Q2 FS4/FS6：创建属性与同步源码核对

2026-10-02 +08:00；仅对已持源码/批准文档作静态核对。
各行 source pin 均为 `b707f1b0a4755aa0b2b6455d53ea8eae641182cd`（简称 `b707f1b`），
不是在该次 CI 上观测原设备。record/io/offline 三个相关 blob 已逐 bytes 与当前工作树
比较相同；没有执行模块、host/设备读取、试写、源码/测试改动或新的来源采用。

表中“实组件”指旧 ordinary v2 确有相应 syscall 调用；当前 retry 的 consumer 仍是
只读 K 集成，不能自动取得这些组件的现场写盘资格。“合成”指纯收据/输入校验。

| 范围 | source pin、函数位置 | 实际调用、guard 与首错 | 能证明的边界及 UNKNOWN |
| --- | --- | --- | --- |
| held parent/祖先 | `b707f1b`：[io.HeldPath:71](../../tests/e3_host/q2_reconciliation_io.py#L71)、[verify:104](../../tests/e3_host/q2_reconciliation_io.py#L104) | 实组件：ancestor用`O_PATH`/no-follow directory fd，目标用`flags()`含O_NOATIME；构造/逐级open前及verify每层调用guard；fstat与no-follow name stat逐字段绑定。权限/O_NOATIME错误传播，无弱化fallback；保护/绑定首错`RECONCILIATION_UNPROTECTED_PATH`、`RECONCILIATION_METADATA_CHANGED`、`RECONCILIATION_PATH_CHANGED` | held identity/protection检查有源码；ancestor仅冻结device/inode/type-mode/UID/GID，leaf冻结完整metadata。不是同UID互斥或中途峰值证明；原设备读取能力仍UNKNOWN |
| 普通身份与时间guard | `b707f1b`：[record._current_operator:87](../../tests/e3_host/q2_host_window_record.py#L87)、[guard:400](../../tests/e3_host/q2_host_window_record.py#L400)、[_identity_guard:478](../../tests/e3_host/q2_host_window_record.py#L478) | 实组件：重复getresuid/getresgid/getgroups，完整排序groups与初始值相同；guard检查identity、原window不变及deadline，preparation_guard追加旧140s界。观测漂移首错`HOST_WINDOW_OPERATOR_CHANGED`/`HOST_WINDOW_ORIGIN_CHANGED`/`HOST_WINDOW_PREPARATION_EXPIRED` | 不读fsuid/fsgid/capabilities/user namespace，不排除采样间change-and-revert；不能把旧140s窗口代替当前retry150s合同 |
| access/default ACL | `b707f1b`：[record._ordinary_acl_absent:105](../../tests/e3_host/q2_host_window_record.py#L105) | 实组件：只对`system.posix_acl_access`与`system.posix_acl_default`逐项getxattr，调用前和ENODATA结果后各guard；只有ENODATA可通过，其它errno首错`HOST_WINDOW_ACL_UNPROVEN`，任何返回值即`HOST_WINDOW_ACL_PRESENT` | 检查包含default ACL，不枚举全部xattr。未读/未排除security.*、trusted.*、user.*或其它system.*；ENODATA不证明创建security钩子/属性块/隐式inode费用为零 |
| ACL期间祖先重新绑定 | `b707f1b`：[record._protected_chain_ordinary:117](../../tests/e3_host/q2_host_window_record.py#L117)、[_ordinary_chain_binding:137](../../tests/e3_host/q2_host_window_record.py#L137) | 实组件：经held ancestor fd打开`.`作metadata/ACL检查，不read/list目录；open前/后、ACL期间及读后guard；本层metadata前后相同，随后全部name↔fd重新绑定。漂移首错`HOST_WINDOW_ANCESTOR_CHANGED`，其余OSError传播 | ordinary ancestor ACL专用open不含O_NOATIME，权限来自原已批准的metadata-only边界，不扩成内容read例外。metadata/ACL稳定不证明全局未篡改/并发为零 |
| 新目录/空intent真实属性 | `b707f1b`：[record._created_file_check:500](../../tests/e3_host/q2_host_window_record.py#L500)、[_created_directory_check:521](../../tests/e3_host/q2_host_window_record.py#L521) | 实组件：payload前核验目录0700/nlink2和regular空文件0400/nlink1、准确普通UID/GID/device、name↔fd；guard、ACL检查后再fstat/name stat并复核目录。首错`HOST_WINDOW_DIRECTORY_IDENTITY`/`HOST_WINDOW_INTENT_IDENTITY`/`HOST_WINDOW_INTENT_REPLACED`/`HOST_WINDOW_INTENT_CHANGED` | 核验创建结果，不读取umask/LSM/default security/config或新增quotactl/allocator来源；不推导额外分配为零。旧_create只有open mode0400，没有fchmod；当前A新writer明确要求held-fd fchmod0400，尚未物化，不是旧合同重批理由 |
| 明确同步链与失败留存 | `b707f1b`：[record._create:576](../../tests/e3_host/q2_host_window_record.py#L576)、[consume:429](../../tests/e3_host/q2_host_window_record.py#L429) | 实组件：mkdir后fsync新目录→parent；完整单次write后fsync文件→新目录→parent，共5次，每次调用前preparation_guard；下一步骤/最终verify与guard继续查截止。短写抛`HOST_WINDOW_SHORT_WRITE`，fsync在调用处抛原OSError；consume异常分支只close fd、不删对象，但close若再次抛错，源码没有独立首错封存 | 五次具体fd覆盖与调用顺序成立；没有为每个fsync返回立即添加独立guard，不能误记“每syscall紧邻双侧guard”。首错在二次close故障下的完整留存未证明；未读flush/cache/storage-chain事实，未证明fsync内部allocation/日志费用/掉电耐久性或全程峰值 |
| 持有文件读回与名称复核 | `b707f1b`：[record._verify_files:655](../../tests/e3_host/q2_host_window_record.py#L655)、[io._read:140](../../tests/e3_host/q2_reconciliation_io.py#L140)、[record.verify:677](../../tests/e3_host/q2_host_window_record.py#L677) | 实组件：parent/boot guard、目录及文件完整metadata与no-follow名字相同、唯一成员/无ACL；同held fd lseek+read，每轮read前guard，读后fstat与长度检查；随后snapshot/budget再复核。首错`HOST_WINDOW_MEMBERS`/`HOST_WINDOW_INTENT_REPLACED`/`HOST_WINDOW_INTENT_CHANGED`/`RECONCILIATION_CONTENT_CHANGED`，读错误传播 | 这是旧intent的实际read机制，不能写成当前evidence的same-fd pread已实现。bytes/SHA/name绑定成立也不单独证明底层flush或反回滚；snapshot不是锁 |
| 隐式属性/metadata/allocator费用 | `b707f1b`：[record._geometry:227](../../tests/e3_host/q2_host_window_record.py#L227)、[_budget:640](../../tests/e3_host/q2_host_window_record.py#L640)、[io.snapshot:231](../../tests/e3_host/q2_reconciliation_io.py#L231) | 实组件：raw feature拒绝EA_INODE等既定mask；snapshot计可见对象st_blocks/inode；_budget核验首次端点M及parent非负净增G，首错`HOST_WINDOW_ACTUAL_LIMIT`。源码没有security/任意xattr/quota/allocator配置读取、listxattr、setxattr或移除属性操作 | EA_INODE拒绝仅关闭所列路径，不证明其余security/xattr/extent/quota/allocator/journal路径无成本；可见st_blocks不穷尽隐藏对象，中途/sync峰值与失败残留上界UNKNOWN。不得编造块界或把未读取配置默认为关闭 |
| 当前evidence同步/属性收据 | `b707f1b`：[offline.validate_evidence_write:248](../../tests/e3_host/q2_old_producer_admission_retry_offline.py#L248)、[WRITE_STEPS/WRITE_FAILURE_AT:45](../../tests/e3_host/q2_old_producer_admission_retry_offline.py#L45) | 合成：检查exclusive-open→fchmod0600→write→file/parent fsync→pread→name rebinding→metadata的固定step和首错位置；错误收据保留first_error、禁止cleanup/retry；失序/伪造报`OFFLINE_EVIDENCE_WRITE_ORDER`/`OFFLINE_EVIDENCE_WRITE_FAILURE` | 不调用这些syscall，返回host_file_created=false/field_ready=false。当前retry实际evidence writer、原设备属性/同步/峰值资格仍UNKNOWN，不能把caller成功receipt采用成实机证明 |

源码核对的三份 bytes/SHA-256：record 39,701 /
`aac66e2f9c9072ad1eb1059884f640c685d75f86241dd879438ccf6f999cd6c2`；io 15,968 /
`f950004072eb9574942a086f9a6380b02fbbdfc327729f6d0b6c28bdb97430f2`；offline 23,454 /
`fce60371ddfffbb9f9864f8ef559267f7412c2cd18efbe14d0f346a87cb440fb`。

同步首错后的二次 close 若抛错，会成为最终传播异常；Python 的异常 context 可关联
原错误，但没有本合同独立 typed `first_error` 封存或 close 首错后全部 FD 均完成处理的
证明。本轮没有运行该故障用例，不把这项静态限制写成已复现的机器失败。

已接受的storage/程序与操作者诚信治理前提仍严格限于当前批准A
`68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`：同一host boot内范围外管理者及同UID进程
不删除、替换或整体回滚受保护parent、消费目录、intent、evidence。依据为
[需求233–241的前提](q2-old-producer-admission-retry/REQUIREMENTS.md#L233)和
[架构229–236的边界](q2-old-producer-admission-retry/ARCHITECTURE.md#L229)，准确接受记录为
[Owner B](../governance/Q2_OLD_PRODUCER_ADMISSION_RETRY_OWNER_DECISION.md#L23)。它是Owner接受的
治理输入，不是0700/0400技术性反回滚、底层flush、LSM属性界或namespace来源诚信证明；
未知/观察冲突仍BLOCKED/UNKNOWN，不能重建或重试。

本轮完成的是FS4/FS6的准确静态调用/错误覆盖表。原机隐式属性/allocator费用、完整同步
峰值及设备/存储适用事实仍未证，`filesystems_qualified=false`、`field_ready=false`保持。
没有新的权威采用、依赖、配置、现场包、消费对象或guest连接；本件不代替
[完整FS工单](Q2_FS_QUALIFICATION_WORK_ORDER_20261002.md)中的qualification条件。
