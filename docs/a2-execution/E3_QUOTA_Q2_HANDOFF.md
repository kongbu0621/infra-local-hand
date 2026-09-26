# Q2 批量前检与保留证据复核

接续 [第七批三阶段整链](E3_QUOTA_Q2_CHAIN.md)。本批把实机执行前后的检查集中成两个显式入口，
并修复外层控制器启动观察和存储计费的具体缺口。范围仍为已 CLOSED 的
`LH-E3-QUOTA-HARNESS-v1`；原三层批准文档、生产封堵和历史 Q1 结论不变。

## 当前交付与前提

源码已经具备同一操作的 preflight、business、evidence，以及目标 controller 独立停止和封存。
这不表示真实 systemd、project quota、完整退出和总容量峰值已经验收。
当前云端执行器没有用户实验 VM 的 SSH 入口、既有 Q1 安装或 systemd PID 1，不能直接执行该 VM 的场景。

| 入口 | 输入 | 执行范围 |
| --- | --- | --- |
| `q2_fixture_check.py` | 准确 supervisor fixture 及其 SHA-256 | 汇总声明一致性与可观察的现有宿主条件；不启动控制器、查询器或业务 |
| `q2_supervisor.py` | 准确受保护 fixture 与其原监督环境 | 独立重新核验输入后，一次原交付、目标退出及有限封存 |
| `q2_evidence_review.py` | 已保留 output、declarations 两目录及独立固定的 seal SHA-256 | 只读校验保留产物的字节和语义一致性；不执行其中命令 |

原 `q2_batch_check.py` 保留已发行单阶段观察配置的 v1 合同，不是新三阶段 fixture 的入口。
普通 unit-test discovery 不启动上述实机工作。

尚未拥有完整 Q2 fixture 时，先用后续新增的
[现有实验机一次性交接](E3_QUOTA_Q2_MACHINE_HANDOFF.md)收集明确选择的当前事实。
该入口不要求先装配完整 fixture，也不改变 Q1 的已完成 scoped 结论。

## 一次收齐输入

fixture 沿用 `local-hand-q2-supervisor/v1 / ISOLATED_Q2_SUPERVISION`，nested launcher 采用
`local-hand-q2-launcher/v2 / ISOLATED_Q2_CHAIN`。完整字段及预算关系见第七批文档和严格 decoder。
不要从合成单测复制 UID、路径、project、boot 或时间作为现场值。

| 输入组 | 需要交付的实际对象 |
| --- | --- |
| 来源与安装 | 同一干净源码完整 commit、所有运行模块和 host 入口摘要、固定解释器/程序和普通安装树 |
| 原监督 | 已运行的独立 root supervisor 原 unit/InvocationID/cgroup、有限 CPU/内存/PID/时间、原双流及外部停止所有者 |
| 现有执行父级 | 专用空 controller、ordinary、query、management 父 cgroup，准确 device/inode 和关系 |
| 分配与原操作 | 三阶段同一 broker operation、原预算/generation、已固定 slot/roots、保留 evidence store |
| 控制与保留 | 准确受保护 fixture、既有独立空输出/声明目录、永久 journal、有限容量、原记录保留责任 |
| quota 与验收 | 管理侧真实文件系统/project 身份和硬限制依据；实际 enforcement、峰值及 H01–H13 逐项仍单独验收 |

前检读取不赋予修改这些对象的权限；没有自动建用户、设 quota、挂载、改 slice 或修改现役服务的步骤。

## 诊断入口与正式执行入口

以下变量必须由既有管理入口根据准确私有交付填写。相对脚本路径以该干净候选仓库为根。
先说明两个入口的区别：它们不是可以在同一原服务中依次运行的两条命令。
独立前检用于集中诊断已有对象：

```sh
python -I -B tests/e3_host/q2_fixture_check.py \
  --fixture "$Q2_FIXTURE" --sha256 "$Q2_FIXTURE_SHA256"
```

前检输出 `CHECKED` 或 `BLOCKED`，只表示当时的观察快照。原监督身份要求 PID、InvocationID、
cgroup、管道和限制同时吻合；普通交互 shell 或服务中的子进程不满足自身准入条件，
报告会保留这个 BLOCKED，同时列出其他可检查的独立结果。缺少 fixture、来源不符或检查不完整，
应保留 BLOCKED 和具体缺口，不能从局部成功推导出整机准入。
即使把前检直接作为准确服务 MainPID 执行得到 CHECKED，它退出后也不能再复用该 InvocationID
执行 supervisor。前检不交付可复用授权，不延长、重建或刷新原期限；本批没有新增同进程接续运行器。

正式执行由既有监督所有者，使用准确原 fixture，直接在对应的原服务上下文中执行唯一一次。
supervisor 会自行重新核验原输入与身份，不消费独立前检的 CHECKED：

```sh
python -I -B tests/e3_host/q2_supervisor.py \
  --fixture "$Q2_FIXTURE" --sha256 "$Q2_FIXTURE_SHA256"
```

这不是重新启动或重新 provisioning supervisor 的指令。该入口仍要求已有独立监督，
不提供绕过 MainPID/管道/期限核验的 shell 包装。目录被消费、启动不明或失败后，保留原现场；
不再次执行这条命令来刷新结果。

## 已有证据一次复核

在可信观察侧固定 `seal.json` 的 SHA-256；同目录自行计算出的摘要只能作为传输校验，
不能替代独立来源绑定。复制保留证据后，可以显式指定副本目录：

```sh
python -I -B tests/e3_host/q2_evidence_review.py \
  --evidence "$Q2_OUTPUT_COPY" \
  --declarations "$Q2_DECLARATIONS_COPY" \
  --seal-sha256 "$Q2_EXPECTED_SEAL_SHA256"
```

复核只读取显式目录中的固定成员，不跟随证据文本内的任意路径，不重放 argv，不调用 manager
或 quota syscall。缺失、截断、错摘要、错原身份、未完整退出/EOF 或无有效 seal 均不能记为完整。
完整复核仅表示固定摘要所锚定产物内部一致，不证明当前现场状态、外部摘要来源或未记录的历史峰值。
成功状态为 `OFFLINE_ARTIFACTS_CONSISTENT`；缺输入为 `BLOCKED`，一致性不足为 `INCOMPLETE`。

仍须区分：磁盘 `CLOSURE_OBSERVED_SEAL_PENDING` 是封存前记录；只有单独有效 seal 才能支撑
目标 controller 范围的关闭结论。`CONTROLLER_CLOSED` 的范围是 `TARGET_CONTROLLER_CLOSURE_ONLY`，
外层 supervisor 自身仍需要原独立退出证据。所有入口保持 `q3_accepted=false`、`production_supported=false`。

## 实机接续与停止点

前检、原执行和复核集中保存完整 stdout、stderr、准确命令、开始/结束时间及原退出码。
原始宿主证据保持私有；公开仓库只记录脱敏结论、准确源码、摘要和未覆盖项。
无需逐项来回复制输出；一次交付报告、缺口和完整保留证据，便可定位同一轮的失败位置。

下一阶段仍按 [H01–H13 验收顺序](E3_HOST_ACCEPTANCE_RUNBOOK.md)推进：先正常链和资源/隔离，
再故障与恢复；分别证明真实全程容量上界及外层原退出。缺少 fixture 的场景为 BLOCKED，
不把本地文件/管道实测、模拟管理器或离线一致性复核计作真实宿主通过。
Q1 的 UNKNOWN/INCOMPLETE、原 payload、reservation 与已消费预算继续保留，不退款、不覆盖或重放。
