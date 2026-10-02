# Q2 原终端 namespace 独立参考：2026-10-02 最小候选

2026-10-02 +08:00。本文是设计审阅与来源边界说明，不是Owner B、独立C、implementation
或现场指令。候选三文档在[需求](q2-namespace-reference/REQUIREMENTS.md)、
[架构](q2-namespace-reference/ARCHITECTURE.md)、[实施计划](q2-namespace-reference/IMPLEMENTATION_PLAN.md)，
scope `LH-Q2-NAMESPACE-REFERENCE-v1`，状态 **PROPOSED / OPEN**，拟批准仅NS1–NS2。

## 当前来源为什么不足

已CLOSED K链的[架构](q2-kernel-fact-read/ARCHITECTURE.md)将原终端/proc/PID对齐明示
为环境前提，固定reader只读boot_id和自身数字PID mountinfo。
旧producer retry[需求R12](q2-old-producer-admission-retry/REQUIREMENTS.md)及
[实施计划P1](q2-old-producer-admission-retry/IMPLEMENTATION_PLAN.md)窄接入相同两来源，
没有授权status/nsfd/任意PID。procfs magic、mount ID、getpid和boot相符不能自行证明来源。
既有[完整K4回传复核](Q2_KERNEL_FACT_READ_FULL_RETURN_REVIEW.md)已有原件，保留其
局部kernel observations和未证项即可，不要求再找同一文件。

只补self status能发现部分proc/PID不对应，但一个内部一致的容器仍可通过；只让observer
交付nsfd同样缺独立原终端来源。最小充分候选选择“明确指定来源 + 固定直接进程关系 +
独立kernel FD对照”，其外部provenance前提明确列出，不能藏在self检查后。

## 固定来源锚和live对照

未来NS3由Owner直接在所选原host native本机终端以固定普通身份启动准确G，不接受任意
terminal PID、路径、caller FD、祖先进程枚举或container名称作为来源。Owner需明确接受
这次直接启动为reference provenance，以及准确pinned端点在session内按代码执行、没有
root/kernel/同UID runtime篡改的endpoint integrity前提；这两项尚未接受，先前storage/no-same-UID
storage-tamper决定不能代替。技术本身不能证明physical origin或任意hostile端点不存在。

G只fork两个单线程直系child R/O，G持有原两pidfd；R独立取reference的own pid/mnt nsfd，
O独立取observer的own nsfd。G从同一qualified procfs下内部fork PID固定路径独立取两child
nsfd与status，与两端实际交付FD比较；对象不同的替代FD不能让O自证错误namespace。
同一对象FD的原打开者不可技术区分，按固定代码取得own FD依赖明示端点执行前提。
R/O还经固定
匿名SEQPACKET进行两个32-byte nonce的双向交换和第二轮同heldFD对照。逐帧kernel
SCM_CREDENTIALS绑定原child，不误用socketpair创建时的SO_PEERCRED。无外部socket、relay
endpoint或任意FD入口。所有peer/object/source/nonce/session/顺序都严格绑定，拒绝后有限关闭FD。

