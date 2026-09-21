# GX10 S1：从 Git 仓库完成本机验收

Owner 已要求 Windows 延后、先运行 GX10。本轮执行已授权的 S1 Linux/aarch64 隔离构建、wheel 安装和验证；Windows 保持 DEFERRED / UNVERIFIED。先完成本轮，再以实际结果衔接 S2 服务切换和 artifact-ledger A2。

给 GX10 本地 Codex：读取本文件后立即执行，有具体问题直接修复并复验，不只输出计划。保留已有 checkout、venv、服务和全部证据。新建目录均须唯一，存在即拒绝；失败产物不得覆盖或删除。不要把隔离 fixture 通过写成现役服务通过。

## 固定输入

| 对象 | 完整身份 |
| --- | --- |
| Public 仓库 | `https://github.com/kongbu0621/infra-local-hand.git` |
| 规则 R（Private companion） | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 已批准三文档 A | `7246b850ffdc2709e359b09cac99f0fb88bda209` |
| 独立 CLOSED 记录 C | `48730d037a1d5c50e8380a60d5b8399e90e1e01c` |
| 本轮产品候选 D | `b763bd6714721d22278086db559fa3f6684aad7b` |
| D 的 Git tree | `0dbf04548f42bbb3693524ae5bd8adedeecd2de1` |

先读取 main 的 `AGENTS.md`、`docs/governance/PUBLICATION_OWNER_DECISION.md` 和本文件，并记录交接 main 的完整 SHA。公开决定仅批准候选和治理摘录的披露，未把摘录变成已采用规则。继续读取 AGENTS 指定的固定原始规则；可只读使用本机已有 SOP checkout 的准确 Git object。不得把 SOP 历史、源规则全文或实机证据提交到本 Public 仓库。

main 的后续文档状态说明不会改变本轮产品输入：**必须构建准确 D，不直接拿最新 main 代替。** 本仓库包含完整 D 及其 A/C/D 历史，无需下载交接 ZIP 或从包外恢复源码。

## 目录与证据

采用本机既有 works 布局：projects 下新 checkout，venvs 下分别新建 build/runtime 环境，data 下建立本次私有证据根。先确认真实绝对路径，再生成 UTC 时间加随机后缀的运行 ID。不得把示例路径当成自动准入的运行配置。

在执行验收命令之前，先在证据根准备外围命令记录器。它不进入产品源码或 wheel。每条命令至少保留：完整 argv、cwd、非敏感显式环境白名单、UTC 开始/结束、单调时钟耗时、退出码和预期退出码、timeout 状态、stdout/stderr 原始字节及 SHA-256、RSS 数值/单位/口径。Linux 可使用 wait4 的 ru_maxrss 或 `/usr/bin/time -v`；记录其为峰值 RSS（KiB），不能称同时进程树总内存。无法测量时记录 UNAVAILABLE 和原因，不填零冒充实测。

命令与证据目录 create-only。日志必须完成捕获后再计算摘要，验收结束独立重新读取文件核对；日志不完整或摘要变化即失败，保留原记录。网络安装失败、超时和预计拒绝的负向用例分别记录，不能把所有非零退出码一概写成 PASS 或 FAIL。配置、机器身份和实际路径保存在本机私有证据中，公开摘要使用必要的聚合结果。

## 执行顺序

