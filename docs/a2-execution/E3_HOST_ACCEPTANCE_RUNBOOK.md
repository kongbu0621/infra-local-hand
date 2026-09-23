# E3 隔离宿主盘点与实机验收准备

本文件是非权威的执行准备说明，依据固定 A `79f73faedcd9cde4164b0d1625782dae27db6c2f` 的[需求](REQUIREMENTS.md)、[架构](ARCHITECTURE.md)和[实施方案](IMPLEMENTATION_PLAN.md)，并与当前[受监督启动及结果读取](SUPERVISED_BOOTSTRAP.md)实现对齐。规则 R、E1–E3 Owner 决定与独立记录 C 仍见根 `AGENTS.md`；本文件不替换三份批准原文，不要求重复批准已 CLOSED 的 E1–E3。

**本轮可执行范围为只读宿主盘点；真正 E3 三单元实机验收尚无完整入口，仍 BLOCKED。** 盘点只回答当前进程可以观察哪些条件，不启动 job，不证明系统约束已经生效，也不授予生产部署权限。`SystemdManager.support()` 的 `E3_SUPERVISION_UNVERIFIED` 固定封堵保持不变。

当前还存在 **本地 project quota 查询权限与单元隔离之间的实现障碍**：仅预建一台 ext4/xfs 配额主机不足以使原 runner 可运行。须先按 [E3 实现缺口](E3_IMPLEMENTATION_GAPS.md) 核对查询机制、设备可见性及现场 errno，不能把问题简化为“换台支持 systemd 的主机”。

## 1. 两类活动与判断标准

| 活动 | 可做什么 | 不能据此声明什么 |
| --- | --- | --- |
| 只读 readiness 盘点 | 读取固定 proc/sys 事实、工具版本及当前用户 manager 的固定只读查询，记录缺失、拒绝与不明 | 委派已生效、真实 quota 可强制、namespace 已隔离、取消可达、E3 PASS 或候选可部署 |
| 后续真正 E3 验收 | 在已预建且独占的隔离测试环境内，运行准确候选与准确 host fixture，实际制造有限进程／资源／存储故障，取得完整证据 | E4 客户端接入、E5 GX10/S2 切换、E6 真实 NAS，或扩大已批准的作业契约 |

当前 `tests/test_local_hand_jobs_runner.py` 的 `test_real_delegated_cgroup_integration_is_not_a_simulated_pass` 是诚实的占位：它使用无私有配置的 manager，遇到 unsupported 就 SKIP；即使支持判断返回真，也直接 FAIL 并要求真实准入 fixture。**换到有 systemd 的机器运行该用例不会自动完成 E3。** 不修改断言、monkeypatch support、移除固定拒绝或增加布尔开关来取得通过数。

现有合成 manager、mock namespace／quota、临时目录、Samba 响应和普通进程测试，继续保留其原覆盖标签。主机恰为 Linux、PID 1 为 systemd、存在 `cgroup.controllers` 或 `cgroup.procs` 可写，都只是条件观察；这些事实不证明三个 unit 的有效约束。

## 2. 当前可执行的只读顺序

使用已获准读取的本地候选副本和普通当前账户；不要从活动部署目录或真实 NAS 执行。若候选只存在于远端，应通过已有授权的源码取得流程准备副本；本步骤不安装软件、不提权、不创建服务或任务目录。

1. 记录准确源码 commit、dirty 状态、探针文件摘要、解释器版本和采集时间。候选工作区有改动时保留差异，不能把它写成干净 commit 的执行。可使用以下只读命令：

   ```sh
   git rev-parse HEAD
   git status --porcelain
   sha256sum tools/probe_e3_host.py
   python3 --version
   ```

2. 在同一候选根目录执行本轮的固定盘点入口：

   ```sh
   python3 -I -B tools/probe_e3_host.py --label candidate
   ```

   由调用方将完整 stdout、stderr、退出码、开始／结束时间和准确命令保存到已预建的私有证据位置。报告中的主机身份、路径、进程与挂载元数据按私有证据处理；公开仓库仅保留脱敏结论及摘要。探针不会因保存报告而修改宿主配置。

3. 按每项事实审阅报告。工具缺失、访问被拒、manager 不可达、输出截断、超时或解析失败均保留原状态。探针 exit 0 只表示成功生成 JSON 盘点报告，不表示宿主合格；参数不合法时 exit 2。`readiness` 区分 BLOCKED、INCOMPLETE、OBSERVED_NOT_ACCEPTED，`real_e3_accepted=false`、`production_supported=false`、`business_authorized=false` 始终不变。若某项只取得声明／可读性，不能转换为实际功能 PASS。
4. 形成缺口清单，关联下面的私有输入与场景。此时结束本轮宿主操作：不根据盘点结果自动建用户、改 sysctl、委派 cgroup、建 slice、创建 unit、挂载文件系统、设 quota、放开网络或读真实凭据。

