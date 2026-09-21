# S1 实施方案：抽取、参数化、独立打包

- Authority: Owner；Status: DRAFT / Documentation Gate OPEN。
- 输入源码提交: `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- 前置条件: Owner 对准确 R/A/S1 作出 closure，独立记录 C 后才写实现 D。当前文档不构成 closure。
- 目标: 形成新仓库可独立构建的通用候选包和公开审查材料，不变更现役服务、mailbox、SOP 主分支或 artifact-ledger。

## P01 有选择地抽取

按 [来源清单](SOURCE_SELECTION.json) 固定 Git blob 身份；实现开始时取回每个拟迁移文件，核对 blob 并补充原始字节 SHA-256。保留源代码归属及 notices；有独立第三方限制时先解决。新产品从干净历史开始，不复制 SOP Git 历史、私有 evidence 或机器状态。

迁入候选为 `tools/local_hand`（排除 `linux_cutover.py`）、`tools/local_hand_connect`、通用测试与 CI 中可复用的步骤。测试逐项移植，保留原断言目的；`test_local_hand_linux_cutover.py` 连同专用脚本留在私有来源。`tools/controlled_executor` 默认排除；若发现直接依赖，先报告并修订范围，不偷偷一并复制。原始实验/实机文档只作事实来源，产品说明重写。

## P02 配置和接口

新增共享配置模块，优先放在 `tools/local_hand/config.py`，由 worker、controller、bootstrap 和 acceptance 入口调用。以下是设计说明，当前不创建可执行 schema 或 runtime 配置。

| 配置位置/字段 | 具体规则 |
| --- | --- |
| Node Profile `profile_schema` | 新版固定标记 `local-hand-profile/v2`；旧版须显式转换并保存新文件 |
| `node_id`, `projects_root`, `repositories` | 保留现有行为和白名单；部署输入不得从 Task 推导 |
| `transport_policy.schema_version` | `local-hand-git-mailbox/v1` |
| `transport_policy.remote_url` | 一个明确 SSH URL；必须属于下面的准入集合 |
| `transport_policy.allowed_remote_urls` | 非空、去重、逐项语法校验；每个拼写指向同一准入 host/user/repository，拒绝混入第二目标 |
| `transport_policy.branch` | 显式完整 branch 名，按 Git ref 规则检查；禁止隐式旧分支回退 |
| `repositories.<name>.validations` | 每项固定非空 argv、有限 0 < timeout_seconds <= 3600、布尔 replay_safe；安装不再硬编码具体项目的 pytest 命令 |
| 安装绑定 | node/profile 路径、state/install 根、运行账户、服务/任务名、Git/SSH/Python/key/known_hosts 绝对路径；秘密仅引用，内容不入包 |
| controller marker | 接受的 remote、branch、transport 对象规范摘要及来源预期；漂移需重新准入 |

Worker 的 `--profile` 为配置权威。显式 `--mailbox-branch` 若保留为兼容 CLI 参数，必须与 profile 一致，否则启动前拒绝。controller 增加明确 policy 输入；保留 task build 的离线能力，submit/wait/call 必须读取已准入 marker。bootstrap 使用同一配置校验路径，不保留脚本内另一套常量名单。

对用户输入不做无提示的 host/path 归一化来扩大允许集合。保存准入的确切 remote 拼写；SSH scp 与 URI 两种拼写须明确列入后才接受。缺失、空、类型错误、null、未知新版配置键、冲突配置和不安全传输均在创建目录、账户或服务之前拒绝。新增配置解析还须拒绝 duplicate keys、NaN/Infinity 和将 bool 当数字的 timeout；这不宣称修复整个旧 Task/Result v1 的严格 JSON 边界。

原有 profile digest 原始字节算法和 Task/Result envelope 不变。旧 CLI/profile 的不兼容安装变化须文档化，不以静默默认制造“兼容”。

## P03 打包与来源

新增 `pyproject.toml`，distribution 名 `infra-local-hand`，首个候选版本 `0.1.0a1`；不上传 PyPI。保持 tools 下两个 Python 包，声明脚本/平台资源为 package data，控制台入口 `local-hand-worker` 与 `local-hand-connect` 对应原 main。build/test 依赖固定实际版本并记录解析清单；runtime 不安装 pytest/build 工具。

构建输入须是干净的既有实现提交，生成包内 `_build_metadata.json`，含源码提交、构建元数据格式版本及产品版本。构建后不可手改 wheel。安装使用新 venv，生成独立安装记录并核对 wheel SHA-256、核心摘要和配置摘要。已安装入口以包内元数据与安装绑定交叉校验，不调用外部 checkout 的 HEAD 证明自身版本。旧环境变量只可作为一致性检查，不能覆盖包内事实；不匹配拒绝。

分别验 source mode 与 installed mode。运行目录选择不包含项目源码的独立空目录，并记录 `sys.executable`、模块 `__file__` 和入口位置，证明没有靠 PYTHONPATH 或 cwd 偷用源码。执行 compileall、源码 pytest 及安装后协议/入口验收。生成物保存完整命令、退出码、日志及哈希。

## P04 验证矩阵与交付证据

| ID | 对应需求 / 架构 | 必需验证与失败信号 |
| --- | --- | --- |
| V01 | R01 / A01,A06 | 独立构建；源码外 runtime venv；wheel 内容检查；所有导入来自预期包；依赖 SOP 即失败 |
| V02 | R02 / A02,A03 | 两套 synthetic SSH policy/node/repository 配置通过同一入口；遗漏、重复键、未知键、NaN、非法 remote/ref、policy 漂移在持久变更前拒绝 |
| V03 | R03,R04 / A02 | 八动作、params 边界、顶层未知键、ID 长度、错 target、错 digest/action/node/provenance；task/result 尺寸上下界 |
| V04 | R05 / A04 | CAS 成功、stale、并发协作锁、single_writer=false；目录穿越、Windows aliases、NFC、symlink、.git 和 1 MiB 边界 |
| V05 | R06 / A04 | 固定 argv/no shell、清理继承环境、输出双流并发限额、timeout 进程树和退出码；清理不确定不能 PASS |
| V06 | R07 / A05 | 重复同任务、同 ID 异内容、崩溃收据、outbox 发布失败/重启、远端结果冲突；确认无盲目重执行 |
| V07 | R08 / A05 | clean commit→wheel→安装元数据→实际 runtime 对齐；篡改任一摘要/commit/binding 拒绝；验证 wheel digest 与 core digest 的覆盖差别 |
| V08 | R09 / A06 | Linux 和 Windows Python 3.12；PowerShell 7 bootstrap/runner exit；5.1 拒绝、路径预算/ACL、平台进程行为；缺平台标 UNVERIFIED |
| V09 | R10 / A01 | 公开候选逐文件清单、private tokens/用户名/路径/邮箱/证据扫描与人工复核；synthetic fixture 不误判成 live proof |
| V10 | R11,R12 / A05,A06 | 新 checkout/build/runtime 路径均唯一；保留失败产物；证据含实际命令、版本、开始结束、duration、exit、RSS 和日志摘要 |

Linux RSS 使用可用的原生 process/resource 计量，记录单位及进程树口径；Windows 用其原生可观测指标并注明不与 Linux max RSS 直接等价。不可用项为 UNAVAILABLE 并说明原因。对资源无回归数值预算的项目只报告实测，不编造达标阈值。测量日志含环境值时仅保留非敏感白名单；公开摘要与私有完整证据分开。

先运行继承的通用测试来固定抽取基线，再验证配置和 packaging 变化。失败按具体风险回溯，修复后重跑受影响项及相关链路；缺陷超出已批准架构时暂停该范围并更新文档。测试计数改变必须解释被移植、合并或排除的项，不用新数量掩盖覆盖丢失。

## P05 顺序、完成定义和后续入口

1. C 已记录后，在唯一新 checkout 中按 manifest 取源；保存上游 blob/字节摘要和旧断言映射。
2. 参数化共享准入、各入口、安装模板和 synthetic fixtures；先闭合 V02–V06。
3. 增加打包和来源绑定，构建新 wheel；完成 V01/V07/V10。
4. 运行 Linux/Windows 矩阵，修复具体失败并重验；缺 Windows 不结束跨平台验收。
5. 冻结候选 commit、wheel、文件摘要、命令证据和 V01–V10 结果；形成公开审查材料。

S1 完成不自动公开源代码或部署服务。发布还需 Owner 确认准确候选、许可证、公开内容和治理来源；无需等待这些决定才能完成本地可审查实现。公共摘要必须同时显示未通过/未执行项目。

S2 新方案列出平台、运行账户、精确项目 allowlist、mailbox 准入和 state/receipt 迁移办法，在新目录验收后再切换。已有环境及日志不删除。controller/worker 的配置变化必须成对处理，不能先覆盖现役一端。旧实例与新实例不可同时写同一目标。

S3 入口是 artifact-ledger `main` 合并提交 `6707a1b521c9c4718674620e6c584656bd434e4c` 和其 `docs/A2_RUNBOOK.md`。须先只读核对 runbook，再落实独立 checkout、build/runtime venv、wheel、源码测试、编译、A1/A2 资源专项及 ext4 本地闭环。当前节点的 allowlist 不包含该仓库，不能通过写脚本或借用现有 validation profile 偷渡。A2 的耗时/RSS、资源预算及实机文件系统证据属于该阶段，不由 S1 的合成测试代替。
