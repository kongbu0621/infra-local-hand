# Journal 本机终端认证：准确方案与待决范围

2026-10-06，Asia/Shanghai。状态 **OPEN / NOT APPROVED**；没有 Owner B，没有 CLOSED C。
本次只准备解决当前认证卡点的文档，不执行 sudo、SSH、marker 或扩容。

## 准确基线及采用声明

- Gate rule source：`kongbu0621/engineering-sop`；原固定 R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 可读取来源：[固定直接规则](https://github.com/kongbu0621/engineering-sop/blob/10d2a5c827964989f41ca6e8eeac3d44de6d0f04/docs/workflow/program-repository-documentation-gate.md)。
- 既有源完整性 SHA-256：`c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- Adoption mandate / Decision authority：Owner；exceptions：none；不得自动升级、弱化或扩展。
- Scope：`LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-v1`，T1–T3；Gate **OPEN**，尚未授权此认证修订或新窗口。
- 准确 A：`2b236865dc0a89e475c4021cac44d7193f252f67`。
- A tree：`3150bd79d0f996c6ab7f07df0965848284ee5a9e`。
- A parent：`c62319400c58e8ce067f0df150f8eb9ad0046719`。
- Reopen：需求、认证/终端边界、原时间/预算、范围、R/A、采用或 Owner authority 有实质变化即重新审阅。

| A 的三文档 | SHA-256 |
| --- | --- |
| [需求](../a2-execution/q2-core-journal-terminal-auth/REQUIREMENTS.md) | `8dd30a7d57327bbbd161a3b113d62877d748701ad6727d56ba4ef55915b984d4` |
| [架构](../a2-execution/q2-core-journal-terminal-auth/ARCHITECTURE.md) | `4de1e4a22f4bcecf9864dbc200303856fdffd9ddae92486810d0c0b9fd6e5082` |
| [计划](../a2-execution/q2-core-journal-terminal-auth/IMPLEMENTATION_PLAN.md) | `dbdb079c5eb83c8651775059ad784e3f56fd82d2ff780e00f0c666ed6fa0cad6` |

## 为什么只有这处需要新决定

已核对的宿主读取 A `2b4448c7b89d1910840f7aee2ae2b781f970e179` 明确：
NOPASSWD 不可用则停止，禁止申请密码、认证保温和配置修改；只允许一次替代预检窗口。
截图报告该窗口已实际失败于 sudo 认证。旧批准不能自行解释成允许交互或再开窗口。
这与此前已授权的收紧一个输入文件权限、提交推送不同；那些事项不需再次申请批准。

本修订只让 Owner 在真实前台终端完成既有固定只读 sudo 调用的认证，并明确给一次新的原规格窗口。
不安装 helper、不改 sudoers、不整体提权；仍需本人已有相应 sudo 权限。不是无人值守方案。
每个实际检查点都可能需要再次认证；密码不进入 AI、参数、环境、输入文件或日志。
15s 包含认证，900s/780s 不变；延迟、拒绝、终端变化或后续检查失败仍停止，关机后的停机风险明确保留。
三文档已作独立设计审阅及相对链接/状态检查；没有代码变更或新的现场测试。

## 待 Owner 确认的准确文本

以下仅为请求，不是已经发生的决定：

> 按原 R，批准 A `2b236865dc0a89e475c4021cac44d7193f252f67` 的 `LH-Q2-CORE-JOURNAL-TERMINAL-AUTH-v1`，关闭 T1–T3 范围 Gate；允许本人在本机真实前台终端为固定只读 writer 直接完成 sudo 认证，并替代本次未创建 marker 的失败预检窗口一次。先独立 C 再实现，保留原检查、15s/900s/780s、预算和累计维护次数；不修改 sudoers、不安装 helper、不整体提权，不自动重试、清理或扩展支线。

只有取得准确 Owner B 后才登记独立 C、实施 T1、验证 T2；全门通过才进入一次 T3。
本修订不批准 H01/Q4/H11、新 boot 核心采用或 production E3。原维护主体不重新申请批准。

## 本地衔接

本地现场记录 `7fd8a1e` 在截图中已提交、未推送。本轮远端无法读取该提交，故没有补造全文或完整 SHA。
本地 Codex 可按既有授权先推送这份脱敏记录；本提案使用独立文档分支，避免覆盖该本地提交。
经 Owner 批准后，采用保留历史的集成方式，使准确 A 和既有现场记录均进入祖先链，再独立记录 C；
不得 squash 掉 A/C/D 的必要独立性，不重置/强推旧现场记录，不修改既有批准三文档。
继续暂停支线，只推进认证接入、原单次扩容和其后的核心验收准备。