探针的可选声明参数为 `--label candidate|scratch`、`--expected-uid N`、配套的 `--cgroup /sys/fs/cgroup/... --slice NAME.slice`，以及最多八个 `--mount-target ABS_PATH`。这些参数只限定本次盘点／对照目标，不授予相应路径权限；不能凭猜测填入私有 UID、slice 或目录。`--mount-target` 只从已读取的 mountinfo 中匹配元数据，不解析、打开、stat 或遍历传入路径。

探针不枚举 NAS 目录、不读取其文件、不执行 quota syscall，也不调用 NAS query。固定工具动作仅为 systemctl/systemd-run 版本及当前 user manager 的只读 show，不创建待验收 unit。proc 中可能出现的挂载元数据不能当作已访问或验证 NAS 内容。准确字段、固定查询和返回语义以本轮 `tools/probe_e3_host.py` 实现及其测试为准，不能沿用另一版本报告。

当前报告 schema 为 `infra-local-hand-e3-host-probe/v1`，`observations` 包含 host、identity、namespaces、cgroups、mounts、systemd 六组，`gaps` 保存结构化 code/component。`unverified_blockers` 固定保留 `REAL_HARNESS_MISSING`、`QUOTA_PERMISSION_MODEL_UNVERIFIED`、`E3_SUPERVISION_UNVERIFIED`，不会因只读观察齐备而删除。报告是一次有界观察快照，不是可重用的部署许可。

Slice 与委派分别核对：[systemd 固定版本委派说明](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/docs/CGROUP_DELEGATION.md)明确 `Delegate=` 适用于 service/scope，不适用于 slice。探针只观察指定 slice 的状态、ControlGroup 和 accounting 属性，不要求给 slice 设置 `Delegate=yes`；user manager 上游的真实委派与实际 unit 约束仍待验收，不从目录可写性或 slice 存在推断。

## 3. 真正 E3 开始前必须齐备的输入

下面是事实与实施前置条件，不是重复请求 E1–E3 授权。缺一项就把对应真实场景记为 BLOCKED，继续可完成的源码／文档工作；不临时扩大正在使用的普通账户或现役服务权限。

| 前置条件 | 必须固定并核对的证据 |
| --- | --- |
| 准确执行来源 | 干净候选完整 commit/tree、wheel 和四包 payload 摘要、安装解释器、真实模块入口；场景 fixture／harness 的准确源码、参数、版本和摘要。当前仍缺完整真实 host harness，不能用不存在的命令代替 |
| 专用隔离宿主／账户 | 与旧 projects/state/mailbox、生产 writer 和真实 NAS 无重叠的测试范围；专用非 root UID、主机 boot ID、内核／systemd／Python 版本、账户和可写资源责任；测试仅使用合成身份和数据 |
| manager 与 cgroup | 当前专用用户 manager 实际可达、准确预建 slice/cgroup、父子关系、相关 controller 的有效启用与写入权限；broker 不能管理任意 unit。只读文件或 `os.access` 结果不能代替真实单元验证 |
| namespace 与文件边界 | 当前内核／账户允许该实现使用的 user/mount/network namespace 和 systemd 属性；准确源／cache／prepared 映射只读，控制账本与数据根隔离，回落路径不可写。不能以 sysctl 数值代替实际 namespace 结果 |
| 预建本地 slot 与 quota | 有限 slot 池及 evidence store 均由受信准备侧事先创建；固定 device/inode/uid、私有权限、无别名／重叠；当前实现仅接受 ext4/xfs inherited project quota。须先解决原非 root／PrivateUsers／PrivateDevices 单元中的查询机制障碍，并验证真实有限 hard limit、计费身份及合并峰值预算；预建目录与 quota 不解决查询权限，没有自动建根或扩池 |
| 预算与时钟 | 每类 job 的全部有限预算、总并发／排队／保留量／账本应急容量、control response 秒数及测量方法；boot-bound operation/phase deadline、v3 三份 CPU 分额和终止宽限。不能用更大测试预算掩盖实际超额 |
| 可信控制和证据入口 | 私有 policy 的准确 node/install/epoch/profile/policy/registry 绑定；authority 锁和 state 根；测试 CLI/MCP 与同 broker 关系；预建私有证据位置、保留容量、完整日志捕获和独立停止观察入口 |
| 故障范围与恢复手段 | 每个故障仅作用于准确测试进程、单元或已声明的合成资源；固定注入点、最大影响、停止条件和恢复责任。存储阻塞须使用预建的隔离故障 fixture，不对现役盘、真实 NAS或全机网络实施故障 |

