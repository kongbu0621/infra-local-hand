# Local Hand 核心交付：云端与本地 Codex 交接

2026-10-04 +08:00。此页是工作交接，不是新的运行时合同、Owner B 或执行许可。
用户本轮指令：由云端完成能完成的工作，将必须本机完成的工作交本地 Codex；
“直接推进核心功能，暂停搞分支功能。”

本地已按本页仅复核既有材料并返回[脱敏事实表与准确缺项](Q2_CORE_LOCAL_HANDOFF_RESULT_20261004.md)。
该结果不构成现场资格或执行许可；下一步按文末分工收敛 capture 路线。

## 唯一交付目标

在已有隔离环境中完成 **正常任务执行并收回结果 → 运行中取消 → 同一任务恢复查询**。
保持原 H01→Q4→H11 条件顺序、真实证据和失败停止规则；每个 case 有自己的对象和 ledger。
H11 恢复的是 H11 自己 origin 的原 ledger/request/execution/unit/grant/deadline，不能借用 Q4 ledger。
namespace、watchdog、旧版能力扩建、内核证明扩展、生产切换与 NAS 支线暂停。

## 接手基线与实际缺项

- 本次工作输入主干：`d374afd1b2e629c4308a6634e04ca95575ec3598`。
- 原核心 CLOSED A：`74366b3fe41e675b1aa2d677228714a5606c275c`；C：
  `a8dd077392ebb656770c8f94ca3b051e93fc296d`；部分 D：
  `520f77f578b90d31870517e33e29bee42918f3c0`。
- 修订 proposal A：`4009e1b560dd873bc3d9b937be539f329b93371a`，仍 OPEN / REVISION REQUIRED；
  [登记](../governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_BASELINE.md)固定准确三文档及摘要。
- 真实效果入口位于 `tests/e3_host/q2_core_delivery_dispatcher.py`：`admit`、`install`、
  `prepare_case`、`plan_case`、`run_h01`、`run_q4`、`recover_h11`、`phase_facts` 与完整 `usage`。
  policy/retained inputs 未绑定，H01/Q4/H11 等入口仍未实现；不能把 FakeEffects 测试当作它们已完成。
- dispatcher release allowlist 仍为空；package=null / NOT_ISSUED。此次核心批次的
  marker/request/H01/Q4/H11 均未执行；历史别的批次不因此变为零或可重放。

## 分工与合并

| 执行方 | 责任 | 交付 |
| --- | --- | --- |
| 云端助手 | 可访问仓库中的实现、定向验证、独立复核；先处理有明确旧授权的工作 | 准确提交、测试结果、未完成项 |
| 本地 Codex | 复核已经保留的私有材料；方案确认后复用现有环境执行仅本机可做的步骤 | 脱敏摘要、可核对的私有证据引用、真实结果 |

接手先检查本地未提交工作和 HEAD；工作区干净且可快进时执行 `git pull --ff-only`。
有本地改动或分叉时保留并报告差异，不 reset、clean、覆盖或自动 stash。避免两边同时改相同文件；
推送前重查 main，保持已有提交。旧 Local Hand 只复用已经准入的能力，不扩建旧版以解锁本任务。

## 本地 Codex 现在执行的最小任务

**仅复核已经保存的材料，先回答 host capture 路线是否实际可用。**
这一步不需要连接 guest、探测当前内核或创建现场对象。

1. 读取根 `AGENTS.md`、本页、修订复核登记及其中已引用的历史资料。复用已有 K4/R3、
   management anchor、profile、安装及存储记录；不重采已有证据。
2. 在本地既有私有输入中定位本次准确 core capture anchor 的来源关系，核对它与真实
   management host/mount 的记录绑定。公开仓库仅存脱敏关系，不写私有路径、IP、账号或密钥。
3. 核对该 anchor 是否已有硬配额或固定容量存储记录：对象身份、byte/inode 上限、
   已占用量、剩余量、执行身份权限分别是否有证据。没有记录就写 UNKNOWN，不能假设现成机制存在。
4. 核对机制覆盖：七个输出对象、parent 增长、额外 inode、瞬时分配和共享使用者是否计费。
   保持原 64 MiB/16 inode 总限额；修订候选的流上限为 52 MiB。逻辑文件大小、终态 `st_blocks`、
   `df` 或 guest project quota 都不能替代 management host 的完整计费边界。
5. 返回下面的一张事实表和最小路线判断。记录只证明其保存时点，不能写成当前资格 PASS。
   缺资料时定位到具体缺少哪份记录即可，停止在此缺口；不自行开内核研究或新采集任务。

| 返回项 | 内容 |
| --- | --- |
| 仓库基线 | 实际 HEAD、采用的 proposal A 和 OPEN 登记 |
| 已有来源 | 非敏感记录代号、bytes、SHA-256、原记录时间；完整对应关系保留私有 |
| 对象绑定 | 是否为准确 core anchor、真实 management host；mount 关系是否有记录 |
| 现成机制 | 有证据的机制／材料明确无机制／UNKNOWN；限额、占用、余额和权限分开列出 |
| 覆盖 | 七对象、parent、额外 inode、瞬时分配、共享使用者逐项列有证据／不覆盖／UNKNOWN |
| 路线与缺项 | 能用哪条已有路线；不能选定时，列准确缺失材料及影响 |
| 本次动作 | 已复核的既有材料；新 SSH/marker/carrier/任务/安装/配置/清理/重试均为 0 |

此表是人类可读交接格式，不是新协议或 runtime schema。公开结果可提交为
`docs/a2-execution/Q2_CORE_LOCAL_HANDOFF_RESULT_20261004.md`；raw machine evidence、私有配置和
完整来源关系继续留在既有私有记录，不上传 Public。
不要安装工具、创建 loopback、格式化、调整 quota、迁移 anchor、sudo、读取 raw device 或
重新资格化旧入口来填表。本机资料不足不等于 core 功能永久不可实现，只表示当前路线依据不足。

## 收回本地结果后的连续推进

1. 云端据事实选择能在现有环境落实的 capture 方案，修订必要合同，保留原资源上限与功能需求。
   不把缺失的 loaded-ext4 度量、完整内核模型当作默认新增项目。
2. 形成具体可审阅的准确 A 后，才按根 `AGENTS.md` 与固定 R
   `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 请求必要的 Owner B，并单独登记 C。
   当前“协作推进”指令不替代这项准确合同确认；本页没有增加任何 Gate。
3. 闭合后直接补齐上述真实效果入口和结果校验，固定一次 package，执行必要源码/安装态验证。
   原已有 SSH、安装和历史材料按准确合同复用，不自行覆盖冻结 candidate 或重装。
4. 本地仅按冻结任务执行一次正常链；前项 PASS 才进入 Q4/H11。失败保留现场并返回首个真实失败，
   无自动重试、重连、清理或旧批次重放。修复必须针对已定位原因。
5. 用真实任务受理、执行/退出、取消/恢复和结果回收记录判断完成。文档提交、CI 通过、
   service active、package 构建均不能单独宣称核心交付完成。
