# Q2 系统管理器启动修复：架构

- Authority：Owner；状态：PROPOSED / Gate OPEN；scope：`LH-Q2-SYSTEM-MANAGER-REPAIR-v1`。
- [需求](REQUIREMENTS.md) → 本文 → [实施方案](IMPLEMENTATION_PLAN.md)。

## 固定职责

普通 Broker/Runner 保留授权、去重、租约、阶段推进和证据判定。
新增受限 manager transport 是真实执行核心的显式后端；不使用 harness
猴子补丁跳过原执行或断言。生产默认入口继续拒绝未资格化 backend。

已有 root controller 内的固定启动适配器持有系统管理权限；复用现有
外部 supervisor、原 deadline、输出和资源封套。它只能根据 root 保护的
安装、任务、路径、额度及阶段声明重建固定 argv/属性，并向 PID 1 交付。
不能接受普通端自选的命令、可执行路径、unit 名或 systemd 属性。
quota observer 继续仅执行原固定 quota 查询，不增加启动作业接口。

PID 1 在降到普通身份前准备隔离环境。每个实际业务 unit 显式固定 User/
Group、空 CapabilityBoundingSet/AmbientCapabilities、NoNewPrivileges，
并保留 PrivateUsers/Network/Mounts/Devices、ProtectSystem/Home/Kernel、
RestrictNamespaces/SUIDSGID、原可见路径及全部资源属性。业务不得以 root
运行，也不获得用于准备环境的能力。这是待现场验证的标准 systemd 路径，
不是已有通过事实。

## 通道与操作

仅使用 controller 创建、传给准确 resident 的私有继承式 Unix 通道，
不建立公开 socket、HTTP 或 MCP 管理入口。两端验证实际 PID/UID/GID、
start_ticks、boot、会话及原期限；拒绝额外/截断 ancillary data 和重放。
请求和响应有严格版本、key、类型、大小及深度上界；不接受任意 FD。

固定操作仅包含：本执行域库存观察、单个原 stage 的首次交付、原身份
状态观察、原身份停止、原结果管道封存。请求使用逻辑 phase/stage 和
已绑定 allocation/grant 引用；控制端核对自己保留的声明和原 quota
会话，不能把普通端自报摘要视为独立授权。
控制端同时核对原管理 journal 和前驱 bootstrap/helper/reader 的实际关闭
证据，按既有阶段顺序单调推进；普通端的 phase/stage 标签不能授权提前启动。

三个 phase 最多九个 stage，每个 stage 最多一次 StartTransientUnit。
控制端先持久化意图再交付；响应丢失、控制端死亡、断线或交付不明都不补投。
原 resident client 的双流和 gateway 管理 client 的双流分别保留，不互相替代。
普通端不能直接 signal root client；停止/等待只引用登记的原 stage，控制端
核验实际 client PID/start_ticks 并返回真实退出状态，不能接受任意 PID。
固定结果流如需 FD 传递，只接受控制端创建并登记的有限只读管道；验证数量、
类型、访问模式、会话绑定及关闭责任，拒绝其它 FD，计入原管道预算。

## 管理器身份、状态与库存

新 policy、fixture 和 durable handle 显式绑定 `manager_kind=system`、
受保护 authority、boot 和新父 slice 的准确路径/dev/inode。旧 user handle
保持旧版本、旧 manager 和原结论；禁止仅根据相同 unit 名迁移或停止。

新 backend 的完整库存来自系统 manager；按已准入 Local Hand 执行域核验
名称、父级和记录，未知或异父身份拒绝。原 user-manager 库存另行保留为
历史，不伪装成系统域的未知 unit 已被“忽略修好”。在首次交付前，新普通
工作父树为空。新普通子 slice 放在既有 controller-parent 内，与 target
service 互为兄弟；二者均为 root 管理。它不包含 broker，且与旧 user
子树、query、management、supervisor 不重叠，普通用户不能直接管理它。
新 schema 只允许这一条准确父子关系，不删除旧版本的所有父级不重叠检查。

