# Q2 隔离实验 fixture 准备：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN**；scope：`LH-Q2-FIXTURE-PREP-v1`。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。
- 新 scope 关闭前只做文档、既有代码检查和可丢弃位置中的既有构建验证；不新增本 scope 的可执行脚本、测试、配置或 fixture。

## 当前目标和依赖

输入是已完成的 Q1 scoped 结论、一次私有只读报告、准确新候选和拟新增对象影响表。
报告仅提供旧 Q1 选择性事实，既不是完整域库存，也不是新 Q2 授权或准备回执。
新工具不再次要求用户逐项复制旧 Q1 诊断；Gate 关闭后集中完成代码、负例、实际准备和完整报告。

本批发现的旧 `q2_chain` 强制 store 别名 preflight root，真实 policy 要求 store 独立，真实 broker 从 policy 获取该 store。
该冲突的修复与真实 Policy 贯通验证是正式准备前置条件，见 [Q2 装配复核](../E3_QUOTA_Q2_ASSEMBLY_REVIEW.md)。
修复以同一 policy/installation 固定的独立 store 为权威，保留 alias 拒绝，并验证真实 policy 与三阶段装配共同通过。
该已批准 Q2 核心修复独立于本提案，不以放宽安全断言代替修复。

## 批次及落点

| 步骤 | 交付与职责 | 停止条件 |
| --- | --- | --- |
| F0 Gate 关闭 | 固定这三份文档为 A；Owner 对 R/A/scope 决定 B；独立登记 C | 没有准确 closure 不实施新准备行为 |
| F1 候选与私有计划 | `tests/e3_host/` 下的显式构建/准备入口及独立合同模块；固定 source/wheel/native/入口；生成可审阅的准确新对象计划 | 源码不干净、候选/构建不一致、缺少明确宿主输入即拒绝 |
| F2 一次准备 | 只在原隔离 guest 内创建新普通账户和实例级 manager 设置、五类独立执行父级、七 quota 根、新安装/state/journal/输出 | 名字/ID 冲突、旧对象重叠、工具/委派/容量不满足时保留一次完整报告，不自动换名字重做 |
| F3 装配与准入 | 从实际回执建立 policy、准确静态 fixture、所有派生 digest；集中做完整路径/安装/空账本/几何/容量检查 | 任一字段来自猜测或旧 Q1 复用、store 冲突、父权限不足均 BLOCKED |
| F4 原监督接续 | 新同 MainPID 绑定入口和外部原交付所有者；有限一次 `host.inspect` 操作；沿用 Q2 原三阶段实现及独立退出证据 | 不明交付、期限不足、原身份变化或捕获不全保留原失败，不启动替代操作 |
| F5 分层核验 | 公开脱敏准备报告/精确源码测试记录；私有完整准备、运行、外层停止和 seal | 准备结果不得标为 Q3/production；H01–H13 未完成项准确保留 |

F1–F4 的源文件只落在显式 test-only host 路径和必要的管理侧辅助模块，不放入默认 wheel 或 Plugin。
新增合同拟使用 `local-hand-q2-fixture-plan/v1`、`local-hand-q2-fixture-preparation/v1` 与单独的原监督入口声明；具体字段必须严格匹配架构表，拒绝未知字段和任意命令。
这些是设计名，不是现已创建的运行 schema。普通业务请求固定 `host.inspect`、空 inputs、新 operation；不给用户传任意 shell 的入口。

## 一次准备的准确顺序

1. 固定 clean source 与工具字节；已有构建命令在独立输出位置生成 wheel，核对 metadata 和完整内容；安装、native 编译和检查全部限定该候选。
2. 在 guest 做有界预检：明确身份、初始 namespace、准确已有文件系统与 free/retained 关系、工具/ABI、名字和 project 未使用、旧记录边界、新路径不重叠、资源可容纳。缺一项时先停止，不做部分“碰运气”安装。
3. 持久保存 preparation ID、输入摘要、全部预期动作及原 finite envelope；用新路径 create-only 建日志/状态，不修改旧记录。
4. 新增一个无登录用途的普通账户和主组；不用旧 Q1 UID/GID。为该 UID 运行期启动准确 user manager，使用实例级委派设置和受限普通子 slice；不改模板、不启用 linger，不为现有用户扩权。
5. 准备 root query、management、controller、supervisor 父 slice 以及 ordinary 子 slice。每个对象实际 device/inode、父级关系、有效资源限制和空状态写入回执。
6. 在既有 quota 文件系统中创建两组三根和独立 store，分配七个未使用的新 project，设置继承及逐域硬限制；逐项保存真实身份与管理查询结果。不得重格式化、重挂载或修改任一旧域。
7. 在新受保护代码路径安装固定 wheel/管理程序；普通账户可访问的只读代码父路径与私有普通 state 分离。创建新普通空 ledger、管理 journal 和独立空输出/声明目录，记录身份及有限保留费用。
8. 依据真实回执生成静态 policy/fixture；同一 source、installation、authority、epoch、operation、两 slot 和独立 store 必须相符。未来 phase grant 仍由实际原 broker reservation 派生，装配器不先发行。
9. 准备完全成功输出 `PREPARED`。原交付所有者另记录本次唯一启动意图、issued/deadline/费用并交付同 PID 入口，核对一次完整原运行及独立停止。步骤 9 的执行结果与准备结果分别封存。

