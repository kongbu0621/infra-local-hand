# E3 配额机制与真实 harness：实施方案

- Authority：Owner；状态：PROPOSED / Gate OPEN；scope：`LH-E3-QUOTA-HARNESS-v1`。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。
- 起点源码/交接 `5257f42d1358be67b6d13377d99ef3465131bd54`；
  原批准 A、R、C 见根 AGENTS。本提案提交只有文档，不是 closure C 或实现 D。

## 实施顺序与停止点

| 步骤 | 具体交付 | 通过后才进入 |
| --- | --- | --- |
| Q0 变更基线 | 三份文档、范围与准确 A；Owner 对 R/A/scope 的决定；独立 CLOSED 登记 C | 新权限组件、接口和 test-only 入口编码 |
| Q1 准确查询与最小权限 | 独立管理侧查询器和 syscall/errno 记录；固定 ABI、FS/root/project、enforcement；在既有隔离 fixture 验证“原普通身份结果”和“管理侧结果” | 后续 quota 接口整合；若管理权限、ABI 或稳定绑定不成立，暂停而非降级 |
| Q2 接口、绑定和预算 | 有界 local protocol、peer/manifest 校验、请求持久防重、generation/epoch、原 deadline 与容量、观察进程退出证明；普通 bootstrap 验根和消费事实 | 真实业务阶段链；先通过身份、陈旧事实、响应丢失、超限写入和阻塞负例 |
| Q3 最小真实 harness | 准确私有 fixture 与源码/wheel/observer/harness manifest；同一 broker 核心，真实 bootstrap/helper/reader；H01–H05 | 后续故障；没有 systemd/专用身份/真实 quota 则实机部分 BLOCKED |
| Q4 故障与恢复 | H06–H13 的准确注入点、双账本/所有 unit/collector 证据、独立停止及保留；共享核心改动的旧 v1/v3 回归 | 准确新候选的完整隔离验收与独立复审 |
| Q5 候选评审 | 分列源码、安装、合成、实际 FS 和真实三单元结果；审阅所有未覆盖项与支持资格 | 另行决定支持声明；不自动进入 E4、E5/S2 或 E6 |

Q1 的真实 fixture 若尚未交付，可完成源码和合成负例，但 Q1 实测仍 BLOCKED，不能假设成功跳到 Q3。
主机准备与代码开发分开：先给出准确代码和装配清单，再由已有管理入口确认并准备实际对象。
不继续让当前 GX10 会话反复读同样的库存；它已提交 NOT_PREPARED 的有效结果。

## 代码与产物落点（批准后）

| 拟议落点 | 职责及依赖 |
| --- | --- |
| `tools/local_hand_jobs/quota_contract.py` | 严格逻辑协议和版本、限额、绑定；不导入管理权限实现 |
| `tools/local_hand_jobs/quota_client.py` | 原 bootstrap 内有界客户端和 server peer/receipt 验证；不得传任意路径或 FD |
| `tools/admin/local_hand_quota_observer/` | 独立管理侧服务、固定对象映射、请求账本、受监督查询；可选平台 ABI 适配器单独固定；不打进默认 wheel 或 Plugin |
| `tools/local_hand_jobs/runner.py`、`bootstrap.py`、`bootstrap_roots.py` | 分离当前根身份检查与 host quota 查询；准确 receipt/版本绑定、持久意图和预算；生产资格封堵保留 |
| `tools/local_hand_jobs/state.py` 等实际相关模块 | 只在需要时增加有版本的观察引用/内部 receipt 字段；保留旧事件语义，禁止迁移时启动工作 |
| `tests/e3_host/` | test-only 准入、真实 manager/三单元场景、固定负载与观察、失败保存；默认 discovery 不产生主机变化 |
| `tests/test_local_hand_jobs_*.py` 与管理侧专项 | 真实风险对应的严格解码、冒用/替换、恢复、错预算、超限和非零 errno 负例 |

