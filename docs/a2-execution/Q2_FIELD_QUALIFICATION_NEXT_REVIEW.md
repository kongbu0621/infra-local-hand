# Q2 现场资格的下一有限范围复核

2026-09-29；复核基线 `bd3f5e038f9517b702590aa0ef6fdda99757562d`。
依据[补证后准入计划](Q2_POST_SOURCE_ADMISSION_PLAN.md)及原 H [需求](q2-host-window-consumption/REQUIREMENTS.md)、
[架构](q2-host-window-consumption/ARCHITECTURE.md)、[实施方案](q2-host-window-consumption/IMPLEMENTATION_PLAN.md)。
H A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37`、C `271c07cd16140aa5942dcf3fad468003c58b6b0e` 保持。
本文件是后续审查材料，不是新 A、Gate 关闭、来源采用或现场指令；原 R 和唯一未发行批次保持不变。

**本轮独立推进首次父目录分配观察与显式计费组件；H07、FS 及完整共同账单仍未通过。**
该组件属于已有 CLOSED H2/H3/H4，准确实现和验证见[组件复核](Q2_PARENT_ALLOCATION_IMPLEMENTATION_REVIEW.md)；
本文件的未来合同/资格材料不冒领组件测试或现场成功。
本轮不修改冻结 runtime，不新增 A，不安装监督器，不执行 host/guest 动作。
已完成的 wrapper/普通身份组件继续保留，不要求重复原文采集、维护或 probe。

## 父目录观察与计费组件的边界

修复目标是在 writer 已有首次读取处保留父目录 before/after 与 marker scan 的准确关系，
并用显式新版本表达同一子预留内的 actual/future 分类；旧版本不得静默接收新结果。
首次观察不能被后来 verify 覆写，不能从历史标量补造；身份漂移、分配缩小或溢出应拒绝。
marker scan 与随后 parent fstat 是有次序的观察，不是同时快照、因果证明或峰值证明。

令 C=65,536 bytes，M 为 marker 子树分配，G 为符合合同的首次 parent 正差：

| 项目 | 旧表示 | 显式新表示 |
| --- | ---: | ---: |
| marker 池 actual | M | M+G |
| marker 池 future | C−M | C−M−G |
| actual+future | C | C |

旧总预留 C 并未因此释放；不能写成“已证明旧账单少预留 G”。确认的缺口是 actual/future
分类及观察依据不完整。capture、device 与 summary 必须同步计算，不双抵 G，不增加 parent inode。
父目录旧基数 B 的来源、类别和覆盖仍须单独核对；G=0 也不能把未知 B 当零。
局部计算成立不证明完整 inventory、源采用、分配峰值、持久性或消费资格。

## H07：先准备合同与逐域证据

当前[旧启动入口](../../tests/e3_host/q2_startup_retry_entry.py)先 probe、后 anchor、再启动 outer；
collector 是另一条调用。后置相对 RuntimeMaxSec 不能证明首次传输、排队和初始化已受原绝对截止保护。
[supervisor](../../tests/e3_host/q2_supervisor.py)只声明目标控制器闭合；异常清理仅在取得 original 后停止。
已提交/排队但未取得 original 的路径，尚未证明撤销及截止后不再激活。

现有双钟较早余量、保守 envelope、迟到帧拒绝、有界 client capture、已绑定实例的 stop/树空检查可复用。
它们分别提供局部证据；client 退出、取消 Job 或一次空树均不是完整远端终止证明。
冻结 `q2_prepare_run.py`/`q2_supervisor.py` 不能通过替换字节修补原批次；
manager 另建单位也不当然位于 outer 子树。下一方案必须保留原 runtime 和固定父域绑定。

| 必须列入的域 | 下一材料须证明的关系 |
| --- | --- |
| host 入口与 SSH client | 同一原双钟、有限传输/输出/EOF；本地结果不冒充远端停止 |
| guest 会话、shell、sudo、probe/loader | 首次远端前已生效的准确监督；不能停止共享 sshd 或其他会话 |
| manager 请求、排队、outer | 请求/Job 身份、迟激活禁入、准确实例绑定及停止 |
| owner、supervisor、controller、ordinary 工作域 | 按固定计划逐域覆盖；停止端点独立于停止树 |
| collector、收尾与监督端点自身 | 同一原窗口、有限自退和费用；失败后不另起 collector |

可在原 H1/H3/H4 内先准备纯 RAM 合同：输入只含固定计划、准确来源清单、原窗口和证据 bytes；
不读现场、不执行进程、不接受调用者的 ADMITTED/allow 开关。至少分别校验：

1. 准确批准/源码/工具与采用用途；固定 host/guest boot 和原双钟。
2. 跨钟区间、误差/有效期、暂停适用边界；工作、停止、EOF/封存预留不晚于原截止。
3. 从计划导出的完整域清单；监督在首次远端前已经生效的证据。
4. 请求禁入、pending/queued 撤销、已绑定实例停止、树空及 EOF；未知项不补零。
5. 全部实际/未用承诺、监督和原生审计费用；不刷新时钟或另开额度。

状态须区分未派发、请求已提交、Job 排队、实例已绑定、停止待证与完整闭合。
“未观察到实例”不能等于“未派发”；完整闭合同时要求当前各域终止及未来迟激活已禁止。
只有 original 分支可复用现有 stop_original；无 original 的终结证据必须另行定义。
合同形状/模型通过不能解除现有 dispatch 或 field_readiness 拒绝。

有限验收包括：首次 arming 缺失、请求延迟越界、无 original、取消与激活竞争、同名换实例、
遗漏 sibling、stdin/初始化阻塞、client 消失、boot/双钟不符、空树后仍有 pending 请求、
collector 未覆盖及缺 EOF。检查准确状态和是否仍可启动，不只检查错误码。

## FS：先固定谓词与来源，不放开 flags

已回传 parent 的 INDEX/多块事实超出当前窄 profile；它不是永久属性，也不表示原机已经运行 writer。
现有 statvfs、GETFLAGS 和端点 metadata 不足以证明全过程分配峰值或掉电持久性。
后续[有限组件修复](Q2_H07_MODEL_IMPLEMENTATION_REVIEW.md)已在 `_geometry` 补拒
`INCOMPAT_EA_INODE` (`0x400`)，沿用已有 superblock 读取，无新增现场权限。
ACL absence 仍不能补成所有创建属性及隐式 inode 均不存在的证明。
这个收紧后的窄几何检查也不是完整峰值资格，完整入口仍在更早的 readiness 门拒绝。
下一 FS 方案应先完成下表，所有现场事实关联同一固定 host/boot/parent/device/mount：

| 资格谓词 | 准确来源及读取合同应包含 | 当前缺口/拒绝条件 |
| --- | --- | --- |
| 设备与挂载一致 | held parent、设备身份、固定挂载来源和原保护语义 | ext4 名称本身不等于资格；变化或未绑定拒绝 |
| block/cluster/features 适用 | 当前实现的受保护 device/superblock 原件，或经充分论证的等价来源 | statvfs/GETFLAGS 不能替代完整 feature 事实；普通身份不自动有 raw 读取资格 |
| 目录/extent 插入与失败残留有界 | 准确内核实现适用性、相关结构/算法上界、固定名称与读取范围 | INDEX/size 不给出分裂路径或峰值；held fd 不提供兄弟创建互斥 |
| 创建属性及隐式 inode 有界 | 创建路径、适用 feature/配置与属性来源 | ACL absence 不证明全部属性不存在；目录 scan 不覆盖全部隐式 inode |
| B/G/M 分类与承诺完整 | 原基数义务、首次观察、marker scan、准确账单来源 | 不把混合用途 parent 整体改归 capture；不双抵、不补零 |
| 同步与存储假设成立 | 文件/目录/必要父目录 fsync 链、错误处理、适用底层存储事实 | stat/SHA/close/CI 成功不是现场持久性；保留原可信存储假设，不承诺检测任意回滚 |

每个候选来源还须固定读取权限、对象/字节/时间上限、失败返回及采用用途，才能形成可评审接口。
本轮没有发现能以现有非 raw 事实完整替代资格的证明，也不据此断言不存在其它接口。
分配、保留空间与累计 I/O 必须分开；既存 JBD2 空间重复写不等于新增分配，
也不免除其他真实分配和 SSH/管理审计成本。写后 G 不能倒证写前峰值。

## 哪些继续做，哪些确实需要新决定

| 工作 | 准确边界 |
| --- | --- |
| 首次 parent 观察、显式 bill 版本、纯组合校验及隔离反例 | 已有 H2/H3/H4 内继续；新 schema 本身不要求新 A |
| H07 纯证据合同、逐域状态/验收、已有材料映射 | 已有 H1/H3/H4 内准备；不新增现场能力或自报 PASS |
| 在原读取保护、定位、预算/时钟内证明更宽 FS profile | 可属 CLOSED 内实现修复；先给充分来源/算法证明，不能仅放开 INDEX/size |
| 新只读 FS 接口 | 逐项对照原本地预检查范围；仅缺事实不自动重开，改变读取例外/信任边界才处理该变化 |
| 把 local-only 内核例外用于消费，或把未采用来源/字段升级为执行权威 | 属准确用途/来源变化；先固定受影响三文档 A、Owner B、独立 C |
| 新增首次远端前准备、监督器/timer/fence、权限/配置或提前持久对象 | 若超出现有准许机制/顺序，须窄 A 明确对象、来源、预算与终结语义；不重批整个 H |
| 改冻结 runtime、SSH 配方、VM 配置、消费定位或扩大额度 | 不属于本轮；不能作为资格修复暗中引入 |

下一顺序是完成本轮组件及准确验证，再整理 H07 合同和 FS 谓词来源表；
只对已经确定的 material 差异形成可审查三文档，不请求任意探测或未来任选接口的空白许可。
若实际需要独立准备阶段，必须明确其自身截止/停止能力以及与原 H07 的差异；
不能先用未受保护 probe 建立监督，再倒称首次动作已受保护，也不能自动续入 owner。
目前不向 Owner 发新的逐项操作请求。旧消费失败 INCOMPLETE 保留；新 startup 仍未发行。

## 一手机制参考

- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)：子树与 populated 语义。
- systemd v255 固定原文：[service.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/service.c)、[unit.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/unit.c)、[unit 文档](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.unit.xml)：相对 runtime 与 Job timeout 的界限。
- ext4 [目录](https://docs.kernel.org/filesystems/ext4/directory.html)、[superblock](https://docs.kernel.org/filesystems/ext4/super.html)、[EA_INODE](https://docs.kernel.org/filesystems/ext4/eainode.html)及[底层 writeback](https://www.kernel.org/doc/html/latest/block/writeback_cache_control.html)。

这些上游资料解释机制，不是现场版本、配置或设备资格。失联、不可中断 I/O、缺停止/EOF 时，
原 UNKNOWN/INCOMPLETE 规则继续适用；不得延长窗口或把局部组件通过改写为 Q2 通过。
