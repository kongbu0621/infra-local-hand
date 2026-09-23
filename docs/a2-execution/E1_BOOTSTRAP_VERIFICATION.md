# E1 受监督启动准备：实现与验证记录

日期：2026-09-23。本文绑定实现提交 `4be98b8c03a4346d80d24663b0c655248b48e744`。报告由后续独立文档提交承载，不将报告提交冒充构建来源。

**本轮已实现受监督启动准备，并完成准确源码的 808 项通过、3 项明确跳过；候选仍不可部署。** E1 整体尚有 NAS 硬配额 provider 代码缺口，真实 E3 和正式 helper 结果读取的阻塞边界未闭合。准确提交的 Linux／Windows CI 已通过。当前工作区的两次本地安装检查失败单独保留，不改记为通过；详情见第 4 节。

## 1. 范围、来源与授权

本轮在已经批准的 `LH-A2-EXEC-MCP-v1` E1–E3 范围内，补齐任务启动准备的内部实现与必要验证。公开六类作业、七工具参数、旧 Task/Result v1 和八动作不变；没有新增生产部署授权，也没有进入 E4、E5/S2 或 E6。

| 对象 | 准确身份 |
| --- | --- |
| 本轮实现提交 | [`4be98b8c03a4346d80d24663b0c655248b48e744`](https://github.com/kongbu0621/infra-local-hand/commit/4be98b8c03a4346d80d24663b0c655248b48e744) |
| 实现 Git tree | `1cf94e3997f1b844e868094c27596942524206cf` |
| 父提交／恢复起点 | `fd55c07e93f590afb14da3720f54ce2fcb872199` |
| 实现提交时间 | `2026-09-23T15:43:21+08:00` |
| 规则基线 R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 已批准三层设计基线 A | `79f73faedcd9cde4164b0d1625782dae27db6c2f` |
| 独立开工记录 C | `367632126c1930983a06b1854f63789448633148` |
| Owner 决定 | `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`，见 `docs/governance/A2_EXEC_E1_E3_OWNER_DECISION.md` |

本轮来源恢复见 `E1_E3_RECOVERY_FD55C07.md`；内部实现边界见 `SUPERVISED_BOOTSTRAP.md`；当前完成程度见 `IMPLEMENTATION_STATUS.md`。三层权威文档保留批准时原文，其历史 DRAFT/OPEN 标记不重新否定 E1–E3 已获批准的事实。

fd55 恢复记录陈述已有提交及当时 CI；本报告记录新候选的新验证。第十轮或 fd55 的测试数、产物摘要、封存材料不转记为本轮证据。

## 2. 本轮实际实现

原 `SystemdManager._start` 在 broker 的 observer 线程中访问任务根、核对配额和写入计划。线程不能独立监督或停止阻塞的文件系统调用。本轮把这些动作移入确定性 bootstrap unit，成功退出并重新通过启动围栏后，才交付正式 helper unit。

| 实现 | 可观察行为 |
| --- | --- |
| 私有预建 slot 与永久消费 | root grant 绑定操作、阶段、目录 device/inode/uid 与摘要；在执行意图事务中分配。preflight/business 只在同一操作内复用原 slot；其他阶段独立消费。取消、失败和重启均不回收已消费 slot |
| 受监督准备 | bootstrap 内验证 namespace/cgroup、已准入根身份及硬配额，写归属 marker 和 create-only 计划，执行文件与目录 fsync；不创建 profile 父目录、不扩大父目录写权限 |
| 两次持久交付 | 分别登记 bootstrap/helper 意图；准备单元的原 boot/unit/invocation、退出码、递归进程树与 queued job 共同形成准备证明。第二次交付前重新检查授权、取消、策略代次、租约和预算 |
| 有界计划输入 | 固定执行计划以规范 JSON/Base64 传递，原始 JSON 上限 64 KiB，另检验单参数及总 ARG_MAX。拒绝已列凭据字段、非固定环境变量和歧义路径；Base64 不是加密或通用秘密检测 |
| 原预算贯穿两单元 | phase 截止从持久预留时刻起算，包含准备、排队、两个单元及终止宽限；CPU 固定分额，不因交付、恢复或阶段切换续额 |
| 恢复与取消 | 首次 manager 回执丢失仍推导并观察两个原 unit，不续接启动；预算损坏不授新时间，但可独立确认的原身份仍能停止。一单元观察或停止失败，不阻止尝试另一单元 |
| 正确聚合结果 | bootstrap 成功但 helper 被拒绝、取消或预算耗尽，不被计为完整 phase 成功；保留“辅助执行发生过、业务未开始”的区别 |
| 服务与证据装配 | 启动库存由持久 execution/root grant 推导双 unit；所有 bootstrap profile 使用同一个准确准入的 evidence store。store 绑定已存在目录身份，控制端不自动创建替代目录，每次访问核对持有 FD 的身份 |

没有安装或切换真实 GX10 服务，没有调用真实 NAS，没有注册当前 ChatGPT 私有 MCP 连接。

## 3. 准确候选的验证结果

以下结果分别记账，互有覆盖，不相加为一个总通过数。

| 验证层 | 准确结果 | 解释 |
| --- | --- | --- |
| 干净准确源码全量 | **808 passed，3 skipped；354.76 秒** | `full-source-final.log`，绑定 `4be98b8`；不使用中途 collection 的旧计数 |
| Python 编译 | **PASS** | 本轮构建记录中的 compile 退出码 0 |
| 构建及产物来源绑定 | **PASS** | wheel、Plugin、完整安装 payload 的候选身份与摘要见下一节；source worktree 记录为 clean |
| 基础／MCP 环境依赖检查 | **PASS** | builder、base、MCP 三个 pip check 均退出 0 |
| 独立安装态 MCP | **37 tests，0 skipped，0 failures，0 errors** | `installed-mcp-result.json`；以隔离解释器执行，产品模块从新 runtime site-packages 加载；不是当前客户端真实连接验收 |
| 首次安装态 S1 | **FAIL** | 完成 52 项检查、152 条命令后，在 `verify_installed.py:757` 的归档数量断言失败；详见第 4 节 |
| 工作区外原版安装态 S1 对照 | **PASS，94 项检查／292 条命令；251.35 秒** | 同一个 `4be98b8` wheel、原验收脚本和基础 runtime，在新的 `/tmp` 目录运行；没有观察注入或验收放宽 |
| GitHub Linux CI | **810 passed，1 skipped；364.56 秒；安装 94 项／292 条命令 PASS** | [准确 push/main run 35833475491](https://github.com/kongbu0621/infra-local-hand/actions/runs/35833475491)，checkout `4be98b8`；唯一跳过为真实 E3 |
| GitHub Windows CI | **211 passed，136 skipped；302.79 秒；安装 10 项／10 条命令 PASS** | 同一准确 push/main run；仅现有 S1 范围，不外推为 Windows A2 |
| 真实 systemd/cgroup、GX10、NAS | **未通过／未执行对应验收** | 合成 manager、scratch 文件和逻辑配额测试均不替代真实 OS／NAS 证据 |

Windows workflow 明确排除 `test_local_hand_jobs_*.py`、`test_local_hand_mcp_*.py` 和 `test_local_hand_plugin.py`，这些文件未收集，**不计入 136 项 skip**。136 项是已收集 S1／共享测试中的平台跳过，不能解释为对 A2 测试的 Windows 验证。

本次全量三项跳过的准确原因：

1. `test_local_hand_jobs_cli.py`：宿主策略禁止 AF_UNIX socket；合成传输测试另计。
2. `test_local_hand_jobs_integration.py`：宿主禁止真实 Unix maintenance socket。
3. `test_local_hand_jobs_runner.py`：`E3_SUPERVISION_UNVERIFIED`、PID 1 非 systemd、无预委派 manager admission、需要专用非 root 账户。

因此，本次 Unix transport 的宿主限制由本次原日志确认，不是从历史报告沿用；真正受监督进程集成仍跳过，不能算 PASS。

定向回归验证了 slot 一次消费、路径/inode 别名、独立根配额身份、准备中断／fsync／清理失败、两次启动围栏、helper 拒绝后的真实 broker 状态、回执丢失与预算损坏恢复、双 unit 独立观察／停止和 production factory 装配。namespace、cgroup 与 quota 的合成部分明确属于逻辑验证。

## 4. 首次安装态失败与后续处理

首次在当前工作区执行安装态 S1，完成 52 项检查、152 条命令后，`verify_installed.py:757` 要求 `len(residue_archives) == 1`，实际匹配到 **2 份相同 payload 的归档**，验证退出 1。此前命令退出码和输出捕获符合预期，不覆盖该失败断言。

两份归档均在第 152 条命令内登记，但 payload 的 inode 和 mtime 不同，一份保留更早 mtime。注入程序确认只注入一次；任务身份及枚举顺序没有随机性。另观察到 seed 中已经 `git rm`、commit、push 的文件再次可见且保留旧 mtime。由此怀疑工作区文件状态不稳定，但未获得能确定底层原因的证据，不能称为已证明的环境故障。

为追踪第二份文件而新建的独立诊断运行，在观察包装尚未触发前，又于原脚本第 477 行的延迟 push 标记断言失败，完成 32 项检查／104 条命令。该次没有提供归档来源的调用跟踪，不能作为最终验收 PASS。原始失败记录和静态复查结论均保留。

**准确提交的 GitHub Linux CI 独立安装验收已完成 94 项检查／292 条命令且通过，未重现上述失败。** PR 的旧 merge-run 也通过，但其 checkout 为 `f5b8c436b3ed9b4a063cd968b1d825ddfdfc960b`，虽然 Git tree 与本候选一致，仍单独记账，不代替准确 push/main 记录；PR Plugin 的来源提交与摘要也不用于本候选。

随后在工作区外新建 `/tmp` 隔离目录，使用原 `4be98b8` wheel、原 `verify_installed.py` 和同一个基础 runtime 完整执行；没有归档观察注入，**94 项检查／292 条命令通过，退出 0，251.35 秒**。这个结果与准确 CI 一致，但仅凭换目录后成功，仍不足以确定前两次工作区异常的底层原因。

没有修改 worker、安装验收脚本或归档数量断言，也没有删除失败现场。成功运行与失败运行分别记录，不能归并成“所有本地运行均通过”。

## 5. 本轮已生成产物

以下来自 `artifact-binding/stdout.log` 与首次构建汇总，均绑定源码 `4be98b8c03a4346d80d24663b0c655248b48e744`。

| 产物 | 大小／成员 | SHA-256 |
| --- | --- | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | 218035 字节；48 成员 | `734248908767c5a0d10a24f551956db3e8c3ecb33f53a8a095219afd0a0c0bde` |
| `local-hand-a2-plugin-0.1.0.zip` | 19218 字节；13 成员 | `09fa69c2b1d982914e69af7a7b8abb3fe873cbbbba70db9ad21f997eb1f24f10` |

完整四包 payload 共 42 个文件，digest 为 `5259568d843701ca5f53e9ac74862ae6157ca389c35ecf7e928e734ce4d050be`；安装前后 release 身份一致。它与 wheel 全字节摘要、旧 core digest 是不同指标，不混用。

Plugin 状态仍为 `UNCONFIGURED_E4_REQUIRED`。存在 Plugin ZIP 和安装态 MCP 测试通过，不表示当前网页已发现工具、完成 OAuth 或接到真实执行主机。

私有证据已封存为 `infra-local-hand-bootstrap-4be98b8-evidence-20260923.zip`：

- 大小：4665216 字节；6091 个 ZIP 成员，含 `MANIFEST.json`。
- ZIP SHA-256：`b86dd3a29bda2d14cc4b12ddefe276d46466abc19dce4078cd2ab33483c21154`。
- 内部 manifest SHA-256：`87d756a818ff8991b2bebeebf90d53085af5d1f41f1605c0982eb57d680be531`。
- 打包后检查 ZIP CRC、成员唯一性，并逐项复核 manifest 所列文件的长度和 SHA-256；外部 ZIP 摘要固定在本报告。
- 包含环境与命令记录、构建产物、准确源码结果、CI 日志与 API 元数据、两次失败现场及 `/tmp` 成功现场。FIFO 等特殊文件只留类型元数据，不打包为可执行特殊节点；不含虚拟环境、依赖 wheel 缓存、完整源码 worktree、私有 SOP 规则或历史。
- CI artifact 实体没有下载后重算；CI 上传日志/API 摘要属于元数据证据。上表本地 wheel、Plugin 和安装 payload 则已逐字节核验，不混淆两者。

公开仓库只保存脱敏结论；原始运行日志和合成测试现场不随公开报告上传。

## 6. 剩余门槛与准确结论

| 项目 | 当前结论 |
| --- | --- |
| 受监督启动准备代码 | 已接入实际 manager/factory 路径，具备隔离验证；从“未实现”推进到“实现待真实 E3 验收” |
| E1 整体 | **未完成**：NAS 硬配额 provider 仍缺失；`ledger.nas.roundtrip` 保持 UNSUPPORTED |
| 真实 E3 | **BLOCKED／未验收**：委派账户、真实 cgroup/namespace、硬配额、子孙进程、延迟启动、broker 崩溃及阻塞 I/O 需实测 |
| 正式 helper 结果读取 | 既有 `_inspect_unit` 仍在 observer 线程调用 `bounded_regular_bytes` 读取 helper 结果；字节上限不等于阻塞 I/O 的时间上限。本轮没有把它迁入另一受监督进程，也没有证明该路径阻塞时取消／停止始终可达 |
| 生产启用 | **仍拒绝**：`support()` 固定包含 `E3_SUPERVISION_UNVERIFIED`，没有配置开关把模拟验证提升为实机通过 |
| E4 当前客户端接入 | 未执行实际 OAuth、私有 MCP／Plugin 配置和文件交付验收 |
| E5／S2 实机切换 | 未安装或切换 GX10；S2 保持其独立 OPEN 状态 |
| E6 真实 NAS A2 | 未执行 GX10 → NAS → GX10；不以本轮合成证据代替 Ledger T01–T15 |

本轮已完成受监督启动准备的实现检查点，准确源码、安装态 MCP 及两平台 CI 验证通过。当前工作区的安装异常保留为未确定根因的失败记录，不据此放宽验收。下一实现优先处理 helper 结果读取的独立阻塞边界，再补 NAS 配额 provider，并在满足委派与配额条件的隔离主机完成真实 E3；本记录不扩大成 E1–E3 或 A2 完成声明。
