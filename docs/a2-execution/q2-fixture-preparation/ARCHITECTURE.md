# Q2 隔离实验 fixture 准备：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN**；scope：`LH-Q2-FIXTURE-PREP-v1`。
- [需求](REQUIREMENTS.md) → 本文 → [实施方案](IMPLEMENTATION_PLAN.md)。准确 A 与关闭决定按根 `AGENTS.md` 登记。

## 责任与信任边界

| 部件 | 输入与职责 | 明确不能产生的事实 |
| --- | --- | --- |
| 候选构建器 | 干净已提交 source；构建 wheel、native 来源清单和 host 入口摘要 | 不预造宿主 UID、project、inode、InvocationID 或已准备标记 |
| 管理准备器 | Owner 批准范围内的私有计划、固定构建摘要、既有 guest 事实；一次核对并准备新对象 | 不继承 Q1 的 reservation、预算、已消费 slot 或历史成功 |
| 离线装配器 | 实际准备回执与准确安装字节；建立一致的 policy、两 slot/独立 store 映射及静态 launcher 模板 | 不发行尚未发生的 broker reservation、phase deadline 或管理 grant |
| 原交付所有者 | 固定运行计划、准备完成的对象、自己的有限费用；一次交付 supervisor 并保留原 client/双流/停止证据 | 不把 systemd-run 返回或 SSH 断开当作完整进程退出 |
| 同 PID 绑定入口 | 受保护静态模板、已发行原 envelope、当前实际 service 身份；在同一 MainPID 进入现有 supervisor | 不重启服务、不派生替代 supervisor、不延长原期限 |
| 现有 Q2 链 | 原 ordinary broker/SQLite 操作，`preflight → business → evidence`，独立管理查询与关闭 | 不把目标 controller 的封存当作外层所有者自身退出或 Q3 接纳 |

管理准备器及同 PID 入口独立于默认 wheel、生产 broker 和 Plugin。普通运行核心继续依赖无特权合同；不能反向依赖宿主准备代码。
现有 source、wheel、目录身份及管理回执是独立输入，派生配置里的自报 digest 不能替代原发行者的授权。
私有原始报告、账户、路径、boot 和对象身份不进入 Public 仓库；仅发布工具、脱敏结论及必要摘要。

## 对象拓扑

新增一名普通账户拥有私有 broker state、policy 和被批准的七个 quota 根；管理代码、journal 与管理捕获目录保持 root 管理。
普通 resident 保持初始 user namespace、零能力和固定普通 UID/GID；它由目标 controller 降权创建，位于普通工作父 cgroup 之外。
普通 bootstrap/helper/reader 继续按原核心在对应 user manager 的专用子 slice 内运行，保留各阶段 PrivateUsers 等既有隔离要求。

`Delegate` 实际属于新增 UID 的 `user@UID.service` 实例，不属于 slice 或 `-.slice`。
CPU、memory、pids 的有效控制器及上级启用关系逐层核对。新增普通工作 slice 位于该 service 委派子树；
query、management、目标 controller 和 root supervisor 各有不同的系统级专用父 slice，彼此不重叠，也不进入 Q1 父级。
外部交付所有者保持独立控制通道，不能处于会被它停止的目标 supervisor 子树。

| 新对象 | 角色 | 复用规则 |
| --- | --- | --- |
| slot A：work/evidence/temporary | preflight 消费，business 继续同一 allocation | 只能同一操作内继承；失败和取消也不退还 |
| slot B：work/evidence/temporary | evidence 的新工作域 | 必须与 A 的路径、inode、project 域完全不同 |
| 独立 evidence store | 同一 policy 和 broker 绑定的长期保留输出 | 独立于全部 slot/profile 写入树；evidence 以 `retained_store` 角色引用，不能别名 slot A |

七个根分别使用新的 project，均位于已存在的准确 quota 文件系统。只创建新根并设置继承与新域限额；不改变文件系统特性、挂载参数或任何旧 project。
profile 父目录不能作为直接业务写入授权；实际每阶段必须取得已持久消费的 slot grant。
普通保留 store 与 root 管理 evidence 是不同对象、不同责任及不同容量项。

## 输入合同与持久状态

