# Journal 诊断修复后替代预检 Owner 决定

本记录保留 Owner 对准确 A 的决定，并关闭
`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1` 的 DR1–DR2。它不是实现、现场预检、
sudo/SSH 调用、journal 扩容成功或核心验收的证明。

- Authority：当前本地 Codex 对话中的本仓库 Owner。
- Event：`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-CLOSURE-20261006-01`；登记日期
  2026-10-06，Asia/Shanghai。
- 稳定来源：本对话紧接[准确请求](Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_BASELINE.md)之后的
  Owner 回复；下文逐字保留，不补造消息时间。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本执行者已重新完整读取直接固定规则，
  SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
- A：`ef46ac169fd9084875cb5c5148a9c4985ace680c`，tree
  `c4390249aa98c2e99cb2f39ab1a25669b6eb63c2`，parent
  `aba18e33f79295f3df1964606e389297d1a8a26a`；三文档摘要由准确请求固定。
- 修复发布事实：`aba18e33f79295f3df1964606e389297d1a8a26a` 的 CI
  `37450280680` 已完成且 conclusion `success`；这是 DR1 输入事实，不是 DR2 准入或现场结果。

## 准确批准

> 按原 R，批准 A `ef46ac169fd9084875cb5c5148a9c4985ace680c` 的 `LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v1`，关闭 DR1–DR2 范围 Gate。诊断修复完成验证、发布并冻结准确候选后，允许沿用 `lhqjgrow-20261006a` 再替代一次已失败的预检窗口；先记录准确 B 和独立 C，再由承接 C 的准确候选执行。旧窗口维持消耗，原认证、全部检查、15s/900s/780s、预算及累计维护次数不变；不增加权限、helper、探测，不自动重试、补采或清理。全门通过后仅完成既有 journal 维护，不执行 H01/Q4/H11 或扩展支线。

## 独立关闭及限制

本提交是 bookkeeping-only CLOSED C：只登记决定和 Gate 状态，不含源码、测试、可执行原型、
依赖、系统配置、release digest 或现场调用。A 的三份文档及其历史 OPEN 标签保持原字节；
实施 D 必须为本 C 的后继且不得与 C squash。

既有诊断修复 `aba18e3` 在 A 之前依据原已关闭开发范围完成；本 C 不倒序追认它。
DR1 的新实施只可把准确 A/B/C 与既有修复、原输入、payload、argv 和最终候选绑定，完成受影响
验证并冻结交付。所有门通过前不得开始 DR2。

DR2 只允许沿用 `lhqjgrow-20261006a` 的一次明确替代预检窗口。旧窗口保持消耗；没有 marker
不退款。原真实本机前台终端认证、每检查点 15s、窗口 900s/780s、最多八个 writer 检查点、
一个 marker、两条维护 SSH，以及正常关机、完整备份、镜像增长、VM 启动和 ext4 增长各一次的
累计上限和全部资源预算不增加。失败即停，不重试、重连、补采、强杀、清理或自动回滚。

只在全部原预检门通过后，才可在同一窗口完成既有 journal 维护。不得增加权限、helper、sudo
探测、认证预热、askpass、整体提权或系统配置变更。不批准 H01/Q4/H11、新 boot 核心采用、
namespace/watchdog、production E3 或其它支线。
