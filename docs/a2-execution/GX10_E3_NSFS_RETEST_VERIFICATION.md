# GX10 nsfs 重测：原始证据独立核验

日期：2026-09-23。**两份实际收到的 ZIP 已独立核验；`nsfs` 解析缺陷在固定源码与本次 GX10 只读记录范围内验证通过。E3 整体验收仍未完成，readiness 保持 INCOMPLETE。**

本记录接续 [云端修复验证](E3_NSFS_REPAIR_VERIFICATION.md)。本轮读取的是上传的原始 ZIP 及外部 verification JSON，核验时未执行包内脚本、未连接目标宿主、未重跑产品测试或实机命令。以下结果来自归档原始 stdout、stderr、命令记录与固定 Git 对象的交叉核对。

## 1. 收到的文件与独立完整性检查

| 项目 | 首轮宿主盘点 | 修复后宿主重测 |
| --- | --- | --- |
| ZIP | `infra-local-hand-e3-host-inventory-20260923T102534Z-287f6b9-evidence.zip` | `infra-local-hand-e3-nsfs-gx10-retest-88b78b6-evidence-20260923.zip` |
| 大小 | 23,315 bytes | 25,927 bytes |
| ZIP 成员数（含 MANIFEST） | 19 | 21 |
| MANIFEST 索引的文件数 | 18 | 20 |
| 已核对的命令记录数 | 4 | 5 |
| 探针来源 | `287f6b92408ee43b7898acefba48eb226160e6fe` | `88b78b6ef908026b763f307c4d78ab3d0c0e6521` |
| 探针大小 | 30,716 bytes | 31,209 bytes |
| 原 probe stdout | 2,257 bytes | 2,753 bytes |
| 原 probe 退出码 / stderr | 0 / 0 bytes | 0 / 0 bytes |

首轮 ZIP SHA-256：`b818433cae0a4640c4420e47871029da0372575420f045e442936aaf0d3b9486`。
首轮 MANIFEST SHA-256：`50567c72c8922cffaa65f5bf9be629bdf09ebbd93ec8dc5597ecf05528ea3248`。

重测 ZIP SHA-256：`827d9adcf8ac682b7ede9944437a312be60ca1724eb73398cebbbcfc75788a08`。
重测 MANIFEST SHA-256：`65c61d5d5f017a7be8c25d29eb23838379ca6f4fa55705271b2cebf6dcc34ac6`。

重新计算的 ZIP / MANIFEST 摘要、字节数、成员数与已提供值及外部 verification JSON 一致；没有直接采用其中的 `verified=true` 作为结论。全部 40 个 ZIP 成员 CRC 通过，成员名唯一、相对且无符号链接；MANIFEST 精确覆盖其余 38 个文件，逐个大小和 SHA-256 全部匹配。9 组命令的两路输出均与记录摘要一致，时间与退出码内部一致，identity 文件与各自 MANIFEST 一致。

两份 `exact/probe_e3_host.py` 分别与其固定 Git blob 逐字节一致，报告内来源摘要也吻合。重测源码 tree 为 `be5e00c2e7b768b61cf34aa19b70d1cd1452e667`，probe blob 为 `a01f5354dfb6e160b8dc42acc1dbffc1697144f7`，probe SHA-256 为 `29ba728639a4674b53799f805abfe31e075f6260ce68f64e2410370210eae651`。

## 2. 前后结果与证据边界

| 观察 | 首轮 | 重测 |
| --- | --- | --- |
| `MOUNTINFO_FORMAT` | 存在 | 消失 |
| 宿主解析诊断 | 55 条记录中，5 条 nsfs 被旧解析器拒绝 | 55 条全部解析成功，5 条 nsfs 保留，类型均为 mnt |
| cgroup2 根绑定 | 未取得 | 实际 FD mount ID 与已解析 mount ID 一致，`filesystem_verified=true` |
| expected UID / 私有 slice、cgroup | 未提供 | 仍未提供 |
| readiness | INCOMPLETE | INCOMPLETE |
| 生产、业务、E3 三个字段 | 均为 false | 均为 false |