私有准备计划采用单独版本，至少包含：批准 scope/基线关联、唯一 preparation ID、明确 guest 和当前 boot、
允许使用的既有文件系统及身份、旧 Q1 保留边界、新账户和准确待创建路径、七个新 project ID、逐域硬限额、
固定候选/构建摘要、有限配置与捕获容量、各专用 slice 的资源上限、后续原交付的责任人/停止入口。
源码没有实际主机默认值；示例和合成对象不能成为现场计划。新增名字或 project 已存在时拒绝，不能“接着用”。

一次准备状态为 `DECLARED → PREFLIGHTED → RESERVED → PREPARING → PREPARED`。
任何持久修改前先保留准确意图和原对象清单；每项实际新对象的身份、命令、输出、退出码与前后事实追加记录。
失败为 `INCOMPLETE`，结果不明为 `UNKNOWN`；二者保留原 preparation ID 及所有已分配对象，不重新分配一个新 ID 来伪装原操作继续成功。
只读诊断可以集中说明已完成和未完成的固定步骤；恢复若可实现，必须证明原意图、原对象、未交付的后续动作且无额外预算，不能重放 quota 设置或启动。

普通 SQLite 仅在新私有路径按当前核心 schema create-only 初始化；初始 operation/events/leases 为空，generation 固定。
“空 ledger”不允许清空旧数据库获得。管理 journal 和输出目录也必须是新准确对象，后续首次写入和不明部分写入均保留。
配置以 no-follow、有限读取、准确 owner/mode、create-only 写入和 fsync/封存维持绑定；目录枚举、文件大小及输出均有上界。

## 准确候选与运行时接续

先提交并固定 source commit，再从该干净候选构建 wheel；wheel 的内置 source metadata、全部文件及完整摘要均核对。
宿主安装使用独立新目录；普通账户须能遍历父目录并读取所需文件，不能把 root 能读当作普通身份可运行。
管理 observer 与 native 单独保留来源/ABI/编译输入，不因 wheel 构建成功就视为已安装管理组件。
宿主准备回执只在上述安装实际核验后生成。后续证据提交不改写原候选和构建身份。

静态 fixture 不含伪造的未来 InvocationID。原交付所有者在一次 launch 前固定 boot、issued/deadline、资源、有限管道费用及唯一 unit 意图，并保存永久 reservation。
新入口在该实际 root service 的 MainPID 中读取自身 InvocationID、cgroup 路径及 dev/inode，核对所有原限制、父级、唯一原 unit 和管理器观察，再直接调用现有 supervisor；不得先运行一个前检进程退出后复用其身份。
仅绑定明确声明为运行时动态的身份字段；原预算、epoch、source、路径、容量、issued/deadline 均不可因此改动。到期或无法证明同一原实例即保留失败。
外部所有者核对并停止准确原 supervisor、无待处理 job、父树空、原 client 实际退出及双流 EOF，再封存自己的结果。
目标 controller seal、supervisor 原退出与外部捕获分别记录，不互相代替。
监督链在既有管理入口及其原管理会话处终止：外部所有者的预算和交付权限由该入口在启动前固定，不能由子级回授。
外部所有者封存的是其对子级的观察，它自己的原进程退出及双流 EOF 仍由原管理会话记录；缺失时保留 INCOMPLETE。
本方案不要求再 provisioning 一层监督者来证明该管理入口，也不以外部所有者自己写出的成功字段代替其实际退出。

## 资源、安全与演化

域、代码、state、管理记录及外层控制费用遵守需求中的有限上界，并以实际文件系统块/inode 及各角色同时存在的峰值组合计算；不以当前空闲值冒充未来预算。
准备阶段与执行阶段分别有原时限、CPU/内存/PID/输出约束；执行费用包括所有 manager 控制调用和外部所有者。
只读观察、模型测试和真实宿主验证分别报告，准备本身不重新声称 Q1 历史峰值或 quota enforcement。

选择新增私有实例而非改造原 Q1 对象，使旧记录仍能独立审查；选择复用现有文件系统和系统工具以缩小影响。
拒绝使用旧 slot、调整系统包来临时修环境、把独立 store 别名到工作根、凭静态清单自报 supervisor 已运行等路线。
如果实际控制器、工具、容量或所需停止权限无法满足本边界，集中停止并提出变更，不在准备脚本中自动切换方案。
停止运行期只停止准确本次实例；自动回滚不删除账户、配额、账本、payload 或证据。删除/回收是后续单独明确的动作，不能抹掉失败分配。
