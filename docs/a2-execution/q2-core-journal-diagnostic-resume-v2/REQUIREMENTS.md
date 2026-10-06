# Journal proc 诊断修复后的一次替代预检

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope：
`LH-Q2-CORE-JOURNAL-DIAGNOSTIC-RESUME-v2`，仅 DR1–DR2。
原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、Owner authority、无例外及
准确 A→Owner B→独立 C→D 顺序不变；本文与[架构](ARCHITECTURE.md)、
[计划](IMPLEMENTATION_PLAN.md)构成本次待决方案。

## 已知事实与唯一新增权限

目标仍为原 journal 256→512 MiB 扩容，解除 Local Hand 核心链的容量阻塞。
[DR2 现场记录](../Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_FIELD_20261006.md)登记：
候选 `deab8acdabf0d35294f55fa87f2bc86d542fdf2e` 的唯一 DR2 窗口在 writer checkpoint 1
以 `GROWTH_PROC_LIMIT` 失败；marker、SSH、关机、备份、镜像增长、VM 启动和 ext4 增长均为 0。
该返回依据 Owner 截图，不是对完整原始输出或宿主状态的独立验证。
多个 proc 限制共用错误码，**具体分支、实际计数与缺口仍为 UNKNOWN**。

现有开发授权内的离线修复仅保留每个 proc 限制点（包括初读和复核）的固定类别、首次拒绝值、
原上限及适用 PID/TID；不增加现场读取，不改变五字段失败 schema，不改变接受/拒绝条件。
它解决诊断不具体的问题，不代表已查明或解决实际容量/阈值问题，不追补任何历史 UNKNOWN。

本提案唯一新增现场权限：该修复完成验证、发布、准确绑定及相关 CI 后，沿用原
`lhqjgrow-20261006a`、原对象、原输入与原流程，明确允许**再一次**替代预检窗口。
全部旧窗口继续保持失败/已消耗；没有 marker、源码修复、CI 成功或普通“继续”均不返还窗口。

## 完整继承与成功条件

继承上一替代方案 A `ef46ac169fd9084875cb5c5148a9c4985ace680c` 的
[未受影响要求](../q2-core-journal-diagnostic-resume/REQUIREMENTS.md)，以及原扩容 A
`59948ec4fedb807a31cdbff77acc134e84414160`、宿主读取 A
`2b4448c7b89d1910840f7aee2ae2b781f970e179`、终端认证 A
`2b236865dc0a89e475c4021cac44d7193f252f67` 的全部未受影响边界。

- Owner 仍以普通身份在已有真实本机前台终端操作，只有固定只读 writer 沿用已批准的 sudo
  认证。密码仅交给 sudo 的控制终端；不新增 helper、权限、预热、探测或系统配置修改。
- 保留全部身份、输入、锁、writer 覆盖/排他和容量检查，包括所有 PID/TID/FD/maps/read 上限。
  **不得通过提高上限、跳过任务、减少扫描覆盖、增加预算或忽略未知来取得 PASS。**
- 两 CLI 绑定同一准确 D、输入、nonce、终端及双时钟窗口；900s 总窗、780s 后不启新修改，
  每个 writer 检查点 15s（含认证）、最多八个检查点且各调用一次，全部保持。
- 所有原预算、历史用量、承诺及 UNKNOWN 保留；不另开预算池。跨历次维护累计最多一个
  marker、两条维护 SSH，以及正常关机、完整备份、镜像增长、VM 启动、ext4 增长各一次。
- 任一失败、未知、超时或绑定漂移立即停止；窗口已经开始即消耗，不重试、重连、补采、
  强杀、清理或自动回滚。失败可能留下 guest 已关闭或部分增长状态，原恢复限制不变。

仅当全部原预检通过，才可在同窗完成尚未消费的原维护动作。成功仍要求原身份/内容保留、
完整备份、两层增长及普通可用至少 400 MiB/32768 inode 的完整结果。
本范围不执行 H01/Q4/H11、不批准新 boot 的核心采用；支线继续暂停，production
`E3_SUPERVISION_UNVERIFIED` 不变。维护完成后依据真实 receipt 准备核心验收。
