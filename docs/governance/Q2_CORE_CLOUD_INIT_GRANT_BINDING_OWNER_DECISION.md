# 固定 cloud init 授权绑定 Owner 决定 B

- Decision Authority：Owner（本仓库 Owner 的当前对话用户）。
- Event：`LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-CLOSURE-20261005-01`。
- 登记日期：2026-10-05，Asia/Shanghai；事件 ID 定位决定，不伪造平台消息时间。
- 稳定来源：本仓库本地 Codex 对话中，紧接下列准确请求的 Owner 文字回复。
  原文保存在本 committed record，可由 Owner 核实，不以截图代替批准。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接读取，原完整性与采用规则保持。
- A：`018bdd7f09998290f536ab5a3726ccb4123dffa3`；tree `a444a2398766ee4cba7e4f674a326c3a18995098`。
- Scope：`LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-v1`，G1–G3 only；三文档摘要见
  [原 OPEN baseline](Q2_CORE_CLOUD_INIT_GRANT_BINDING_BASELINE.md)。

## 紧邻的准确请求

前一回复说明：已同步 `e2a40bd` 并将复核及提案推送到 `3f07b0a`；CI 3/3 成功，
本地 953 passed / 35 skipped。固定原件将账号和 sudo 规则分开声明，不能直接删除原字面检查。
准确包仍被阻断；真实任务尚未执行、结果未收回、该轮没有消费 marker/request。请求为：

> 按原 R，批准 A `018bdd7f09998290f536ab5a3726ccb4123dffa3` 的 `LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-v1`，接受固定 cloud-init 同一账号 mapping 到规范 sudo grant 的来源归一化，关闭该范围 Gate，执行 G1–G3；先独立 C 再实施。原版本、预算、时限及条件单次 F1 不变，支线暂停，生产 E3 限制保持。

## Owner 回复原文

> 按原 R，批准 A `018bdd7f09998290f536ab5a3726ccb4123dffa3` 的 `LH-Q2-CORE-CLOUD-INIT-GRANT-BINDING-v1`，接受固定 cloud-init 同一账号 mapping 到规范 sudo grant 的来源归一化，关闭该范围 Gate，执行 G1–G3；先独立 C 再实施。原版本、预算、时限及条件单次 F1 不变，支线暂停，生产 E3 限制保持。

## 独立关闭与执行边界

本 bookkeeping-only C 只保留 B 并更新 AGENTS Gate declaration；不修改 A 三文档或历史 OPEN
baseline 字节，不包含新源码、测试、配置、包或现场动作。后续 D 必须以本 C 和全部原 C 为祖先。

仅批准准确 A 定义的固定 whole-file pin 下同一 users/name/sudo mapping 到规范 grant 的转换，
及原两个机读字段的来源解释修正。原账号、sudo 权限、current held sudoers/helper/HELLO 身份检查
均不放宽；未知不推定成功。G1–G3 包括实施、验证、准确包审查与原条件单次 F1 交接。
这不是额外现场授权或立即发行许可，所有原 release/admission 门仍须通过。

原 runtime candidate/wheel/projection、对象、三文件结构、预算、时限、一次 marker/request、
不重连不重试和 H01→Q4→H11 顺序保持。H11 仅使用自己的原 ledger/unit/grant/deadline，
不重启业务、不延时、不读取业务结果补资源统计。旧批次不重放，不重装历史目录，不清理、不改系统。
namespace/watchdog 及支线保持暂停，production `E3_SUPERVISION_UNVERIFIED` 保持。

本登记没有创建 marker、执行 carrier 或运行真实核心任务；当前 marker absence 未作观察。
R 的实质变更 reopen 规则继续适用，治理关闭不代表实机验收。
