# Q2 系统管理器启动修复：实施方案

- Authority：Owner；状态：PROPOSED / Gate OPEN；scope：`LH-Q2-SYSTEM-MANAGER-REPAIR-v1`。
- Rule R、输入源码及目标见[需求](REQUIREMENTS.md)；职责见[架构](ARCHITECTURE.md)。
- 当前交付仅为原因核实与准确方案；M1–M4 均未实施、未消费现场运行。

## M1：真实核心与固定管理通道

对 `tools/local_hand_jobs/runner.py` 的现有 manager 命令/交付边界作显式
transport 分离；user backend 保持原行为，新增 system transport 仍调用
同一 Runner 阶段、取消、观察和结果代码。同步 policy、handle、quota
lifecycle 对 manager authority 的严格版本化绑定，旧版本无自动迁移。

在独立管理模块实现固定启动适配器，并接入 `tests/e3_host/q2_launcher.py`
的现有 controller 生命周期。`q2_resident.py` 按受保护 fixture 显式选择
新 backend。只读 quota observer 不承担新增职责。

协议采用单独 `local-hand-q2-system-manager/v1`；请求最大 64 KiB，普通
元数据响应最大 32 KiB，深度最多 12，严格拒绝重复/额外 key。业务结果
仍走原有限结果管道，不塞进管理元数据。现有 grant 自身的 32 KiB 上限
及原解析器保留。最多九次首次 stage 交付、全操作最多 256 次管理调用、
最多一个未完成调用、累计请求和响应不超过 4 MiB。最多一个控制通道及
当前 stage 的两个只读数据管道端；前驱 FD 未关闭不进入下阶段。拒绝超额，
不扩容、不循环刷新预算。IPC 顺序处理，不保存原始消息副本；CPU/缓冲区
计入 target，4 MiB wire 保守计入管理输出账，不另建日志池。

状态固定为意图保留、一次交付、原实例观察、终态或 UNKNOWN；通信断开
不得重连重发 launch。管理端重建固定命令，并验证新的 system unit
User/Group、隔离属性、父级、runtime/CPU/memory/tasks/日志费用。

## M2：装配、保留资源与候选更新

更新 `q2_prepare_assembly.py`、`q2_fixture_check.py`、`q2_supervisor.py` 及有限准备
入口，给新版本 facts/launcher/resident/policy/handle 绑定系统管理器和
新的普通父 slice。旧版本 schema 和既有入口不静默改变语义。
移除新路径对 user@ 委派几何的依赖，保留普通 resident 身份和零能力校验。

准备一份准确私有计划：复用既有 SSH/Python/普通账号/文件系统，新建一个
普通任务子 slice、新 state/capture/code 目录、七个新项目根和一次消费
标记。每项 create-only；目标已存在或半成品就停止。旧安装和所有旧批次
目录、unit、数据库、配额、lease、代码费用完整保留。不执行 reset-failed。

首次创建普通可写对象前，核对全部旧 resident/broker、控制链、管理 client
和待交付请求的准确身份及当前完整有限库存，排除同 UID 的旧生产者影响新目录。
无法证明则结束本次；不得仅凭原 bootstrap failed/父树空放行。这项新准入
证据不改写历史验收或释放旧资源。

现有同 payload 代码更新入口不能装载发生变化的 wheel：新增显式版本，
同时核验原安装回执、原/新 source、完整文件 manifest、真实 wheel 内置
metadata 和新 payload 摘要；普通可读性也须核验。复用原解释器，不 pip
重装旧环境。旧代码更新入口继续拒绝不同 payload。

预算输入固定为私有包 `local-hand-normal-7780364-management-fix-20261001d.zip`，
SHA-256 `04c2e6d1b29180ab7987b670ec4aa35e3935584709454b4325bf3188c5cecf36`。
只继承其数值上限和原安装来源，不复用旧批次身份、期限或已消费标记。