host fixture 必须让真实 systemd/cgroup/namespace/本地 quota 参与验证，同时保持生产 support 封堵；其明确的测试装配与可验证入口还需实现和审阅。它不能替换 manager 为 mock、把真实 OS 检查返回值写死为真，或直接绕过 broker 的持久意图和启动围栏调用业务命令。

本说明不提供改变宿主配置的 sudo、mount、quota、sysctl、systemctl enable/start 命令。尚未预建的条件是当前缺口，不由只读探针自动补齐。不同 systemd 版本与文件系统行为分别验收；引用固定 v257 源码不是对现场版本的通用认证。

静态依据中，[Linux v6.12 的 quota 权限检查](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/quota/quota.c) 对 PRJQUOTA 的 Q_GETQUOTA 要求 CAP_SYS_ADMIN；[systemd v257 的 PrivateUsers 说明](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/man/systemd.exec.xml) 不赋予宿主 user namespace 的能力。原路径达到该检查时预期会被拒绝，但 PrivateDevices 下 source block device 解析也可能更早失败，不能预填所有目标都返回 EPERM。准确 errno 只能在未来隔离真实用例中观察。本轮不调用 Q_GETQUOTA：固定内核源码将它列为可能分配 quota 元数据、需 write/thaw 处理的路径，不能仅因名称含 GET 就当成无副作用只读盘点。

当前实现也未保留 quotactl 的即时 errno，bootstrap 标准流为 null；一般 UNSUPPORTED 或 unit 非零退出不能反推已观察到哪种内核错误。准确 syscall 诊断的受监督取证入口也属于尚缺实现。

禁止以 root 运行、授予宿主 CAP_SYS_ADMIN、关闭 PrivateUsers／PrivateDevices，或放宽普通 helper 的权限来获取验收 PASS。可行查询机制及其信任／权限边界须先由实现复核解决，保留真实失败与未完成状态。

## 4. 后续真实验收的执行顺序

真正测试只能在上一节完整具备且准确 harness 已交付后进行。以下是执行顺序和证据约束，**不是当前已有一键可运行的 host 验收脚本**。

1. **先处理实现障碍，再冻结输入。** 明确原单元的 quota 查询可见性／权限机制及实际 errno，完成准确 host harness；无法成立就停在该缺口。保存准入 manifest、候选／安装／fixture 摘要、当轮只读盘点以及每个场景的预期结果。负例预期应为拒绝或 UNKNOWN，不能统一要求业务 SUCCEEDED。
2. **建立对照。** 先取得独占合成控制根、slot 池、证据容量和空闲 unit 库存的准确事实；无法证明没有原 writer／延迟启动时不开始新场景。不得清账本、删 lease 或清空已消费 slot 来制造空闲。
3. **最小正常链。** 用准确合成 profile 通过同 broker 执行固定本地作业，证明 bootstrap → helper → result_reader 的三个真实 unit 和三次 durable guard。bootstrap 完成不等于业务启动；helper 退出不等于结果验明；reader 成功不改写 helper 退出码。
4. **资源与边界负例。** 依次运行下面 H02–H05，先验证拒绝／限额的实际效果，再进行阻塞和崩溃故障。每项只使用自己已消费的根，不与前项残留混合。
5. **启动、取消及故障。** 运行 H06–H10 的准确注入点。任何退出或未来启动仍不明，都冻结有关资源，先按原身份观察／停止，不为推进矩阵更换 operation ID 或再建 helper。
6. **恢复、核对和证据。** 在保留原账本的前提下运行 H11–H13；仅在合同允许且原 writer／未来启动已被证明阻断时，显式提交独立 reconcile。用独立审阅核对事件、实际进程状态、文件残留和证据成员是否一致。
7. **作出逐项结论。** 汇总真实 PASS、正确拒绝／正确 UNKNOWN、FAIL、BLOCKED、SKIP、LOGIC_ONLY。未完成项不自动转绿；将修复绑定新准确候选，保留先前失败证据，不以重试覆盖原记录。

## 5. 逐场景证据与通过判据

每一行都要求真实 OS/文件系统证据。源码单测只为场景提供预期，不代替本表结果。场景映射回固定 A 的 AX-V01–V12，实际 Ledger 程序仍按固定调用合同执行。

