# Q2 固定内核读取：原机部分观察回执

2026-09-28 00:40:51 +08 收到 Owner 新截图。可见报告已到
`final_local_recheck`，返回 `OBSERVED_PARTIAL`，原因是
`LOCAL_FACTS_ONLY_LATER_ADMISSION_UNPROVEN`，并已回到 Bash 提示符。
此前 `host_boot` 的权限阻断已越过；本地预检得到部分事实，后续联合准入仍未证明。

本记录继续采用原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、准确 A
`887b640b394f9983f37dfe97c58ba35aaa099359` 与独立 C
`f7f8b503470725ca1ba18d1cb8d8b39e09a15ea8`，属于已批准 K4 的现场结果记录。
实现仍为 D `e15c633adbdfbf1e29cb12b2410975fe4911458d`，未修改代码、交付包或批准边界。
先前[实现复核](Q2_KERNEL_FACT_READ_IMPLEMENTATION_REVIEW.md)保留其交付前时点。

## 原图与可见事实

原图 `image(20260927-164046).png`，3,337,723 bytes，SHA-256：
`d1ea317231a25ff3611885d9f4ea4887aa64724d20453b0d49d19f053d333234`。
原图只在私有材料保留，公开[观察索引](evidence/q2-kernel-field-20260928/screenshot-observations.json)
不含用户名、真实 host 路径、实际 boot 或内核原始内容。

| 截图可见字段 | 值与解释 |
| --- | --- |
| `status` / `stage` | `OBSERVED_PARTIAL` / `final_local_recheck` |
| `source_tree` | `c7c60ec47b742615dbae9f8cb230679f3a9c4997`，与准确 D tree 一致 |
| `offline_sources_verified` | `true`，报告声明离线来源校验通过 |
| `observed_unique_allocated_bytes` | `13,189,120`，限定观察范围的去重已分配字节 |
| `observed_unique_inodes` | `42`，报告中的去重 inode 数 |
| 树费用类别 / 分类已证明 | `UNPROVEN` / `false` |
| `native_audit_peak_bytes` | `null`，仍未知，不能填零 |
| `historical_identity_adopted` | `false`，当前观察没有自动采用为历史身份 |
| 本次消费 / 远端尝试 / wrapper 执行 | 三项均为 `false` |
| Q2、Q3 验收 / production supported | 均为 `false` |

截图前部没有展示，尚未收到完整原始 JSON。不能将图中 inode 的 uid 当作进程
euid，也不能独立确认未显示的 `implementation_commit`、完整批准声明、消费路径
状态和全部计时字段。截图不是完整 JSON 的摘要证明或独立现场鉴证。

## 与准确代码的核对

按 D 的 `tests/e3_host/q2_host_window_preflight.py`，上述成功返回分支在初始
boot 匹配旧 pin、五组固定树扫描、七份旧 pin 完整匹配、最后路径/marker/boot
及期限检查后才成立。这是**结合准确源码的条件推断**；缺失的 JSON 字段没有
被补写成已直接观察的事实。已有截图足以说明现场报告越过先前权限阻断，
完整回执核验仍待原文。

13,189,120 bytes 不是完整费用、全部历史未来承诺、原生审计峰值或全 host 清单；
不能用它判定 64 MiB 预算已通过。H07 首次远端截止、wrapper 来源与执行绑定、
文件系统持久资格及联合账单仍各自缺证。原实现复核登记的通用 CI 失败也未因此消失。

## 当前状态与下一步

K4 的现场执行已有截图佐证，**完整 JSON 接收与核验尚未完成**。Owner 从现有
终端向上滚动，复制本次完整 JSON（从最初 `{` 到最后 `}`）回传即可；无需重跑
预检或再次批准，也不要求原 host 新建输出文件。若需要整理成文件，可在另一台
工作机保存已复制的文本后上传，保留原内容。

收到后先核对 D/tree、第四条批准声明、完整 pin/树观察及计时范围，再用于后续
缺口判断。当前记录不消费批次、不发行 owner，不将部分观察升级为 Q2 完整验收。
