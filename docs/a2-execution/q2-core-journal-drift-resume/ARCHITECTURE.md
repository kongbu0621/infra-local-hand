# 原维护组件与单次接续边界

Authority：Owner。**PROPOSED / Gate OPEN**，范围仅来自[需求](REQUIREMENTS.md)。
继承 [scan-work 架构](../q2-core-journal-scan-work/ARCHITECTURE.md)及其原维护组成。
沿用普通 coordinator、固定生成 root writer、原终端认证和两阶段 guest 协议；无新组件。

## 来源和状态传递

`growth_sources` 增加本范围准确 A/C、三文档摘要与祖先校验，最终 D 承接独立 C，且包含
已验证诊断修复 `711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5`。保留全部旧 pins。
`WriterObserver.binding` 增加本范围 A/C/修复身份；准确 D、payload/loader、工具、
原输入、nonce、TTY 和双时钟仍走同一个原 manifest 与两 CLI 交接。
旧候选、旧成功报告、旧交接或更换 session 均不能替代本次准确绑定。

实现差异仅限新增授权绑定及相关验证。scanner、生成 writer 函数与固定入口保持修复
版本的字节；payload 仅准确 `EXECUTION_D` 值随候选变化，不再重构诊断或扫描。
原 `lhq-journal-writer-result/v2` 六字段成功/失败报告、严格 13 字段 progress、
reason/errno、EOF/真实退出和父层首因优先级保持。没有合法 child 报告时不补造 progress；
已有合法 request 的报告缺失 progress 仍拒绝，早期 request/progress 均 null 的原规则保持。

DR1 可在原静态资料上做离线来源与交接核对，不构造现场 Window 或 observer，不提前调用
sudo、实际 writer、当前 boot/proc/VM、工具资格探针或 SSH。旧冻结交接只保留为证据。
DR2 按原 CLI 顺序：源码/身份/继承资源/参数检查→真实 TTY 资格→建立并绑定 Window→
原输入冻结和现场准入。不得把窗口移到耗时读取之后，不刷新计时。
execute 必须复用预检的同一 D、manifest、窗口和 writer handoff；保留原源码中的再次
准入、checkpoint 2 及本地 SSH 配置检查，不新增预检窗口、不重放 checkpoint 1。

## 当前预算与停止条件

| 维度 | 保留的当前合同 |
| --- | --- |
| FD stat | 每 writer 2097152 次，初始/复核/匹配共享，调用前收费，错误不退款 |
| PID / 每 PID task / 全部 task | 32768 / 32768 / 65536；原所有复核保持 |
| 单 snapshot / maps | 65536 项；单文件 1 MiB、累计接受 512 MiB |
| stat / fdinfo 文本 | 16384 / 4096 B；原初读与复核保持 |
| writer / 总窗 / 修改截止 | 15s（含认证）/ 900s / 780s；八串行检查点各一次 |
| 内存/句柄/控制子进程 | AS 256 MiB / FD 128 / 最多八个；原 120 CPU-s、512 MiB 部分观测 |
| writer 输入/stdout/stderr | 65536 / 65536 / 4096 B；progress 4096 B、reason 160 字符 |
| 两维护源 / root payload / argv | 各 98304 / 32768 / 65536 B |
| guest bundle | guest 源 98304 B；reader/input 65536 B；压缩 49152、解压 393216 B |
| 存储 | 原逐设备 1296 MiB/370 inode 条件，旧承诺 264 MiB/80 inode，备份 320 MiB，镜像 576 MiB，capture 8 MiB/32 inode |

这些不是新增预算或对整机峰值的保证；历史用量不退款，原管理祖先/TTY 计量边界保留。
现行双钟和协作式读取期限不被宣称能强制中断内核 I/O；不延长时限来吃满计数上限。
不得复制旧 resume-v2 中过期的五字段结果、64 MiB maps 或 65536 B 维护源限制。

预检全门通过后，沿原状态顺序完成正常关机、确认退出/离线、完整备份、镜像增长、一次
原配置启动、原被动等待（最多 60s）、ext4 增长及内容/容量验证。累计动作次数不变。
失败立即停止后续步骤，保留已取得首因/前缀/退出事实；不新增现场观察以解释失败。
失败可能留下 guest 关闭或部分增长状态，没有自动恢复或回滚授权。

选择一次完整维护接续，是为了让原合格流程有机会完成且失败能区分具体检查项；不是证明
普通宿主活动可被忽略。拒绝自动重试、提额、缩减扫描、停宿主应用和改一致性策略的路线。
若新证据要求实质策略变化，应审阅该具体变化，不能在本窗口中临时修改。
