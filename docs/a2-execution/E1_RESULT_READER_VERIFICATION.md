# E1 受监督结果读取与 NAS 查询合同：实现验证记录

日期：2026-09-23。实现来源为 `95f65ddbab86ca358d12bda57a2a3e72e50639a3`；本报告由后续独立文档提交承载，不替代构建来源。

**本轮将 helper 结果文件读取移入第三个固定受监督进程，并完成 NAS 固定只读查询的构造与逻辑校验。候选仍不可部署。** 实际 NAS 查询没有启用；真实 E3、E4、E5/S2 和 E6 不由本轮模拟结果关闭。

## 1. 来源与范围

| 对象 | 准确身份 |
| --- | --- |
| 实现提交 | [`95f65ddbab86ca358d12bda57a2a3e72e50639a3`](https://github.com/kongbu0621/infra-local-hand/commit/95f65ddbab86ca358d12bda57a2a3e72e50639a3) |
| 实现 tree | `c513ff65042d6cde882c6e7898f4e7ad91538167` |
| 父提交 | `cf69c596b611d0eee2f478709bb2584e879f6704`，上一启动准备检查点的报告提交 |
| R / A / C | `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` / `79f73faedcd9cde4164b0d1625782dae27db6c2f` / `367632126c1930983a06b1854f63789448633148` |
| Owner 决定 | `LH-A2-EXEC-MCP-E1-E3-CLOSURE-20260922-01`；E1–E3 隔离实现与验证 |

本轮重新读取固定 R，源码 SHA-256 与既定 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5` 一致；实现是 C 的后代，三份权威文档与 A 逐字节一致。未增加第三方依赖，六类公开作业、七工具、旧 Task v1 八动作和固定 Ledger 调用不变。

本轮新增 55 个测试方法：结果协议／文件读取 13、broker／预算／库存 17、runner 生命周期 12、NAS 合同 13。另迁移两项已有 runner 回归到真实 reader 文件解析与匿名管道，保留原 fsync 失败后的业务结果语义和外来／非对象结果拒绝。测试数量属于测试方法，不等同于 55 项真实主机验收。

## 2. 实现与修正

| 边界 | 本轮行为 |
| --- | --- |
| 固定三阶段 | 带 `bootstrap_slots` 的新执行意图在首次交付前持久保存 `supervision_version=3`；bootstrap → helper → result_reader 各有确定 unit 名和独立 durable delivery intent，首次回执丢失也能推导完整库存 |
| 原预算 | 三 unit 共用原 phase 绝对截止，包含终止宽限；bootstrap／reader 各取 CPU 总额的向下取整三分之一，helper 取余额，不退款、不续额；不足以资助三 unit 时在消费 slot 前拒绝 |
| 启动围栏 | reader 只在原 helper 的 boot、unit、invocation、cgroup、无排队启动和递归树退出证明齐备后交付；重新核对取消、撤权、策略代次、资源租约、根分配及原预算 |
| 文件读取 | reader 内绑定准确根 FD 和固定文件名，核对单一普通文件、权限／属主、大小、inode、时间及前后命名绑定；正文上限 1 MiB。拒绝替换、变化、links、FIFO、非法 JSON、重复键、非有限数和超限复杂度 |
| 父端 IPC | observer 仅从匿名非阻塞 pipe 收 READY／RESULT 两帧，绑定原 reader/helper 身份；分 tick 和总量有界。完整帧不能替代 manager 退出证明；设置非阻塞失败后不尝试读取 |
| 取消与本地客户端 | `systemd-run --pipe` 可能在 reader 已退出后仍等待；不以其 poll 代替真实 unit ACK／退出，不因客户端仍活着而跳过停止 unit。unit 退出后独立清理本地客户端并收齐有界数据 |
| 恢复 | 只观察／停止三个原 unit，不自动重投、重读或重跑业务。管道丢失时业务结果保持 UNKNOWN；三原 unit 均完成退出观察后，监督状态可为 EXITED，保留启动已阻断／树已退出证明，本地 collectors_stopped 仍为 False，允许新的显式 reconcile |
| 旧布局 | 旧 v2 保持原两分 CPU，不补授 reader；legacy／v2 observer 不再直接访问结果存储，缺失业务证明保持 UNKNOWN |
| preflight 与状态 | preflight 进入 business 必须同时有成功退出与 `effects_checked=True`，拒绝矛盾证明；公开状态不暴露内部 bootstrap/helper 根分配和完成元数据 |

实现细节见 [SUPERVISED_BOOTSTRAP.md](SUPERVISED_BOOTSTRAP.md)。systemd 行为依据固定 v257 源码 `70bae7648f2c18010187c9cf20093155eaa26029` 的 [src/run/run.c](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/src/run/run.c)，不是本宿主真实集成 PASS。

恢复后的本地 pipe 客户端退出没有可持久证明，故 `collectors_stopped=False`，不能据此封存原任务、报告原业务成功或释放原屏障。客户端只是原请求的观察者；三原 unit 无排队启动且树为空的独立证明允许新显式核对。真实 E3 仍须验收 broker 崩溃后客户端残留、阻塞 I/O 与整个取消链的实际行为。

NAS 实现仅为 `smbcquotas-user-v1` 的两个固定只读请求、完整响应解析及身份／时间一致性校验。固定 Samba 4.23.0 源码表明“不支持 quota”可能退出 0，因此退出码不充当配额证据；有限**总硬上限**须落在 job NAS 预算内，不能以剩余空间代替。成功返回固定 `LOGIC_ONLY`、`business_authorized=false`；`execute_live_queries()` 无条件 UNSUPPORTED。完整依据、内部结构及缺口见 [NAS_QUOTA_ADMISSION.md](NAS_QUOTA_ADMISSION.md)。

## 3. 准确候选验证

各层结果互有覆盖，不能相加为总通过数。

[准确 push/main run 35842009312](https://github.com/kongbu0621/infra-local-hand/actions/runs/35842009312) 的 head 为 `95f65dd`，attempt 1，三个 job 全部 SUCCESS，无重跑。Linux 的唯一跳过为真实 E3；本地受限制的两项 Unix transport 测试在该 CI 中通过。

| 验证层 | 准确结果 | 边界 |
| --- | --- | --- |
| 完整源码 | **863 passed，3 skipped；358.14 秒** | 干净准确 worktree，前后 SHA/tree 一致 |
| 编译／shell 语法 | **PASS** | compileall、bash -n 退出 0 |
| 构建／产物绑定 | **PASS** | wheel、Plugin、44 文件 payload 对照准确 Git blobs |
| 安装态 S1 | **94 检查／292 命令 PASS；252.582 秒** | 原验收器单次运行，退出 0，完整捕获；新 `/tmp` fixture |
| 安装态 MCP | **37 tests，0 failure/error/skip** | 隔离解释器从全新 site-packages 导入；不是 E4 当前客户端连接 |
| 依赖与身份 | **PASS** | 三个环境 pip check；base/MCP 安装前后 release 身份一致 |
| Linux CI | **865 passed，1 skipped；355.84 秒；安装 94／292 PASS** | 准确 push/main，不借用 PR merge 或旧 run |
| Windows CI | **211 passed，136 skipped；436.07 秒；安装 10／10 PASS** | 既有 S1 范围；不外推 A2 |
| 真实 E3／NAS | **未验收** | production support 拒绝不变 |

本地完整源码准确结果为 **863 passed，3 skipped，358.14 秒**。三个跳过来自本次原日志：`test_local_hand_jobs_cli.py:745` 的 AF_UNIX 禁止、`test_local_hand_jobs_integration.py:298` 的真实 Unix maintenance socket 禁止，以及 `test_local_hand_jobs_runner.py:1173` 的真实 E3（`E3_SUPERVISION_UNVERIFIED`、PID 1 非 systemd、无预委派准入、需要专用非 root 账户）。这些跳过不计为 PASS。

Windows workflow 排除新 job/MCP/Plugin 测试文件，其未收集项不混入 S1 平台 skip 数；Windows S1 通过不表示 Windows A2 已实现。

开发过程中两项旧结果读取用例先因入口迁移失败，新用例另有 fixture 事务／字段预期错误，以及一次测试路径不存在的调用；修正后的最终结果另记，原日志或标明来源的工具输出摘录保留，不覆盖失败。没有降低断言来接受外来结果、放开无证明启动或把跳过改为通过。

首次最终构建因验证包装没有预建 `dist` 输出目录，Plugin 构建正确拒绝并退出 2；此时 wheel 与安装验证尚未开始。补建输出目录后使用独立记录继续同一准确源码，未修改产品或覆盖首次失败记录。

准确候选的构建、安装与验收命令均通过后，外层包装的原工作仓库 clean 检查发现并行新增的本报告草稿，退出 1。冻结的 source-build worktree 前后仍为准确 `95f65dd`／`c513ff65` 且 clean；另行核对命令记录与身份后确认候选验证通过，不重跑产品、不把该包装退出码改为 0。

安装态 S1 从一开始在新的 `/tmp` 隔离目录运行，使用冻结 wheel 和原验收脚本，无观察注入或断言放宽。上一检查点的工作区安装异常仍按 [原报告](E1_BOOTSTRAP_VERIFICATION.md)保留，本轮成功不证明其底层根因已修复。

## 4. 产物与私有证据

| 产物 | 字节／成员 | SHA-256 |
| --- | --- | --- |
| `infra_local_hand-0.2.0a1-py3-none-any.whl` | 231470 字节／50 成员 | `5df3306ba79a4d479c4712eb22f09753bf13f3e688be5de123a9ecd7426036bc` |
| `local-hand-a2-plugin-0.1.0.zip` | 19218 字节／13 成员 | `d2a8de7733169a1e2b7ebda2f683befd6c3e5a9b06eadf40ccaedb11a6ec5dd6` |

四包完整 payload 为 44 个文件，digest `fa9894ed1a883f853e0822b8948fdfb273e9bddcdae5293acca5ecf7e67609b5`；它与 wheel 文件全字节摘要是不同指标。固定 builder 复用，基础及 MCP 运行环境为本轮新建。Plugin 仍为 `UNCONFIGURED_E4_REQUIRED`，不是当前客户端连接验收。

私有证据包 `infra-local-hand-result-reader-95f65dd-evidence-20260923.zip` 已封存：

- 3048020 字节，3429 个 ZIP 成员，含 `MANIFEST.json`。
- ZIP SHA-256：`67e4cee7d74aa2c2b6889ca1ba5d35a69ee8262ba998de7864b236cd29cef431`。
- 内部 manifest SHA-256：`5af28e168b5db5dcca939fc7f931fe402edb371d34cb845af9ca68c8f74db042`。
- 已核验 ZIP CRC、成员唯一性，以及 manifest 中每个文件的字节数和 SHA-256。
- 包含准确源码运行、构建／安装、完整 CI 日志与 API 元数据、原失败记录和合成现场。FIFO、symlink 仅保留元数据；不包含虚拟环境、依赖缓存、完整源码 worktree 或私有 SOP 原文／历史。

公开仓库只保存脱敏实现结论及摘要；原始日志、合成现场和安装记录保存在私有证据包。CI artifact 上传日志/API 摘要只作为元数据，未将未下载重算的远端实体冒充本地逐字节核验的产物。

## 5. 剩余门槛

| 项目 | 当前结论 |
| --- | --- |
| helper 结果读取 | 独立受监督代码及故障逻辑已实现；真实 E3 未验收 |
| NAS 配额 provider | 固定查询与逻辑解析已实现；实际 collector、准确 writer SID、服务端计费域、凭据与限定网络仍缺准入和实现闭环，真实入口禁用 |
| E3 | `E3_SUPERVISION_UNVERIFIED` 保留；专用账户、真实委派 cgroup/namespace、本地硬配额、进程树、延迟启动、重启与阻塞 I/O 仍需隔离实机证据 |
| E4 / E5 / E6 | 未连接当前真实客户端，未切换 GX10，未执行真实 NAS 往返；S2 保持 OPEN |

下一步应冻结真实配额查询所需的服务端、写入身份、凭据和限定网络输入，并在具备委派与硬配额条件的隔离环境完成 E3。当前不通过配置开关启用生产，也不把本检查点写成 A2 可部署结论。