| ID / 映射 | 实际场景 | 必留证据与通过标准 |
| --- | --- | --- |
| H01 / V01,V05,V10 | 准确来源、独占 authority 与三单元正常链 | 原请求摘要、源码／安装身份、slot grant、三次交付意图、boot/unit/InvocationID/cgroup、原 helper 和 reader 退出事实；新版本固定为 v3，不越过任何 guard，不产生第二 authority |
| H02 / V02,V06 | 文件与 namespace 边界、临时目录回落 | 各 unit 实际 namespace、mount 属性、真实写入拒绝；bootstrap/helper 仅能写准确 slot，profile 父树、控制根、只读输入和系统临时根不可写；实际解释器 tempfile 与匿名临时写入绑定本 job；reader 无任务根写权。环境变量正确不是通过依据 |
| H03 / V02,V08 | 本地 project quota、查询权限、合并保留峰值与别名 | 原单元内准确 syscall/返回值/errno、user namespace 与设备可见性、目录 FD 的 device/inode/uid、继承 project ID、FS 与 hard bytes；查询未成立先记 BLOCKED，不提权兜底。机制成立后受控超限写入确被拒绝，实际峰值不超过准入上界；相同 quota identity 不重复计算，多个独立 quota 的合计不越预留。dirty／替换／错误 marker 根不产生业务启动，失败根保持消费 |
| H04 / V02,V04,V08 | CPU、RSS、进程数与完整子孙树 | unit 属性、实际 cgroup cpu/memory/pids 计数、子孙关系和故障结果；内存／进程限制实际生效。特别验证全进程树累计 CPU 是否落在各分额和总预算内；CPUQuota 是速率属性、LimitCPU 的配置值不是整树累计硬上限证明，证据不足或实测超额即未通过 |
| H05 / V04,V08 | 独立 stdout/stderr、日志超限与三段截止时间 | 双流原始字节计数、保留／丢弃／截断记录；超限后仍排空并受控停止。bootstrap、排队、helper、reader 共用原 operation/phase deadline；每段时间与 CPU 分额完整，无重启／切段续额或退款 |
| H06 / V03,V04,V09 | 每次 durable intent / manager 交付 / 回执交界的崩溃和响应丢失 | 对 bootstrap、helper、reader 分别注入，保存确切注入点、持久事件序号、原 unit 及 manager queued job；恢复只观察／停止同一身份，不补投后续 stage、不重放原业务，未知不能伪报“未执行” |
| H07 / V04,V09 | 三次交付前后的取消、撤权、策略代次变化与迟到激活 | 取消／撤权持久点、guard 决策、Job/ActiveState/SubState、InvocationID 和递归 populated；持久点后不新增获准交付。已投递但未 ACK 的请求须证明未来启动被阻断；当前 cgroup 空或本地命令退出不能单独证明取消完成 |
| H08 / V04,V08 | bootstrap 目录打开／quota／fsync 和 helper 输入哈希的真实阻塞 | 阻塞 fixture 身份、处于内核 I/O 的进程证据、同时进行的 status/cancel 请求及单调时钟延迟；本地账本健康时回执须在冻结 control_response_seconds 内返回。发送 TERM/KILL 但未证实退出时维持 UNKNOWN、租约、容量和已消费根 |
| H09 / V04,V08 | helper 已退出后的 result 文件打开／读取真实阻塞 | 原 helper 完整退出事实、独立 reader 的实际阻塞、控制响应、停止请求和 reader cgroup；observer 不回退直接读取 result 文件、不等待存储；结果不明与原 helper 已退出分别记录。用 sleep 或 mock `_read_result` 只算逻辑测试 |
| H10 / V04,V07,V08 | reader 帧、管道和 `systemd-run --pipe` 客户端生命周期 | READY/RESULT 摘要及长度、原 helper/reader 身份、管道 EOF、reader 整树退出与本地 collector 停止事实；半帧、超限、错身份和追加字节不被接受。杀本地客户端不证明 unit 退出；reader 成功不能覆盖原 helper 非零退出 |
| H11 / V03,V04,V05 | broker 重启、原 pipe 丢失、旧 v1/v2 receipt 与身份复用 | 保留原数据库及三单元身份、boot、状态恢复事件；不重新读取旧 result、不新增未预留 reader、不延长 deadline。三个原 unit 已退出可独立记录，但丢失原客户端证据仍为 collectors_stopped=false，不封存／释放原屏障、不按未知 PID 杀进程 |
| H12 / V03,V04,V05 | UNKNOWN 后的显式只读 reconcile 与并发屏障 | 原执行完整停止／未来启动阻断证明、准确 reconcile_id、当前独立授权、预算和新 slot；同 id 重试复用原记录，同父最多一个活动核对。核对只读原来源，可写自己的 scratch；不续跑业务、不发布 NAS、不释放已消费 slot |
| H13 / V07,V10,V12 | 证据完整性与固定本地 Ledger fixture 链 | 静止证明、完整事件、原失败及残留成员、create-only/fsync/登记交界故障、ZIP/manifest/seal 的独立校验；固定 Ledger 来源／wheel／解释器／输入链准确，上游自清理成员标 EPHEMERAL_BY_UPSTREAM_TOOL。来源测试通过不自动表示 E3 资源约束通过 |