`/proc/self`与`ns/pid`、`ns/mnt`是唯一新增magiclink例外；先完成held procfs/mount资格，
再以固定status `Threads=1`、single-level NStgid/NSpid匹配内部PID，核验proc PID视图
对齐。NSFS_MAGIC与NS_GET_NSTYPE只查询这两个held nsfd。无boot_id、mountinfo、stat、
readlink或通用proc来源，也不声称同boot。普通UID/GID三元与完整groups在操作前后匹配固定context。
接口依据是man-pages项目的
[proc_pid_status(5)](https://man7.org/linux/man-pages/man5/proc_pid_status.5.html)、
[pidfd_open(2)](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)、
[ioctl_nsfs(2)](https://man7.org/linux/man-pages/man2/ioctl_nsfs.2.html)与
[unix(7)](https://man7.org/linux/man-pages/man7/unix.7.html)；这些不是原机qualification结果。

原pidfd仍活着、G未reap、process/ns名称前后绑定、namespace对象全程held及两轮对照共同
避免PID/inode数字复用。Reference只在该session活体观察期间有效；退出/关闭后是历史
报告。O是standalone observer时，只证明O，不给另一个consumer PID或未来window发准入。

## 固定caps与资格边界

一个session固定：3个新单线程进程；FD≤24/进程、≤72aggregate；artifact≤256KiB、
内含context/manifest≤16KiB；status每读≤16KiB、≤12读/192KiB aggregate；指定namespace
open/rebind≤40次；两个nonce合计64bytes；IPC≤16帧、≤4KiB/帧/64KiB总payload；stdout≤32KiB、
stderr≤8KiB；RAM≤128MiB、CPU≤5s；双钟total≤30s=20s观察+5sstop+5s退出/EOF/report。
原双钟先于proc/身份观察，阶段固定绝对截止，不刷新。collector新持久对象/网络均为0；
匿名IPC、既有fixture监督及原生audit成本不能据此记零。
G常驻参考FD为21，SOURCE重复FD逐帧最多2个，比较后立即关闭；status/rebind串行，
不长期保留两份SOURCE产生25FD峰值。准确launcher仅stdio继承，不用新增proc/self/fd扫描
或无限probe来宣称unknown FD absence。
FINISH后R/O各对交叉通道shutdown-write并真实读peer EOF才正常退出，不加第17帧；
G只直接观察自己两control EOF和原child wait。cross EOF按pinned child代码/正常exit
来源单列，G自身exit与双流EOF只能由外部fixture监督/有限receipt证明，不提前自证。

NS2只在manifest明确supplied isolated fixture及其已有普通supervisor下验证，最多12个
顺序case，共≤360s/60sCPU/480KiBoutput，不自动重试。RAM/CPU/原process stop/EOF的准确
enforcement/成本来源缺失就BLOCKED，不能新建manager/cgroup、提权或改系统配置。
pidfd signal和deadline guard不证明不可中断内核调用绝对停止；缺原wait/EOF或超时为UNKNOWN，
外部cleanup不补成功。接口语义/ABI和每项caps目前均为待资格要求，未声称已通过。

NS1–NS2不接consumer、不生成P4包；未来NS3需要准确私有artifact、独立Owner稳定event/ref、
明确provenance接受和原host local-only监督/费用资格，仍无SSH或消费。NS4实际consumer用途
另需受影响准确A/B/C/D：实际O PID/source、活体reference、原150s/300s双钟、费用/stop/EOF
与失败状态逐项绑定。随后P4仍需其准确包的独立发行event/ref，H07/FS也仍需各自资格。

## 三文档的material补充

| 文档 | 本候选准确增加 | 保留边界 |
| --- | --- | --- |
| 新需求 | 独立provenance/execution前提、固定status/nsfd来源、magiclink窄例外、G/R/O及普通身份、FD/PID活性/两轮nonce、全部caps和NS1–NS4用途 | 原K两来源与旧retry准确A字节不变；原storage接受不扩张；NS3/4排除 |
| 新架构 | fixed direct-fork source chain、G独立child FD、nsfs/procfs资格、16帧匿名IPC、原pidfd/nsfd生命周期、strict来源/报告和停止界 | 不加入stat/readlink/boot/mountinfo通道、外部参考daemon或host策略更改 |
| 新实施计划 | R→准确A→OwnerB→独立C→NS1 D；synthetic负例/explicit isolated native12-case；后续NS3 artifact/event和NS4准确集成条件 | 无虚构B/C、qualified结果或P4运行权；unsupported/缺资源/stop来源保持BLOCKED/UNKNOWN |

候选能在明示前提成立时证明指定reference与当前observer的namespace关系及proc PID
视图对齐；它不技术认证physical host、全局initial namespace、同boot、usernamespace或
未来consumer，也不补足H07与FS。该充分/不足边界和未qualified状态是候选合同的一部分。