1. **主机确认。** 记录实际 hostname、uname、architecture、OS、Python/Git/SSH 版本、磁盘空间、所选目录的文件系统。确认是目标 GX10、Linux/aarch64 和 Python 3.12。不要套用云端版本信息；缺少 Python/venv 时报告实际缺项，不覆盖系统 Python。
2. **现役只读快照。** 识别实际承载现役 worker 的 systemd unit，再记录 active/enabled、MainPID、启动时间与 unit 摘要。账户名称不能代替 unit 名称。权限不足记 UNAVAILABLE；本轮不停止、重启或替换服务，也不扩大权限。
3. **新 checkout。** 从已克隆的 Public 仓库创建 `git clone --no-hardlinks <repository-absolute-path> <new-checkout>`，然后在新 checkout 执行 `git checkout --detach b763bd6714721d22278086db559fa3f6684aad7b`。用完整 SHA 核对 HEAD、tree、clean 状态及 `git fsck --full`。保留 main 的任务书和公开决定副本到本次证据根。
4. **来源复核。** 验证 A、C、D 存在，C 是 D 的祖先；D 的独立历史恰为 7 个提交。逐字节比较 D 与 A 中的 `docs/REQUIREMENTS.md`、`docs/ARCHITECTURE.md`、`docs/IMPLEMENTATION_PLAN.md`，不得修改这些批准文档。读取 D 的使用说明和 S1 实现说明。
5. **build venv。** 使用本机 Python 3.12 创建唯一新 build venv，按 D 的 `requirements-build.txt` 安装固定工具版本。保存 pip list/freeze、Python 路径与所有安装日志。不得复用任何已有 venv。
6. **源码测试。** 在 D 的 checkout 用 build Python 运行 `-m pytest -q`，云端参考为 139 项。随后运行 `-m compileall -q tools tests setup.py` 和 `bash -n tools/local_hand/bootstrap_linux.sh`。实际数量、失败、跳过、warning 和耗时/RSS均入证据；差异要解释。
7. **本机 wheel。** 用 build Python 执行 `-m build --wheel --no-isolation --outdir <new-dist>`。记录 wheel SHA-256、大小、文件列表与包内 `_build_metadata.json`，其中源码提交必须为 D。构建器校验载荷集合及 Git blob；构建后不得手改 wheel。ZIP 时间可能使本机 wheel 整体摘要不同于云端参考，判定依据为准确源码/版本/载荷，不强求二进制包整体 hash 相同。
8. **runtime venv。** 创建另一唯一新 runtime venv，用其 Python 运行 `-m pip install --no-index --no-deps <new-wheel>`。确认只包含 pip 和产品包；runtime 不安装 pytest、build 或其它构建依赖。
9. **源码外安装态闭环。** cwd 切到证据根，用 runtime Python 执行：

   ```text
   <runtime-python> -I <new-checkout>/tools/verify_installed.py --wheel <new-wheel> --run-root <new-acceptance-root>
   ```

   Linux 参考为 25 项检查、66 条子命令，覆盖八动作、两个 console 入口、Git mailbox 往返、CAS stale、重复任务、错节点、安装 create-only 与来源篡改拒绝。该测试使用隔离本地 SSH fixture，不使用现役凭据、不写现役项目。`physical_node_tested=false` 是该测试入口的既有范围标记，不得手改；报告另行说明测试实际运行于 GX10，但未验收新现役服务。
10. **独立复核。** 复查所有 command.json 的预期/实际退出码、capture_complete、stdout/stderr 摘要及报告聚合结果。确认实际模块与 console 路径来自本次 runtime venv，wheel 元数据为 D；profile、package、安装记录摘要分别对应本次实例。检查源码仍 clean。
11. **现役前后比对。** 再取只读 service/进程快照并与前态比较。记录发现的变化及原因，不能仅凭 PID 是否变化推断本次进行了部署。
12. **交付。** 在私有证据根生成中文报告和 evidence ZIP：准确输入与实际执行 commit、主机/版本/文件系统、每项结果、测试计数、命令/日志/摘要、耗时/RSS、wheel/安装信息、失败与修复轮次。明确 Windows 状态、新版服务尚未切换、artifact-ledger A2 尚未执行。

发现已授权 S1 范围内缺陷时直接修复，保留失败证据和 diff，形成新的干净修复提交，并为该轮创建新 build/runtime venv 和输出目录重新构建验证。不能把新提交称为原 D；原始 D 与修复后候选的结果分开。若需要改变已批准需求、架构或扩大权限/阶段范围，先报告具体范围问题。

## 下一阶段

本轮 PASS 后形成基于实机事实的 S2 切换方案：核对 profile/mailbox 准入、运行账户、项目白名单、state/receipts、未决任务、单 writer、切换和回滚条件。不要把合成 fixture 配置覆盖到现役服务。

artifact-ledger A2 的既定输入为 `6707a1b521c9c4718674620e6c584656bd434e4c` 与该提交的 `docs/A2_RUNBOOK.md`。届时单独执行其 checkout/build/runtime/wheel、源码测试/编译、A1/A2 资源专项与 ext4 正向闭环；不得用 Local Hand S1 的隔离测试替代 A2 实机证据。