| 对象 | 本次固定上限 |
|---|---|
| 外层准备及运行窗口 | 300 s；准备 150 s；owner 120 s |
| controller-parent | 512 MiB、64 tasks、1 CPU rate、swap=0，保持原值 |
| target（含 resident/gateway/管理 client） | 256 MiB、32 tasks、85 s + 1 s stop；1 MiB/64 inode 文件池 |
| 新普通子 slice | 256 MiB、32 tasks、swap=0；位于 controller-parent 内，与 target 为兄弟 |
| 普通 operation | 总 72 s、30 CPU-s、98304 B 日志；各 stage 64 MiB/8 processes；1 s stop |
| 普通 phase/stage | 每 phase 24 s/10 CPU-s；bootstrap/helper/reader 分配 3/4/3 CPU-s，非每 stage 30 s |
| supervisor | 64 MiB、32 tasks、100 s + 1 s stop；8 MiB/64 inode 文件池 |
| owner | 512 MiB、64 tasks、120 CPU-s；8 MiB/64 inode 文件池 |
| 管理 collector/admission/query | 各 64 MiB、8 tasks、2 CPU-s、32768 B 输出；stage 8/7/5 s |
| 管理成本总上限 | 400 CPU-s、1536 MiB、1024 pids、16 MiB 输出、32 MiB/1024 inode |
| 新 state/journal/capture | 分别 8 MiB/1536、1 MiB/128、20 MiB/384 inode |
| 七个新 project 根 | 各 1 MiB/128 inode；不复用旧项目或额度 |
| 新代码交付池 | 64 MiB/4096 entries；包含 bundle、wheel、解包代码、manifest、临时峰值及输入 ZIP 的实际驻留副本 |

管理成本原保守合计为 327 CPU-s/1408 MiB/200 pids/602112 B 输出/
20 MiB/384 inode。gateway 位于原 target 限额内，不能再次独立增加进程封套；
4 MiB 控制流计入输出后仍须与其它实际输出联合检查。管理成本与原普通
grant 分开列账；新增子 slice 由不变的 controller-parent 约束，不能重算
成额外顶层父域。意图及最多 32 KiB 安全诊断重分 target 原 1 MiB/64 文件池，
同时计入原 capture 池，不把总成本表的余量当作新磁盘授权。
全部历史代码/运行包义务继续按原池保留，新候选全部驻留峰值必须进入上述
64 MiB 池；若保守实际算法所需池更大，须停止而非扩容。任何入账、父级几何
或旧生产者覆盖不足均在首次交付前结束；已有未知费用不算零。

## M3：针对真实故障验证并形成单次 ZIP

需要的回归只覆盖此次改变及真实风险：

- user backend/旧 schema 无变化；system backend 真实共享阶段核心。
- 任意 argv/属性/unit、错误 peer/PID/start_ticks、重放、消息/FD 截断拒绝。
- 每个 stage 一次交付；发送后丢响应、控制端退出、延迟启动和停止 ACK 丢失
  保留原意图/身份，禁止补投，不伪造 EOF、退出或资源释放。
- 系统 manager/父级/InvocationID 错配、隔离属性缺失或 capabilities 非零拒绝。
- 新旧资源不相交、旧费用仍保留、所有生产者有界、超额/过期拒绝。
- 新 payload 准确准入；原安装、旧回执、错误候选和已消费包不能被覆盖或重跑。

模型、真实本地进程/管道和实际 systemd 检查分别记结果；不支持不算通过。
不能为测试擅自开新主机或消耗退休实验的轮次。
源码审核后提交 main 并从干净准确 commit 构建 ZIP，固定 SHA-256。
包内 `TASK.txt` 写明唯一入口、复用 SSH/安装、全部对象与预算、消费规则、
一次执行及原输出收集方法；不允许执行者自行修环境后重试。

## M4：原 guest 一次执行与验收

本 scope 获准后，整个 M1–M4 批次无需逐项再次询问。对准确已核验 ZIP，
local Codex 复用原 SSH，先独占消费标记，再在原 300 s 窗口内完成上述有限
新对象准备和最多一次原正常链；不得在准备失败后另起一个窗口继续。
只有显式环境/原安装/身份/保留容量/实际 source 全部符合才可进入正常链。

保留隔离建立、真实 Python 入口身份、管理器和每个 stage 原 invocation、
完整双流、终态、配额、结果及父级证据。保留原验收标准，显式新增 system-manager
证据版本；旧 user-manager 验证器不静默改义，也不以只检 exit=0 替代验收。
任何首错结束本次，保留所有实际新对象，不清理、不自动重试。

现场没有失败证据不能证明路径已覆盖；离线测试不能证明 AppArmor 下已通过。
本次正常链成功也不关闭 Q3 故障矩阵或生产资格。进一步实质边界变化仍按 R
处理；旧范围和历史批准文件不覆盖、不重写。
