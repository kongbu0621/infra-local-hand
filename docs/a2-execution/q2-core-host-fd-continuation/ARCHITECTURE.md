# 固定历史 FD 持有与单份历史编码

**PROPOSED / Gate OPEN / NOT APPROVED**，`LH-Q2-CORE-HOST-FD-CONTINUATION-v1`。
依[需求](REQUIREMENTS.md)，本架构仅解决维护进入原核心路径的两个确定容量缺口。

## 有界 FD 所有权

在宿主现有来源读取、55件旧维护原件核对、VM/工具身份固定之后，preflight 之前，创建
一个匿名本地 socketpair 并 fork 一次。固定子进程源码置于
`tests/e3_host/q2_journal_retained_fds.py`，≤16384 B，纳入准确 D 的来源和安装验证；
不接受执行字符串、自由路径或可扩展插件。子进程不 exec、不 SSH、不写原件、不调用其它程序。

父子共享的固定只读清单来自已验证 profile：55个 basename、原持有 FD、原 metadata、
bytes/SHA和原锚身份；还绑定准确来源、nonce、D和完整历史摘要。目录/文件 FD 原封继承，
不经路径重新打开。继承后子进程立即关闭所有无关副本，包括 SSH key、工具、VM/其它数据
FD和对端 socket；这些对象仍由父进程持续持有。使用已知描述符范围关闭，不扫描宿主。

child 保留55原件、锚目录、唯一 IPC 端和必要标准流，确认原普通 UID/GID/组与父进程
准入一致。逐件核对原 fstat/name、owner/mode/nlink/dev、不同 inode、大小及SHA；保持
原 no-follow/no-atime、原锚身份和所有原保护谓词。父进程仍核对完整锚路径，child 使用
同一被持续持有的目录；正常新输出导致的目录变化沿用原 after_create 规则。

READY 包含固定集合及源绑定摘要，不接受缺项、额外项或自报任意集合。父进程保留所有
自己的副本直到收到有效 READY，并以 pidfd/PID-start 确认该子进程。然后一次性交还自己
55个副本的所有权，从父 `held` 中移除它们；其后每个原 recheck 边界必须先通过 child
的独立完整检查。交接途中异常只能停止，不能再次 fork、重新打开原件或切回路径校验。

协议仅 READY、CHECK、RELEASE 与其严格响应。绑定 nonce、D、集合摘要和递增序号；
最多64次 CHECK，请求≤4096 B、响应≤16384 B，累计IPC≤2 MiB。每次请求受原剩余
期限及单次5秒上限；固定双向 framing、EOF和部分写处理，不允许无界缓存或延长总期限。
检查返回仅已绑定元数据/摘要及实际结果，不复制全部原文；父进程原内存中完整原文仍保留
且按原规则验证。失败、错误序号、截断、child提前退出或计量未知均 STOP_AND_RETAIN。

维护现有 `bindings()` 和 `GrowthAnchor.recheck()` 涉及历史 FD 的路径统一接入该检查，
不留任何旧 `next(...fd...)` 读取已关闭编号的代码。旧维护禁止出现的后续输出检查仍由
父进程在原边界执行；跨集合不同 inode 检查通过原固定身份集合保持。修改任何证据内容、
同名替换、删除、硬链接或权限都必须被拒绝，不能仅信任先前 READY。

## 生命周期与预算

普通 preflight 与 execute 是原来两个调用，各最多一个 custodian；两者同窗费用累加。
child 只服务该调用，记录实际 PID/start、存活 CPU/RSS/退出状态；不建立后台驻留或自动
恢复。管理采样纳入该已知子进程的实际存活 CPU/RSS，wait 后纳入已退出子进程费用且不
重复计算；计量或身份缺失不得按零继续。相同120 CPU-s、512 MiB累计RSS和8控制子进程
上限约束父、custodian及原工具/SSH。VM费用仍按原规则独立受限。

连续身份保护保持到原调用的最后一个完整检查和结果保存。正常结果保存后，父进程释放
自己的其它持有对象时才向 child RELEASE并关闭IPC，child关闭原55FD并退出。父进程
在同一剩余期限内收回该准确子进程；不能将孤儿或UNKNOWN退出算作正常收尾。若收尾不
完整，顶层调用必须失败，条件核心发行器同时检查真实顶层退出、完整原件及维护状态。
早期失败也只释放该调用自己的 FD/IPC，不对 VM 或其它服务发信号；不执行恢复或重试。

预期源级下界/保守布局用于设计，FD1仍需真实限额验证：

| 时点 | 宿主描述符布局 |
| --- | --- |
| 交接前 | 原下一代121 + socketpair2 + child pidfd1 =124；另留身份检查临时3，至多127 |
| 交接后父进程 | 121−55 + IPC1 + child pidfd1 =68；生命周期余量20给出88 |
| child检查 | 55原件 + 目录1 + IPC1 + 标准流3，临时检查计入后要求≤64 |

不能只把一方FD或RSS记录为整个宿主上界。启动握手也必须测试，不能在旧峰值时用带额外
管道的 Popen启动 custodian。源码/环境导致实际布局不适配时停止发行，不提高128。
guard的暂时目录副本不属于原证据 FD，归还副本不释放任何证据身份。

## 完整历史只编码一次

新manifest v13在 `resume` 保留十一代完整历史；`inputs` 移除唯一重复的 `resume`，
改为 `resume_sha256`。其它 source binding 字段不删。计算摘要使用原canonical+LF规则。
规范重建操作先检查唯一字段集合、完整resume与55原件、引用值，再把完整resume放回
inputs并移除引用，得到原内存 source binding。desc.source_binding_sha256 对此完整
重建结果计算，不能对缩略inputs计算，也不能把新编码错误地应用到旧v2–v12原件。

manifest hash和marker依新实际编码计算。host、portable prior consumer、approved-input
和独立 dispatcher 均实现严格相同的验证；拒绝缺历史、错摘要、同时出现两种字段、混用
版本、自报成功和只改一端。custodian清单摘要也由这个经过完整验证的历史派生。

已留存旧63853 B形状加入第十一代的样本为66121 B；去重后54325 B。该样本未包含最终
所有 custody 字段和准确新A/C/D，不是发行证明。FD1须重新生成准确完整 marker、receipt、
pre/post description、真实压缩/展开bundle/argv、transition、approved-input和整包上界。
所有原上限不变，超出即继续离线修正，不用一个现场窗口验证静态长度。

## 新历史与两端协议

旧09b仅按其准确v12 manifest/receipt、v4 input和实际五原件验证。其特例为
LOCAL_IO_OR_TRANSPORT/errno24，空pre流、无完整transport记录、无guest报告，原事件和
nonce/来源/manifest/时钟关系必须一致。不得调用要求stderr含guest报告的旧通用分支，
不得推断SSH启动或guest动作；remote_exit仍UNKNOWN。其它十代验证不放宽。

新09c manifest/receipt v13、preflight v12、transition v12、reconciliation/history v16、
host-capacity v15。guest input/report继续v4，仅绑定新session及新source hash；运行时
动作和输出语义保持RT实现。新receipt在原字段外保留严格有界的custody关系和检查结果，
总大小≤65536 B。独立消费者要求新来源/所有权关系，不能把老receipt当作新完成证明。

FD2前准确D含全部生成/消费端并冻结。维护失败禁止生成实际核心包；成功则由原独立
验收读取完整原件、顶层真实退出与新boot/角色/身份后再发行原07a。核心自身的FD/资源
路径也做完整离线核算，不盲目复用维护父进程布局。原H01/Q4/H11业务语义完全保持。
