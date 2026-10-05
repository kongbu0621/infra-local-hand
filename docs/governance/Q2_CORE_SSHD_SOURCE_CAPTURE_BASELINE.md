# sshd 单次只读取证提案基线

- Authority：Owner；状态 **OPEN / NOT APPROVED**。这是提案登记，不是 Owner B 或 CLOSED C。
- Scope：`LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1`，仅 P1–P3。
- 准确 A：`f2eb31deb3c52d69ccd2079fb7d88608d1a25a62`；tree `dec4cf6e6cd32010d203e8bde2dfde4d53a02104`。
- 源码基线：`46b08d9640ca19505fa02aa89d5d71d298536489`；不是新增采集范围的 D。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；[直接固定规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)已读取。
- 规则 SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`；Owner mandate、no exceptions 和原 change control 保持。

| 准确 A 的权威文档 | SHA-256 |
| --- | --- |
| [REQUIREMENTS.md](../a2-execution/q2-core-sshd-source-capture/REQUIREMENTS.md) | `e9fb702b74b86381d5e8ed47722d7203528444a137b58e86a7a192d3a1e58e08` |
| [ARCHITECTURE.md](../a2-execution/q2-core-sshd-source-capture/ARCHITECTURE.md) | `62b2a95421364055fa65b2899087ab116632190a5be378399501cbf88b629962` |
| [IMPLEMENTATION_PLAN.md](../a2-execution/q2-core-sshd-source-capture/IMPLEMENTATION_PLAN.md) | `8c280c33d7643dbc5daf9ed00d3058b1d471bc76685db9b18a7a5d2f9328ecc5` |

## 本轮交付与准确缺项

Owner 提供的 2026-10-05 17:41 +08 截图要求准备最小只读配置采集，并明确新采集须单独授权。
本轮只编写这三份提案、冻结 A 和登记 OPEN；没有新实现、测试、marker、SSH/carrier、安装、配置修改或业务运行。
未重搜同批私料，未重跑全量测试；三文件内容、五项既有管理源摘要、预算算术和文档差异已核对。

准确缺项仍是当前 guest 的真实 sshd 输入。此前已搜材料不包含原件，诊断虽已完成，实际现场拒绝行仍未知。
方案请求用一次只读采集补齐这个输入，不需要启动第四批 H01/Q4/H11；采集仍可能失败。成功采到的是当前快照，不会把它冒充 05b 历史原件。

## 最小请求及需接受的边界

- 沿用已绑定管理 anchor、同一账号/密钥/host key/回环 endpoint，仅新增固定 `lhqsshd-20261005a` 诊断请求。SSH 参数更严格且不修改 wrapper 或配置。
- 只采 `/etc/ssh/sshd_config`、固定 `.d` 目录一层清单及 `.conf`，最多 65 文件/1 MiB；不执行其内容，不运行 `sshd -T` 或业务。
- 本地 60s 窗口，reader 初始化后 20s alarm、5 CPU-s/128 MiB address-space；stdout 2 MiB、stderr 64 KiB；新增 capture 4 MiB/8 inode。
- 三旧 host 64 MiB/16 各全额保留；新旧当前可用条件合 196 MiB/56，非排他预留，更早历史仍 UNKNOWN，不保证证据完整回收。
- 这是固定 SSH 身份下的只读诊断信任，不另作业务运行时 attestation、旧 scope 静止核验或整棵进程树硬限额证明。
  SSH/sudo/PAM/审计和访问时间可能有副作用；故障时远端退出可仍 UNKNOWN，不能通过补连确认，也不宣称整机零写入。
- 原文只留受保护本地，公开结论仅含摘要、固定错误码及文件/行序号；不放宽核心文法、权限或生产 E3。

P1 写固定采集器和窄回归，P2 离线验证并冻结准确 D/参数，P3 仅在全部本地门通过后发一次请求并作离线解析。
三次旧核心机会均已消费，不能据本提案、旧批准或一次取证成功再发业务请求；所有 UNKNOWN、原件及承诺保留。
本范围没有批准前实现或现场动作，不要求 Owner 重复寻找已搜索范围内未发现的旧原件。

## 建议决定文字 尚未收到

> 按原 R，批准 A `f2eb31deb3c52d69ccd2079fb7d88608d1a25a62` 的 `LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1`，接受文档中的只读诊断信任、三旧 UNKNOWN 与完整承诺、非排他容量、管理副作用及远端退出可能 UNKNOWN 的边界，关闭该范围 Gate，执行 P1–P3；先独立 C 再实现。仅新增一次固定 `lhqsshd-20261005a` 配置采集，最多一次 marker 和一次 SSH 请求，失败不重试、不重连、不补采、不清理；原文只留本地，不执行业务，不改变 SSH 配置；支线暂停，生产 E3 限制保持。

收到上述准确决定后，才保存真实 B 并另作独立 C；不得将本登记称为已批准或提前创建 C。
如果 Owner 不接受这些诊断保证边界，P3 保持禁止；不以读操作名义绕过原 no-reconnect 规则。