两份原始 probe JSON 的 host / boot / namespace / 观察身份字段一致；重测的解析诊断记录为 6,047 bytes 的 mountinfo、55 个记录、5 个 nsfs 和 1 个 cgroup2。重新从两份 JSON 计算的比较结果，与包内比较命令 stdout 完全一致。目标为 aarch64，记录的探针解释器为 Python 3.12.3；该现场执行不扩张为整套源码测试或安装态测试。

证据保存了解析命令及计数输出，**没有保存完整原始 mountinfo 字节**。因此本核验确认固定脚本的归档现场执行结果，不声称在云端重放了那 55 条原始记录；相同 boot 和计数也不证明两次完整挂载表逐字节相同。`observations.mounts` 仅保存显式 mount target 的结果；本次未传该参数，空列表不表示解析时过滤了 nsfs。

`delegation_sufficient=false`、`write_test_performed=false` 保留。根 cgroup 绑定通过不能证明专用账户的私有委派已经准备。原服务的两次只读快照字节相同，只证明两个采样点，不能推导全时段连续监控。首轮空导出文件仍保留，实际 probe 命令引用的是已匹配 Git 字节的 `exact/` 脚本。

## 3. 当前状态与下一步

本次 `nsfs` 兼容性修复已取得原始宿主证据并完成独立核验，无需为该问题重复无参数盘点。剩余两个盘点缺项为 `EXPECTED_UID_REQUIRED` 和 `PRIVATE_CGROUP_AND_SLICE_REQUIRED`；三个固定 blockers 仍是 `REAL_HARNESS_MISSING`、`QUOTA_PERMISSION_MODEL_UNVERIFIED`、`E3_SUPERVISION_UNVERIFIED`。

下一步分别推进：

1. **现场输入确认。** 在私有记录中确认拟用于隔离 E3 的专用非 root UID、准确 slice 与 cgroup、既有准备依据和与现役服务的隔离范围。当前登录身份及编辑器所在 cgroup 只作为观察事实，不能自动成为批准的测试配置。尚未准备就明确记 NOT_PREPARED；本轮不以创建账户、unit 或委派替代缺失事实。
2. **实现障碍复核。** 按 [E3 实现缺口](E3_IMPLEMENTATION_GAPS.md)解决原隔离模型下的 quota 查询、准确 errno 取证与真实三单元 harness。现场填表不解决权限模型冲突，不触发 quota syscall；改变信任或隔离边界的方案须遵守已有变更规则。
3. **有条件进入真实验收。** 准确实现和完整隔离输入齐备后，再按 [宿主验收准备](E3_HOST_ACCEPTANCE_RUNBOOK.md)冻结候选并运行相应场景；仅补齐盘点参数最多得到 OBSERVED_NOT_ACCEPTED，不是 E3 PASS。

本轮只追加脱敏证据结论，不改产品代码、测试、依赖、生产封堵或已批准 A 的三份文档。既有 R / A / B / C 与 E1–E3 范围保持；E4、E5/S2、E6 状态未改变。主机路径、账户、boot / namespace 标识、进程信息与完整原始日志继续私有保存。

## 4. 独立核验交付

私有核验包 `infra-local-hand-gx10-nsfs-audit-20260923.zip` 为 13,570 bytes、9 members（含 MANIFEST），ZIP CRC、唯一成员和逐成员字节均已复核。ZIP SHA-256 为 `bf63e033d73c563753a7819d4129b16afce04629d63ffe1b4ecc2edb697b7cc6`，MANIFEST SHA-256 为 `2fe682f95d27a198a431a9d0842244121318b731d8fc3ec1ff720cc2d6278cae`。

包内含本次离线核验脚本、实际核验命令／双流、独立 `verification.json`、范围核对，以及一次性 `GX10_E3_INPUT_CONFIRMATION.md`。其用途是交付核验记录和下一步事实确认任务；不重复复制两份原始宿主 ZIP，也不是一次新的 GX10 实测。
