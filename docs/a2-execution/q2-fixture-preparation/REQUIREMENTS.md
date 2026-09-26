# Q2 隔离实验 fixture 准备：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- 拟议 scope：`LH-Q2-FIXTURE-PREP-v1`。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，采用关系、完整性及例外规则沿用根 `AGENTS.md`。
- 本文与 [架构](ARCHITECTURE.md)、[实施方案](IMPLEMENTATION_PLAN.md)构成新提案；准确 A 由包含三份文档的提交确定。本提案不代替 Owner 的 B 或独立 CLOSED 登记 C。

## 目的与已有事实

为已有隔离 Q1 guest 准备一个新的、有限的 Q2 实验 fixture，随后接入现有 test-only 三阶段入口。
用户已经完成一次只读交接；报告确认所选旧安装可读取，并明确九组 Q2 输入未交付。
继续重复读取旧 Q1 库存不会创建这些对象。本次目标是把安装、普通身份、配额对象、账本、容量和原监督入口集中准备，减少逐条命令与截图往返。

Q1 原 guest 范围的收口结论保留。现有 `LH-E3-QUOTA-HARNESS-v1` 已 CLOSED 的范围允许代码和已交付 fixture 上的隔离测试，明确排除了 host provisioning；本提案只补这个实际准备边界，不重新审批该已批准范围。

## 范围与可观察结果

| 编号 | 必须具备的能力 | 成功条件 |
| --- | --- | --- |
| P01 | 只在明确选择的既有隔离 Q1 guest 工作 | 在首次持久修改前，核对管理方提供的 guest、boot、现有文件系统、旧记录保留清单与新对象无重叠；任一不符即 BLOCKED |
| P02 | 新增一个专用普通账户和主组，以及其独立 user manager 执行区域 | 普通运行身份无附加组、零 capabilities；`user@UID.service` 的真实 service 委派及 CPU/memory/pids 控制器成立；原 Q1 用户不改动 |
| P03 | 固定候选及安装 | 新独立受保护目录容纳准确干净 source、普通 wheel 安装和管理侧程序；source、wheel 内容、运行入口、解释器及 native 构建来源对应同一候选 |
| P04 | 为一个新操作准备有限配额对象 | 两组各三个根及一个独立保留 store 全部新建、准确固定且未消费；原 Q1 分配及所有历史 payload 保留 |
| P05 | 准备控制与管理对象 | 普通私有 policy/空 SQLite 账本、独立管理 journal、输出和声明目录、query/management/controller/supervisor 专用父级分别固定；新 endpoint 尚未绑定 |
| P06 | 一次原监督入口 | 静态准备完成后，由一次原管理交付建立有限 supervisor；自身实际 InvocationID/cgroup 只在同一 MainPID 内绑定，随后直接进入现有 supervisor；独立外层所有者保留原 client、双流和停止责任 |
| P07 | 保留失败并批量报告 | 一次调用输出完整准备或失败清单；部分完成、超时、未知交付或退出不全均保留且不可自动重试，不删除 reservation 或退回 slot |
| P08 | 分开准备与验收 | `PREPARED` 只表示对应固定对象准备完成；实际 Q2 执行、原退出及完整捕获另有记录；任何结果不自动接受 Q3、生产或 E4–E6 |

## 准确影响边界

仅允许在上述 guest 内：新增一个账户/组；新增该 UID 的特定 user manager 委派设置和运行期启动；
新增专用父 slice；在已存在且已启用 project quota 的隔离文件系统中新建根并设置**新的 project**硬限额；
在明确选择的已有系统、journal、evidence 文件系统中新建代码、state、管理和证据目录；
安装准确已构建 wheel 到新隔离位置；通过固定工具构建或核验管理侧 native 程序；创建新的空账本；进行一次有限原监督交付。

禁止格式化、分区、扩容、挂载/重挂载、修改 fstab、升级系统包或内核、安装新系统依赖、改变旧 quota、递归修改旧目录权限、修改通用 `user@.service` 模板或既有服务、触碰 GX10/现役 S1/真实 NAS。
现有工具或控制器不满足条件时集中报告 BLOCKED，不临时扩大修改范围。新 user manager 只用新 UID 的实例级设置；不启用开机常驻或 linger。

Q2 不采用任何旧 Q1 slot。两个新 slot 分别承担 preflight/business 和 evidence 的新 work/evidence/temporary 根，另有一个独立 `bootstrap_evidence_store`。
总计 **七个新目录、七个不同新 project**；business 复用本操作 preflight 的三个根，不另增三根。
保留 store 不得与任一 slot 或 profile 写入父目录重叠，不以第七个根冒充 Q1 已有 payload。
本批发现的旧整链 decoder“store 必须别名 preflight 根”限制与真实 policy 冲突；该冲突的修复与真实 Policy 贯通验证是正式准备前置条件，见 [Q2 装配复核](../E3_QUOTA_Q2_ASSEMBLY_REVIEW.md)。不能通过削弱 policy 来使该提案可运行。

## 容量与保留约束

每个新 project 的提案上限为 **64 MiB、4096 inode**，七域合计最多 **448 MiB、28672 inode**。
这些是授权上界，不是默认设置、可用容量证明或预先发行的预算。实现应选择能覆盖固定 `host.inspect` 的更小明确值，并在首次设额前确认原保留量、各域和所有管理开销能够同时被计入实际文件系统余量和批准的有限总上界。
原有域的保留承诺继续累计；同一文件系统计费必须去重，不能把硬限额、目录占用和虚拟盘容量重复相加。

新 source/wheel/native 和构建暂存合计上限 **256 MiB**；新普通 state 与准备日志合计 **32 MiB**；
新管理 journal 开销上限 **64 MiB**；新管理捕获与声明开销上限 **64 MiB**。
它们属于各自实际文件系统的独立费用，必须包含部分失败和文件系统块/inode 开销；不足即阻塞，不清理旧记录腾空间。
原 supervisor 延续现有 **不超过 120 秒**的合同；普通操作及每阶段、目标 controller、外部停止和双流捕获各有原 deadline，不能在接续时刷新。
原交付所有者使用既有管理入口作为本 fixture 的外部信任终点；它不依赖被监督进程为自己授权。
子级退出由它核对，它自身的退出及双流 EOF 由原管理会话保留；该记录缺失时保持 INCOMPLETE，不增设无限递归监督层或自报完整退出。

## 验收与需要的 Owner 决定

准备验收至少包含：准确安装、普通身份可访问路径、7 域身份/继承/限额、新空账本、实际 service 委派、独立 cgroup 几何、有限容量、同 MainPID 接续，以及一次原外层退出/EOF 证据。
模型测试、静态准备和真实运行分别标记；缺少任何必要输入保留 BLOCKED，不能靠自行生成 acceptance 字段补齐。
故障实验 H06–H13、Q3 接纳、上线与业务扩展不在本次准备验收中。

需要 Owner 对本 scope 的准确 R/A 关闭 Gate，并允许上述**既有隔离 guest 内的新增对象准备与一次有限原监督接续**。
该决定可以一次覆盖集中实现、验证与交付；不要求每创建一个目录或每项本地测试再逐项批准。
超出明确对象类别、数量或上界，改变已有部署，或发现需要挂载/升级等禁止项时，受影响工作仍须回到变更评审。