准备器和入口均有 no-argument BLOCKED 模式。单次调用的目标是保存完整结构化报告与原输出，不需要用户根据某个失败行手工删除文件再重跑。
首次 syscall、文件创建、manager 调用发生后，失败保留该 preparation 的已完成边界；只读复核可以再运行，产生副作用的接续必须先证明原意图和准确未交付步骤。

## 预算与运行约束

七 project 的硬限制合计不超过需求中 448 MiB/28672 inode；每个实际值在计划中固定，不把该上限全部默认分给作业。
对一个固定 `host.inspect` 的普通预算，应满足既有 `Policy` 的 reservation/temporary/log 关系、每阶段根去重费用、evidence 四角色和原总 deadline。
准备容量还须单列新安装/构建暂存、普通 state、root journal、管理捕获/声明及外部所有者的有限开销，均在需求所列上界内。
现有 120 秒 supervisor 上限保持；内部 target 和 phase 时限必须留出 manager 调用、原 StopUnit、完整 EOF、fsync 和 seal 的费用。
原管理会话预先固定外部所有者的有限预算并记录其实际退出及双流 EOF；外部所有者不证明自己的退出，不临时新建一层监督者来补缺失证明。
预检后空间变化、块开销超出或任何期限不足时拒绝，不能延长总时限、退款或清理旧 Q1 文件。

## 风险对应验证

| 风险 | 必须的验证 |
| --- | --- |
| 错宿主或旧 Q1 对象误入准备 | 错 boot/namespace/文件系统、别名、symlink/hardlink、既有名字/project、旧路径重叠均在变更前拒绝；旧记录摘要保持 |
| 普通运行权限和安装不匹配 | 同一候选 wheel 构建/安装检查，正常缓存可读；private ancestor、额外包、错 source、解释器变化拒绝；真实普通身份启动检查 |
| 准备名义通过但无 service 委派 | 正确 user@UID service、错误 slice-only Delegate、缺控制器和错误父级负例；实际 manager/cgroup 记录 |
| 配额身份/继承或 store 冲突 | 7 域真实管理查询与根身份；两 slot/独立 store 合同共同验证；错误 project、共享旧域、继承改变、别名与不足预算负例 |
| 半完成准备被重放 | 在账户、project、账本、配置和 manager 操作边界注入失败；保留原回执、对象和意图；重复执行不得覆盖或另建替代对象 |
| 原监督身份与期限刷新 | 不同 MainPID/InvocationID/cgroup、过期 envelope、独立前检退出后复用、重新启动均拒绝；同 PID 原接续和原双流验证 |
| 假退出或假准备/验收 | 超时、client 非零、缺 EOF、待处理 job、父级不空、seal 缺失分别保留；PREPARED 不等于运行完成，运行完成不等于 Q3 |

源码验证在准确 committed candidate 上执行；模型测试、真实文件/管道、真实宿主准备和实际 Q2 结果分列。
普通 discovery 不运行 host 准备；实机只走显式计划和原有管理入口。无需为了这个准备 scope 重跑 Q1 查询或覆盖 slot004 历史结果。

## 完成定义与后续

完成交付是：固定构建和工具、一次可审阅影响计划、新对象实际准备回执、准确私有 fixture、原监督接续及外层退出材料、失败保留路径和公开脱敏验证记录。
若真实运行尚未发生，只报告 PREPARED/BLOCKED，不把代码测试补作实机结果。
后续 H01–H13 正常链/故障验收沿用原已批准实现计划；本次不自动宣告 Q2 全部负例、Q3、E4–E6 或生产完成。
默认保留新账户、限额和证据；准确停止本次运行可以执行，删除与回收需另有明确任务，不能用“回滚”抹去永久消费记录。
