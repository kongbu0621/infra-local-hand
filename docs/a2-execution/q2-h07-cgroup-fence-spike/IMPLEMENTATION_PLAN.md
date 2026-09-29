# H07 受控进程子树原语实验：实施方案

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- Scope：`LH-Q2-H07-CGROUP-FENCE-SPIKE-v1`，仅 F1–F4。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本方案。
- R、输入基线与历史链保持；准确 A/B/独立 C 前不创建实验 source、测试或 workflow。

## 文件与阶段

| 阶段 | 具体交付 | 准入与完成条件 |
| --- | --- | --- |
| F1 | `tests/e3_host/spikes/q2_cgroup_fence/` 内固定 C11 helper、fixture capability 记录；独立 `.github/workflows/q2-cgroup-fence-spike.yml` | 从独立 C 开始；不用 apt/pip 下载新依赖，记录现成 cc/Python/kernel/image；无准确权限/API/限额就 UNSUPPORTED |
| F2 | 同目录的固定控制帧、原 pidfd/FD 生命周期、G/S/W 状态及截止；仅定向非特权解析测试 | 有界输入、拒绝降级、原 clock/epoch 不可刷新；不触碰原 Q2 入口和包 |
| F3 | 准确 D 上六个固定实际病例；同目录收件验证器 | 实例身份、关门、tree、EOF、guardian 退出分别有证据；负例保留原失败与缺项 |
| F4 | `docs/a2-execution/evidence/q2-h07-cgroup-fence-spike/` 下脱敏结果、源码/工具/原件摘要与评审 | 只报告 fixture 能力，明确未运行/失败/资格通过；不生成原 Q2 READY |

测试源码可用已有 Python 3.12/pytest 做严格收件验证；实际进程创建/封闭由 C helper
执行，禁止用 Python ctypes 冒险跨 fork/clone 多线程解释器状态。C 编译 C11 并启用
警告，源码及二进制摘要进入记录。行为接口仅固定枚举，不接受任意命令。
具体文件拆分可按职责调整，但不得新增生产后端、依赖或自动重试入口。

## CI 与 fixture 顺序

workflow 只含 `workflow_dispatch`，`permissions: contents: read`，checkout
沿用已有固定 action SHA，`persist-credentials: false`。使用 `ubuntu-24.04` x64
托管 runner，禁止 self-hosted、原机或复用已有部署。job timeout 15 分钟，
并发组串行且 `cancel-in-progress: false`，不因新请求取消正在留证的实验。

每轮绑定准确 D、run_id/run_attempt；只接受 run_attempt=1，不 rerun 旧 job。
本范围最多三个 dispatch：首轮，以及最多两轮针对明确源码缺陷的修复后验证。
executor 先登记本轮序号、修复原因、D 和已用额度，再记录实际 run_id；保留每轮
原件。成功触发即占一轮，包括随后 UNSUPPORTED/setup 失败。没有准确修复理由、
环境根本不支持或清理不明时停止，不为了命中竞态而重复；scope 变化或额度耗尽
才重新请求决定。该 lab 额度与原 Q2 唯一 startup 消费互不替代。
取得 run_id 即登记已用；触发应答不明时先查询已有运行，不补发。非预期 UNKNOWN
或清理未证也阻断后续轮次，不能换 runner 遗忘未决；预期 C3/C6 且 cleanup 已证
除外。45 分钟仅为三个 job 的最大执行时间之和，不包括排队/人工等待。
workflow 输入 expected_commit 为完整 D；任何副作用前校验 github.sha、checkout
HEAD 和冻结源码闭包都等于 D。默认分支已前进则拒绝，不能测试另一候选冒充 D。

1. 离线审阅 source、构建与非特权负例，通过后发布准确 D；审批 C 与 D 分开。
2. 由 executor 在 GitHub 页面按登记额度触发该 D 的一轮实验；工具/页面不可用即未派发，
   不以普通 push 或原 CI rerun 偷换执行通道。
3. 只读记录 image、内核、架构、cgroup 类型/已有控制器、编译器、Python、UID、
   有效权限与原 fixture boot；标签或 UID=0 不代替这些实际事实。
4. setup 创建本 run 的唯一 root 所有目录和 E 子树、专属无登录实验 UID，
   从而固定 G/S/W、只许自身分支的控制器及 FD；祖先不具能力就停止，不调宿主。
5. capability probe 仅创建一次固定无业务子进程，核验 clone3 原子入组/pidfd、
   seccomp 和 cgroup.kill，计入 setup 预算；它不是前置“只读”步骤，须在 C 后。
   它使用 E/B 限额和 20 秒固定子窗口（含 3 秒停止观察），全部权限拒绝 probe
   在该唯一子进程中完成，诊断计入另列的 256 KiB，不暗加真实病例或第二轮探测。
   该 probe 的创建来自 T，不能代证普通 S 的正向 clone 权限；后者在 C1 实测。
   若它不能清理，不进入六例，保留副作用可能发生的 UNKNOWN。
6. 每例独立固定 case ID/原点，不重跑同例；成功清理前不进入下一例。
7. 保存有界原流和 JSON 报告后，只清理精确本次临时构建/控制对象、空 cgroup
   及实验账户；待上传原流和报告排除在清理外，artifact 成功留存前不得删除。
   出现残留或 identity 不符，停止清理升级而非递归删除陌生目录。