新 allocation 只能用新根/新 project，原七条 lease 和其它历史保留账项
不能释放、抵扣或迁移。准入同时验证旧资源身份、隔离关系及累计保留容量；
旧迟到执行仍只能占用其原边界。若共享路径、生产者或容量无法证明被原额度
覆盖则拒绝，不以“新 manager”作为无条件继续理由。

同 UID 的旧 resident/broker 位于初始 namespace，可能访问未来同 UID 的
新目录，因此新路径/新 project 单独不足以证明不相交。创建任何普通用户
可写的新对象前，必须完整核对所有历史 resident/broker、launcher/controller/
supervisor、管理 client 和未决启动的准确身份，证明当前不存在仍可影响
新资源的旧生产者或待交付请求。新旧 worker parent 空不能代替这项检查。
来源须来自全部保留批次的保护记录并与当前有限完整库存一致；缺项、新进程、
身份变化或旧请求是否仍能启动不明即拒绝。当前准入证明不补写历史 EOF/成功，
不释放旧 lease，也不授权停止旧对象或更换 UID 来继续。

终态仍需原 invocation、无未决启动、停止 ACK、原 client 退出、双流 EOF、
原父级及子树关闭证据。管理端增加的意图、client、管道和排队操作也在这个
证明范围内。失败保持原 UNKNOWN，不创造新的“failed 即释放”快捷路径。
停止只针对原准确 unit，不能停止共用的 controller-parent。外部 supervisor
继续核对整个 controller-parent 的空树；controller 退出不代表普通 sibling
退出。gateway 随 controller 退出后不复活，也不新增替代启动者；各 stage
仍受原时限约束，若缺完整停止/EOF/无未来启动证明，保留 UNKNOWN。

## 费用、兼容与方案取舍

新增 gateway 在现有 controller 封套内运行，所有线程/进程、CPU、内存、
消息、管道、文件、systemctl/systemd-run 调用都显式计费。现有 controller
256 MiB、外层 300 秒以及阶段/输出/存储上限均不因换 manager 增长；超出则
在运行前拒绝。原 controller-parent 保持 512 MiB/64 tasks/1 CPU rate、
swap=0；target 保持 256 MiB/32 tasks，新普通子 slice 为 256 MiB/32 tasks。
两子域共用父级硬上限，核对有效祖先限制；不是另增一个顶层 256 MiB 父域。
旧 ordinary 的 256 MiB/64 tasks 及其它旧保留费用保持。原五个顶层父域上限
合计仍为 2048 MiB/320 tasks/5 CPU rate；这是这些父域之和，不是整机所有
管理开销的总额。普通操作独立的 30 CPU-s grant 不冒充包含在管理成本表中；
父级共享 CPU 的竞争不能刷新任何期限。所有历史费用与其它控制费用仍须核对，
不能按当前空闲内存核减旧 UNKNOWN 的承诺。
AppArmor/sysctl、系统包和旧 manager 完全不改。

不采用全局 executor profile：其范围超过单个 Local Hand，且最终 exec 的
confinement/NNP 兼容性不能靠一行规则保证。不新建第二个 user manager：
同 UID 的 bus/runtime 冲突和新 profile/生命周期比固定 PID 1 接口范围更大。

原 wheel payload 若因真实 backend 接口变化而改变，使用明确版本化的候选
代码更新合同，保留原安装及真实 payload 摘要；不得关闭原 same-payload 检查
或把新代码标成旧 payload。新增代码、wheel 元数据、管理入口和预算全部绑定
到准确新 source。停止新路径是禁用新入口，不回滚删除旧记录或现场。
新候选 payload 放入新增 root 拥有的只读目录，保留真实 wheel 元数据并由
固定来源 loader 核验；普通业务入口使用该目录和原解释器，不导入旧/新混合代码。
