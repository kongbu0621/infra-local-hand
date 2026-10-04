# 核心 v2 接线与剩余执行工作

2026-10-04。承接 `a066bdb612419a5414cc9249f226b3244374dc7b`。
本件是已批准 D1–D4 中的源码推进记录，不是 package freeze、F1 或真实任务完成证明。

## 批准与已有结果

沿用 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、A
`0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`、Owner event
`LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-CLOSURE-20261004-01`、C
`7598886e15ed6911fe0e09e2f8d66203455f9057`。没有要求 Owner 重复批准这个范围。
三份 A 的原字节、摘要和既有 CLOSED 记录未改。

前一源码提交 `25dabbb4763520e26c75b769c3acc6d9a6f69c34` 的
[CI 37177671053](https://github.com/kongbu0621/infra-local-hand/actions/runs/37177671053)
已经 completed/success。这是旧提交验证结果，不代替本轮源码验证或现场验收。

## 本轮实际源码

| 核心部分 | 已完成的实现 | 验收边界 |
| --- | --- | --- |
| 批准输入 | 新增 `q2_core_approved_inputs.py`：16 locator 关系、历史原验证器输入、36 行承诺、46 行 quota、retained、source union、policy 和 reconciliation 聚合；source-aware builder/parser | 云端没有完整私有 retained closure，不能声称真实 aggregate 已建成 |
| 本地冻结 | 使用原 900s origin；实际 writer/anchor；三个 held policy 原件绑定；source-aware 验证；独立 bootstrap 第二解析；支持正常 import 的输入类型 | 不刷新窗口；没有创建现场 marker 或 package |
| HELLO/package | v2 amendment、private member、实际远端账户及五个程序实体的有界 JIT 读取、固定命令摘要；bootstrap 保持原源文件大小限额 | HELLO 不是 current policy admission |
| 远端解析 | dispatcher 自包含校验批准输入的固定关系、向量和 policy 模板；不依赖额外未验证现场模块 | 尚有 host writer 传输缺口，真实 effects 前明确停止 |
| 回传与本地终结 | 六文件 capture 接入；九项摘要从实际 host preimage 重算；session/admission/installation、marker、BIND、package 和双钟逐值绑定 | 临时文件及合成流测试不构成真实任务完成 |
| 安装桥接 | root-only create-only staging；逐成员写入、fsync、回读；调用已有候选安装器；固定环境、受限双流 child、异常 kill/reap；private member 不进入安装投影 | 内部写入逐项 deadline、实际执行工具身份和共享分配峰值仍未完成；readiness 明列阻塞 |

实际 host 工具、writer 及 policy 原文读取均不改成 guest 身份或请求方自报值。
固定四个宿主程序继续沿用原读取 profile；没有因普通账号无 `CAP_FOWNER` 就引入权限降级重试。
六文件验证回读仍要求 NOFOLLOW/NOATIME、同 held parent/inode，无 weaker fallback。

## 交叉复核中修正的问题

- 返回 admission 校验漏传本次 context 会使所有完整回执失败，已接入冻结 manifest、原 approved member 和实际 HELLO。
- 有效 Ed25519 公钥加上重算后的 policy 摘要不能代替当前 held 公钥原件；freeze 重新派生整个 policy。
- 正常模块和隔离 package 模块的 dataclass identity 不同，不能把合法调用者误判为来源错误；转换准确字段后仍运行完整 raw-source 验证。
- 历史验证必须加载原 manifest 绑定的工具源码，不能要求历史源码等于当前 checkout。
- 安装 child 启动后 selector 构造失败也必须进入 kill/reap/close；安装活动不得借用 45s remote-final reserve。
- 不再用 `pids=1`、存储零值或本进程统计冒充所有 child/unit 的实际资源峰值；缺少计量时明确失败。

## 具体协议缺口：marker writer 尚未传给 guest

A §5 已要求 marker v2 包含实际本地 `writer`。当前固定 package.entry、BIND 和 private member 的
准确字段集合却没有传送该 preimage。guest 的 `session.consumption` 仍必须报告 marker 的准确
`basename,bytes,sha256,state`。只有 local-binding SHA 无法反推 writer，guest PID/UID 也不能替代
host writer。故 dispatcher 保留 `CORE_DISPATCH_HOST_WRITER_UNBOUND`，没有猜长度、删 hash 校验
或发送第二个 request。

建议的最小后续接口修订是：在现有 package.entry 中携带准确 `writer`，freeze 强制它等于
`local_management_binding.writer`，bootstrap 验证其固定结构，guest 用它重建同一 marker 并核对
BIND 的消费摘要。不增加文件、请求、执行次数或权限，也不放宽安全校验。
这是尚未实施的 schema 提案；按 R 的 change control，须先完成该小范围文档修订及准确批准登记。
原 A 下其他 D2 实现不因这个局部缺口停工。

## 验证记录

本轮最后一次 13 个核心测试模块合并运行：**295 passed / 1 failed，4.90s**。
失败项是原有 `test_bound_writer_reads_process_not_guest_identity`：本工具运行环境中
`os.getpid()` 返回 `2`，同一进程 `/proc/self/stat` 返回 `11786`；独立小程序也复现这两个视图
不同。没有据此修改产品身份验证、修改该测试或自动标为 SKIP。必须由准确新提交的普通 Linux CI
及本机验证补足，不能宣称此云端测试全绿。范围为 capture、contract、package、freeze、entry、
bootstrap、loader、dispatcher、dispatch_v2、approved_inputs、obligation_inputs、legacy_inputs、
policy_basis。首次新增测试及交叉复核所暴露的问题保留在工作记录，修复后重新合并运行。

新增/修改 Python 文件语法解析通过。bootstrap 实际 **48828 B / 49152 B**，dispatcher
**195390 B / 262144 B**，没有扩大发行上限。批准 A 的三份文件摘要仍准确相等。
聚合、历史 RAM loader 与 freeze 独立组合为 **73 passed**；它与上面范围重叠，不相加。
另外从固定历史 `8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1` tree 实际加载 42 个原工具，
纯 verify 可调用且导入状态恢复；没有将这项加载验证冒充私有原件的完整 verify。

代码已由并行 reviewer 交叉检查 host-return 绑定、输入来源/历史加载、bootstrap 和安装异常路径。
上述未完成项及真实现场条件仍阻止 D4/F1；这不是 D4 完成声明。

## 本地 Codex 接续顺序

1. 合入本提交，继续已授权核心 D2：current guest collector/policy 判定、existing-account preparation
   adapter、固定 plan、真实 H01、Q4、H11、phase facts 与完整资源计量。只复用已有身份、SSH 和
   retained evidence；暂停其它分支功能。不要重放旧失败批次或把合成 fixture 改写为现场 PASS。
2. 完成安装内部 deadline adapter、逐命令执行身份绑定及 shared-pool accounting；以真实反例验证后
   才可移除对应 readiness 阻塞。不得通过删掉 guard/改摘要/伪造 usage 消除阻塞。
3. 本机使用已有 raw closure 运行聚合 builder 和独立验证，交叉核对实际 held policy；私有原件和
   完整机器身份不提交公开仓库。不要求 Owner 再寻找已保留且已核实的同一历史文件。
4. 处理上述 writer 小范围 schema 提案；D4 独立审查所有剩余项，冻结准确 implementation/tree 与
   单次包、TASK.txt。只有全部已批准条件满足才进入原条件单次 F1；不自动重试、不清理现场。

目前 release allowlist 仍为空；package `NOT_ISSUED`，本轮没有 SSH、现场安装、systemctl、H01/Q4/H11
执行或现场清理。`q2_accepted=false`、`q3_accepted=false`、production 仍是
`E3_SUPERVISION_UNVERIFIED`。不能把源码测试或旧 CI 绿灯写成 Local Hand 核心已完成。