专属 UID 和 cgroup 仅在该 job 生命周期内；无 host 服务安装、持久委派或系统
策略修改。编译器/runner/原生日志属于独立 lab 设施成本，不能伪称原 Q2 零开销。

## 六个固定病例

| ID | 确定的注入点 | 必须验证的事实与失败分类 |
| --- | --- | --- |
| C1 | 正常创建两个固定 worker，正常结束后关闭 | clone 时已在 W、准确 pidfd、原退出/双 EOF、B 空、G 摘要后真实退出；只有全部齐备才完整闭合 |
| C2 | S 已接收 REQUEST，停在 clone 以前的 barrier；G 关闭后 T 尝试释放及再提交 | 后到消息不能恢复 S 或新建 worker；不能用单个“拒绝”字段替代 S 原退出与整树事实 |
| C3 | clone 已成功，S 在身份/FD 回传以前被中止或丢弃该应答 | B 整体清理；原 worker 身份/结果保留未知，不能用暂未收到应答推出未启动；不会补投 |
| C4 | worker 已运行，S 崩溃，后代继续占用原流 | G 独立发现原 S 退出并封闭/清理后代；原 EOF 与树空须实测，不以 S 退出代替 |
| C5 | 固定有限 fork burst（至多 8 后代），关闭时至少一个真实后代和仍有剩余 fork 次数的活生产者；保留原流 | producer 与后代不逃离 B；17 秒进入关闭，20 秒内未取得完整事实就 UNKNOWN；未观察到上述状态时标 INCONCLUSIVE，不能把调度偶然当覆盖 |
| C6 | G 在形成最终摘要前崩溃 | T 不合成 G seal/FENCED；结果 CONTROL_LOST/UNKNOWN，原 pidfd/EOF 与最后 cleanup 独立保留；cleanup 不回填按期成功 |

C2/C3/C4 使用可核验事件/barrier，不用随机 sleep 宣称命中特定阶段。
C5 记录 S/W 的原身份、至少一个真实后代、未用完的固定 fork 配额以及关闭
时刻。用户态前后事件不证明 kill 恰好撞到内核 fork 临界区，亦不覆盖全部调度
交错；该窄内核竞态保留文档/源码依据及本次未必覆盖的限制，不伪造命中。
未取得本例明确的可观察前提则 INCONCLUSIVE，阻止总体资格通过，不重复碰运气。
G 关闭后，所有已收/未收控制包中的 FD 均有固定关闭责任；额外 FD、包截断、
重复/乱序、未知 frame、跨例、过期、借旧 cgroup FD 创建等协议负例先离线验证。
网络/manager连接、迁移、继承控制 FD、exec 提权的固定拒绝 probe 在 F1 已武装
权限约束后验证；不连接真实外部服务，不把 NNP 单独视为 IPC 禁止证明。

C3/C6 是预期缺证对照：报告可显示负例断言通过，但不声称这些例子达到完整
停止/身份/封存成功。结构化汇总分别给 `case_expectation_met`、`fence_observed`、
`identity_complete`、`tree_empty`、`streams_eof`、`guardian_exit_observed`、
`deadline_met`、`cleanup_verified`；缺项为 unknown，不填 true/零。
C6 固定最后执行；在它之前有非预期残留则不运行 C6。fixture 资格指六例各自
预期及覆盖判据满足，不要求将 C3/C6 的业务缺证改成闭合成功。

## 资源、证据与停止条件

按需求的 120/180/30 秒阶段、20 秒每例、E/G/B 限额与输出上限执行。
原数据流不能先无限捕获再截断；达到上限进入关闭，报告 exceeded，并有界
排空/清理，不能以截断产物声称原流完整。无 core dump；不写 worker 临时文件。
生成报告与实际 allocated/目录成员分开核对，CI artifact 只上传精确 allowlist。
公开输出不含 tokens、完整 runner 环境、真实机器凭据或原 Q2 私有定位。

收件器核对运行源码 D、工具/image 事实、帧序列、pidfd 交接、关闭时刻与
原时钟、实物 cgroup 读数、各原流、资源 counters 和清理日志，不能只信 G 总布尔值。
非预期缺项/残留/超时立刻停止剩余例子；预期 C3/C6 的控制缺证只有在外部
cleanup 已确证时允许完成其报告，不借此再跑一次。

当前 cloud 不具 fixture，不能作为真实测试替代。托管 runner 能力是 F1 的
待验证假设，明确不阻塞该有限实验实现，但阻塞实际 C1–C6；若失败，应保留
UNSUPPORTED 并重新设计，不自动换成原机、增加权限或修改平台配置。

## 退出与后续

通过只证明准确 D/fixture/六例判据，不证明 H07 原链、first SSH、跨钟、FS、
真实账单或完整 Q2。失败或不支持同样形成可用的否决证据。
原 frozen runtime、旧 API、五父域语义、预算与唯一 startup batch 全部保留。
将该原语用于真实角色需要另行完成采用与架构方案，不自动拷贝实验代码进产品。
