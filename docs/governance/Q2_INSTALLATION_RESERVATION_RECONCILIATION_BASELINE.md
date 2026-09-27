# Q2 安装未来义务对账：准确提案 A

2026-09-27。**PROPOSED / Gate OPEN / AWAITING OWNER**。
本文仅登记已经公开的准确文档基线和待决范围，不是 Owner B，也不是关闭 C。

| 身份 | 准确值 |
| --- | --- |
| Scope | `LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1` |
| Rule R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 三文档 A | `c65ff4e25ea6373aabf8db25d304ee7614b96eb5` |
| A tree | `76ef30d197c026c6acd796fced65f182889e67b0` |
| Owner B / 独立 C / 新实现 D | 尚未形成 |

R 的来源、采用关系、Owner 权威、规则完整性和变更要求沿用根 AGENTS.md。
本次已在线读取固定 R 并核对源码 SHA-256
`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；
未把私有 SOP 历史或完整正文复制到公开仓库。采集器所在环境此前 HTTP 404 的
事实另行保留，不能从云端可读推断它已经可读。

## 三文档完整性

以下路径均相对于仓库根，内容固定在 A；本登记不改变它们。

| 文档 | SHA-256 |
| --- | --- |
| [REQUIREMENTS.md](../a2-execution/q2-installation-reservation-reconciliation/REQUIREMENTS.md) | `3261d65ca264d07d1f3b0e174fbcd651ad68922bee3fd766341fcb7f62fcadc3` |
| [ARCHITECTURE.md](../a2-execution/q2-installation-reservation-reconciliation/ARCHITECTURE.md) | `4085374fd1544201edf33f4ce1cdaccb50ebc8944ea75f9d6078f8404885d739` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-installation-reservation-reconciliation/IMPLEMENTATION_PLAN.md) | `f6244c622906512c3727bb0038c8555363167a91bc24f576c73f0f2519aa7ed6` |

## 需要 Owner 一次决定的准确范围

1. 采用 A 指定的两份当前原件作为前瞻性的有限输入，并采用 609 项第二 staging
   树加 1 项旁置 intent 的准确比较基线。该 610 项索引 SHA-256 是
   `9b5b5ec8dd1516cb8807bf26f657c652079843a3669783db215a4f9c5dd5852e`。
   不补造历史整字节同一性，不把整个回传包当作通用历史权威。
2. 在 A 指定的五项 atime 偏差范围内，接受初次无保护 hash 探测后、inventory
   记录时点的准确元数据起点；永久保留偏差，不恢复时间戳，后续保护要求不变。
3. 只追加终止原 192 MiB/8192 inode 与第二独立 64 MiB/4096 inode 安装目标
   尚未消费的未来义务，逐维计算 `max(0,C−A)`。所有实际和其他承诺继续计费。
   在本 A/B/C 后完成实现、验证、交付，并仅在完整现场准入通过时继续原唯一批次。

新增 state 对账材料最多 1 MiB/16 inode，计入原 32 MiB/4096 inode 类别，不新增
总额度。两账本、全部计费树、真实 quota/父 cgroup/manager/account/namespace、
双次 boot/保全/费用检查均在原唯一 300 秒窗口内，准备总阶段仍不超过 140 秒。
完整 after 尚未取得，批准不会保证能发行；任何未知、漂移、超限或时间不足都停止。

已批准 startup A `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc` 与 C
`d4a925c883672fadc7d1b10a8dfe58df18b922cd` 及其三文档保持不变。runtime 仍为
`b49d3df3d1e76813faf08e59ab4975e25279c2fc`；没有第二次运行授权或窗口刷新。
新 startup 尚未发行，原授权未消费；两项旧 INCOMPLETE 和所有未验收结论保持。

## 证据与登记边界

[回传复核](../a2-execution/evidence/q2-readonly-return-20260927/README.md)及
[公开 manifest](../a2-execution/evidence/q2-readonly-return-20260927/manifest.json)
记录原包、12 个历史树、15 个旧文件、628 份重叠原件、双账本、五项偏差和容量边界。
私有归档提交 `14be72107572bc092c8b8aaf16abcdf5c99c7a87` 保留父提交和全部旧条目，
750 个索引条目、431 个去重对象通过重新 clone、Git 与逐字节摘要验证。

本 A 与登记只修改文档/证据索引，未生成对账实现、原型、测试脚手架或 READY
入口。旧 startup 三文档摘要、相对链接、公开隐私边界、Git 对象与发布 tree 已核对；
没有以旧 D 的测试通过冒充新实现验证。准确 Owner B 后应另作独立 C，再继续 D。
Owner 无需再寻找已取得的十项原始输入或重复进行一轮手工采集。
