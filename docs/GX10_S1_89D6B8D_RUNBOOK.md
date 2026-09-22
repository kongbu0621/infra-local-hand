# GX10 S1：89d6b8d 隔离实机复验任务

本任务交给 **GX10 上的本地 Codex** 执行。Owner 已要求进入本轮 S1 隔离实机复验；当前云端没有 GX10 shell、SSH 或 Local Hand 执行通道，发布任务书不表示实机命令已经执行。

范围为已批准的 S1：在 GX10 Linux/aarch64 上新建隔离 checkout、build/runtime venv 和证据目录，完成源码、编译、构建、安装态验证及独立证据核对。现役服务、旧 checkout、旧 venv 和旧证据全部保留；不提交现役任务，不切换服务，不执行 S2 或 artifact-ledger A2。Windows 延后。

## 固定输入与适用关系

| 对象 | 准确输入 |
| --- | --- |
| Public 仓库 | `https://github.com/kongbu0621/infra-local-hand.git` |
| 云端复核记录基线 H | `d2e0ef2489cfbe3441b84a20e13bd3d729d81f0e` |
| 产品候选 D | `89d6b8d807287396d4bac102d5fa8057558c3c7e` |
| 产品 tree | `487136f7887e8525145a56129868ed549e68748f` |
| Gate 规则 R | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` |
| 三文档 A | `7246b850ffdc2709e359b09cac99f0fb88bda209` |
| 独立 CLOSED 记录 C | `48730d037a1d5c50e8380a60d5b8399e90e1e01c` |
| 云端参考，不能当实机结果 | 297 passed / 0 skipped；安装态 93 checks / 291 commands |

读取交接仓库的 `AGENTS.md`、本任务书、H 中的 `docs/S1_RESULT_ENCODING_REVIEW.md` 及既有 `docs/GX10_S1_RUNBOOK.md`；保留准确文档提交和文件摘要。继续读取 AGENTS 指定的 Private companion 固定原始规则，核对完整性及 S1 关闭证据；公开节录未获等价采纳。

本任务具体化 H 已记录的后续复验输入。**本轮构建 D，不构建最新 main，也不回到旧任务书的 b763bd6。** 旧任务书的“恰为 7 个提交”、139 项源码测试和 25 checks / 66 commands 是历史统计，本轮不用它们作断言。旧任务书的其他隔离、记录、失败保留及不触碰现役服务要求继续适用；本任务不修改 R/A/C 或扩大授权范围。

## 执行顺序

1. **确认真实主机。** 只读记录 hostname、uname、架构、OS、Python/Git/SSH 版本、磁盘及拟用目录文件系统。必须确认当前终端是目标 GX10、Linux/aarch64；身份不符时报告并停止实机流程。选择本机已有 Python 3.12，不覆盖系统 Python。实际身份与路径只保留在私有证据中。
2. **识别现役服务。** 只读识别实际承载 Worker 的 systemd unit，记录 active/enabled、MainPID、启动时间、unit 与运行配置摘要。历史账户名或历史 unit 名不能代替当前识别；不操作历史 PID，不停止、重启或替换服务。权限不足记录 UNAVAILABLE，不扩大权限。
3. **准备唯一目录与记录器。** 遵循本机既有 works/projects、works/venvs 和私有 evidence 布局；为 checkout、build venv、runtime venv、dist、安装 fixture 分别生成包含候选简称和唯一运行 ID 的新路径，存在即拒绝。明确所选目录是否受同步程序或网络文件系统影响；不修改同步服务或挂载配置。按旧任务书先准备外围命令记录器，再执行正式命令。
4. **取得准确源码。** 可从已更新的 Public 仓库执行 `git clone --no-hardlinks <本机仓库绝对路径> <新checkout>`，在新 checkout 执行 `git checkout --detach 89d6b8d807287396d4bac102d5fa8057558c3c7e`。核对 HEAD、tree、clean 状态与 `git fsck --full`；验证 C 是 D 的祖先，保留完整修复历史。逐字节比较三份批准文档与 A，不能修改批准文档。
5. **新建 build venv。** 按 D 的 `requirements-build.txt` 安装固定工具版本并保存完整日志、pip list/freeze 和 Python 路径。注意文件指定 `build==1.2.2.post1`；前轮云端实际使用 `build==1.3.0`，本轮应按候选文件执行并如实记录差异，不能照搬云端 venv 或改写历史版本记录。
6. **源码验证。** 用 build Python 运行完整 `-m pytest -q`、`-m compileall -q tools tests setup.py`；运行 `bash -n tools/local_hand/bootstrap_linux.sh`。逐项记录真实数量、失败、跳过、警告、退出码、耗时和 RSS。297/0 是云端参考，不能将平台差异改写成 PASS。
7. **本机独立构建安装。** 用 build Python 执行 `-m build --wheel --no-isolation --outdir <新dist>`，记录 wheel 摘要、成员、构建元数据及载荷摘要，`source_commit` 必须为 D。创建另一全新 runtime venv，用 runtime Python 执行 `-m pip install --no-index --no-deps <本机新wheel>` 和 `-m pip check`。runtime 只包含 pip 和产品包；不安装测试或构建依赖，不手改 wheel。允许 ZIP 元数据使整体包摘要与云端不同，必须解释来源与载荷一致性。
8. **运行源码外安装态闭环。** cwd 切到私有证据根，执行下面命令，所有路径均替换为本轮真实绝对路径：

   ```text
   <runtime-python> -I <新checkout>/tools/verify_installed.py --wheel <本机新wheel> --run-root <新acceptance-root>
   ```

   必须完成全部检查并取得最终 `report.json`。93 checks / 291 commands 是参考；缺报告、捕获不全、摘要变化、非预期退出码都不能算完整通过。该程序使用合成本地 Git/SSH fixture，不使用现役凭据或现役项目；`physical_node_tested=false` 保持其既有范围语义，在外围报告另行证明程序实际运行于 GX10，不能伪装为现役服务验收。
9. **独立核对。** 从实际文件重算每条命令 stdout/stderr 摘要，核对 capture_complete、预期/实际退出码、报告聚合与 Result 业务状态。命令退出码 0 不自动代表业务 succeeded。交叉核对 D 的 Git blob、wheel 文件、构建元数据、安装文件/RECORD、实际模块与 console 路径、profile/安装实例身份及持久收据。确认 checkout 仍 clean。
10. **现役前后对比与交付。** 再取只读服务快照，解释前后变化，不仅凭 PID 判断因果。在私有 evidence 根生成中文报告、完整 evidence ZIP 和摘要，报告完整输入/实际候选、主机证据、逐项结果、命令日志、版本、耗时/RSS、wheel/安装身份、失败与修复轮次、未决项及下一阶段入口。对外提供非敏感摘要和本地证据绝对路径；不把原始机器证据、凭据、规则全文或私有历史提交到 Public 仓库。

## 本轮必须保留的观察

前轮云端两次 outbox 残留的原始时序和根因仍未确定；最终隔离通过及后续诊断成功不关闭归因。

- 核对投递超时恢复 LH9995 与读取故障恢复 LH9804：成功结果确认后 pending 是否删除，重复轮询是否保持业务文件、receipt 和远端 Result 不变。
- 核对新增 Result 编码链路 LH1020–LH1022：原始异常 Result/receipt/outbox 字节保留，错误状态与冲突屏障正确，后续健康 CAS 成功，再次轮询不重放。
- 再出现残留时，先冻结原始目录状态、文件字节与摘要、命令时序和当前相关进程观察，再在明确区分的诊断轮次中调查；不能直接删除 pending、降低断言或用后续 PASS 覆盖失败。证据不足时保留 UNRESOLVED。

在既有 S1 范围内确认缺陷后直接修复，保留原失败与 diff，形成新的干净候选，并使用新 build/runtime/output 目录重新构建验证；准确区分原 D 与修复后候选。若触及需求、架构、权限、阶段范围或既有服务，则先报告具体边界问题。运行中断时记录 INCOMPLETE，不能补造最终退出码或验收报告。

完成实机复验后提交结果供核对。本任务本身不关闭 S2/A2，不批准现役服务切换。