H11 的跨 boot 处理另需真实更换 boot 的隔离证据；不能把修改 JSON 的 boot ID 当实机重启。若本轮测试范围没有一次性实例的安全回收／重启条件，该子项记 BLOCKED；本说明不执行或提供整机重启命令。PID 复用、unit InvocationID 改变和 manager 信息不可读也应分别证明“不明时不抢占”。

结果读取正例要求原 unit 与本地 collector 的证据同时完整。恢复后仅已知三 unit 全部退出但原管道／客户端归属丢失的场景，正确结果可以是保留 UNKNOWN；这是故障语义通过，不是原业务成功或原证据可封存。H12 是否可启动按现有合同逐字段判断，不把缺少 collector 事实改为 true。

## 6. 统一停止、保留与重新进入条件

发现身份／来源／挂载绑定变化、资源计费超额、非准入路径写入、控制请求超出已冻结界限、证据链缺失，或任何原进程树／排队启动不明时，立即停止该场景的新提交及后续 stage 交付。只通过准确原身份发起受控停止和观察；不能用全机 kill、任意 unit pattern、删除 state、重建 authority 或切回旧版本来“收尾”。

停止结论至少分别记录：新准入是否关闭、原延迟启动是否封阻、bootstrap/helper/reader 各树是否退出、writer 是否停止、collector 是否停止、已知副作用、证据状态和缺失事实。TERM/KILL、命令超时、一个 PID 消失、systemd-run 客户端退出和查询不到 unit，均不能单独满足全部条件。

保留原操作／核对身份、SQLite 事件、原始 stdout/stderr、完整或部分结果、归属 marker、root grant、分配 lease、证据产物和故障 fixture 的可记录现场。UNKNOWN 不释放资源屏障；所有已消费 slot 在成功、失败、取消和重启后都不退款。测试容量不足即停止，不能删历史或回收已消费根继续凑场景。

重新进入新的真实场景前，应有准确停止证明和当前授权／版本／资源事实；涉及 UNKNOWN 的原业务只可依合同显式核对，不以新 id 重跑。修复造成候选变化时，记录新来源和受影响场景重验范围；旧失败不覆盖、不回写为 PASS。真实结果若推翻批准设计假设，按既有变更规则处理，不由实现静默改变验收标准。

## 7. 证据包与最终判定

每次场景至少保存以下并行信息，使用私有证据包并附逐成员 SHA-256：准确候选／安装／harness 身份与命令；预期、开始／结束时间和原始退出码；准入 manifest 摘要；operation/execution/reconcile ID、状态事件序号和预算；三个 unit 的 boot/InvocationID/cgroup/queued job 与实际计数；slot／quota 绑定、现场成员及部分失败；控制请求延迟原记录；结果／ZIP／seal 的校验及全部缺失事实。日志须原样捕获；事后转录要明确标 TRANSCRIPT，不能冒充原重定向日志。

通过标准是本表对应场景的真实机制与预期行为均被独立核对，且固定 A 的 AX-V01–V12 隔离列其余要求有准确候选证据。每个负例的正确拒绝或保守 UNKNOWN 可计为该故障语义验证通过，但不能计为业务成功。SKIP、BLOCKED、UNVERIFIED 和 LOGIC_ONLY 不计真实机制 PASS；本地、CI、安装态和宿主结果不得相加或跨候选套用。

只读报告完全产出、工具版本齐全、原占位测试不再被环境拒绝，都不构成 E3 出口。当前仍缺真实 host harness 和上述实机证据；没有自动更新 support 或生成生产启用配置的步骤。即使将来本地监督各项完成，也须在最终状态报告中继续单列尚未完成的 NAS collector、writer SID／计费域／限定网络准入，以及 E4、E5/S2、E6，不能直接宣称 A2 可部署。