依赖方向：bootstrap → 无特权 client/contract；observer → 同版本 contract + 管理侧实现；
共享生产核心不依赖 tests/admin。host 管理产物单独版本/摘要/依赖清单。
不新增第三方运行依赖来处理密码学或通用 RPC；如证据迫使改变选型或权限边界，先更新设计。
不得提前创建上述空模块、可执行骨架、运行配置或新依赖来代替 Q0。

## 私有 fixture 装配清单

装配交接必须给出准确候选及构建摘要、专用测试实例/UID、有效 user manager 与委派关系、
预建 slice/cgroup、独立本地 FS 和有限 project/slot、控制账本与证据容量、observer 的受信身份及
固定 roots 映射、有限预算和 socket 可见性、管理员修改围栏、日志位置、保留策略及逐项停止/解除方法。
每个真实字段都来自管理侧交付；代码中的示例值不能自动指定为 GX10 实际值。
Delegate 的实际位置按 service/scope 委派关系核对，不能只给 slice 写一个 Delegate 属性。
需要修改 GX10 对象时，另给准确影响清单后才能实施；此次只请求开发与已交付 fixture 上的隔离测试。

第一验证环境优先采用可独立回收的测试实例，与编辑器/S1 服务/旧 state/mailbox/真实 NAS 无重叠。
阻塞故障须有可解除的独立存储 fixture；没有则 H08/H09 BLOCKED。
如果确需重新准备测试实例，先保留旧失败及原停止证据，不把新实例当作原未知操作的继续或成功重试。

## 验收映射

| 需求 | 必须出现的证据 |
| --- | --- |
| R01/R02 | 普通三单元有效 UID/capability/namespaces；observer 准确权限及固定接口；错 peer、任意字段、路径/FD、设置动作被拒绝 |
| R03 | 请求/receipt/原分配/预算绑定；旧 boot/epoch/generation、过期、错 root、mount 别名、被替换 endpoint/manifest、回执重放均拒绝；每个 syscall 立即保存 errno |
| R04 | 有限合成写入触发真实硬配额拒绝；计费域唯一与共享域去重、总峰值上限；project/继承变更及域外写入负例；仅有 ENOSPC 不等于已证明 quota enforcement |
| R05 | listener/broker 有限响应、query 原身份和实际停止；意图/交付/ACK 崩溃、延迟启动、取消、重启；未知继续占用且不派生替代工作 |
| R06/R07 | [H01–H13](../E3_HOST_ACCEPTANCE_RUNBOOK.md) 分项真实结果；Q1 原单元权限诊断与新机制证据分别记录；H03 原“单元内查 quota”要求随本变更拆成单元验根与管理侧查询，不悄悄删除 |

每个场景保存候选与 fixture 身份、命令/版本/时间/原退出码、stdout/stderr、事件与进程身份、
quota 和 namespace 事实、资源计数、停止状态、完整/部分结果及 manifest/ZIP/seal。
管理侧原始记录可能包含私有主机事实，继续私有保存；Public 只写脱敏结论和摘要。
mock 是协议/恢复逻辑证据，不能覆盖真实调用或实机场景。编译/CI 通过不改变 Gate 或部署权限。

## 兼容、回退与当前交付

保持旧 Task v1、MCP/CLI 契约和不理解新 receipt 时的拒绝行为。管理服务未安装或无权限时明确
UNSUPPORTED/BLOCKED；不回退到旧普通 quota 查询并称成功，不自动设 quota、不切 root 运行作业。
中止开发可保留当前固定封堵版本；已发生真实测试则先按准确身份停止/核对并封存原记录。
回退不删除 observer 请求记录、broker 事件、已消费 slot 或失败现场。

本轮交付为已核验输入、可审阅设计和准确变更基线。没有新增运行源码、部署配置、fixture 实例、
管理服务或实机验收结果；生产候选仍不可部署。
