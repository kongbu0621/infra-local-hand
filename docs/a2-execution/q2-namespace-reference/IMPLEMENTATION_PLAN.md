# Q2 原终端 namespace 独立参考：实施计划

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-NAMESPACE-REFERENCE-v1`；拟关闭 **NS1–NS2 only**。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本计划；R 与两文档一致。
- 目前没有准确 A commit、Owner B、独立 C 或新 implementation D。本文是拟实施路线，
  不能由“继续修复”或原 Q2 CLOSED 记录自动生成本新来源的源码/现场权。

## 准确 A/B/C 前的工作

当前只读复核已证明已有 K/consumer 两来源不足以证明原终端/proc/PID namespace 对齐。
本文固定新增来源、magiclink 例外、普通身份、G/R/O、pidfd/nsfd、IPC、caps、候选前提和
NS1–NS4 分界；没有运行新 proc 查询、collector 或原终端命令，没有新 dependency 或
runtime/configuration。既有 K4 retained 回传不重交，旧 batch/candidate/现场结论不改。

准备准确文档提交 A 后，由 Owner 对原 R、该准确 A、NS1–NS2 scope 和两项候选前提
作可核验决定 B；若只批准 isolated fixture reference 而不接受原终端 provenance，B 必须
明确这种范围，不能解释为原 host 参考已采纳。先独立 bookkeeping-only C，再形成 D；
不得把 C 与 source/test squash。NS3/NS4 仍排除，Owner 决定不能由本计划合成。

## NS1：固定 standalone 合同与实现

仅从本范围独立 C 的后继开始，不修改 K reader、consumer、生产候选、P4 dispatcher 或
现有 runtime/configuration。collector 与 fixture/test source 单独命名和登记为本范围 D。

首先确认并固定 primary interface 来源/ABI 与支持矩阵：procfs self/status 中
NStgid/NSpid 的 mount-relative namespace 语义、单线程 getpid 关系、proc/self 的固定
magiclink、pid/mnt nsfd 身份/NS_GET_NSTYPE、pidfd 生命周期/退出/SIGCHLD 条件、
SO_PASSCRED/SCM_CREDENTIALS/SCM_RIGHTS/SEQPACKET 的 credentials、截断和 FD 生命周期。
这些接口语义和准确 fixture Linux x86_64 LP64/kernel/runtime 必须相互绑定；未知平台
不新增 syscall number 或 generic fallback。接口来源证据不等于原 host 已支持接口。

固定代码只实施：

1. G 单线程、恰好两次 fork、原 pidfd 与正常 reap；固定两轮表及唯一 syscall/source枚举。
2. proc held ancestor/mount qualification；仅 self 和 pid/mnt 两类 magiclink 例外；
   status 严格有界解析，nsfd 的 fd 级 NSFS/type/身份，G 独立 child 对照。
3. 三个匿名 socketpair、逐消息 credentials、16帧/两个nonce/固定FD数量，strict JSON
   与固定 source/runtime/context/fixture/session binding；没有环境/CLI PID/path覆盖。
4. 固定 ordinary guard、原双钟和所有 caps；失败首错、原退出/EOF、有限报告和 FD cleanup。
5. 结果 schema 中 NS1–NS2 不允许 `OWNER_DESIGNATED_TERMINAL_MATCHED`，更不允许
   consumer/field readiness、同 boot 或 P4 权；各种合成/fixture状态分开。

纯 synthetic 反例至少包含：

- status 缺字段/重复/多级/非整数/单线程与 PID不符，proc子挂载、普通假文件、资格未通过即读取；
- unknown proc source、caller PID/path、self以外 link、错误namespace类型/设备/名称、释放后复用；
- child 在pidfd前/后退出、提前reap、PID复用、原fd被替换、只有数字PID或JSONinode匹配；
- O交付与其实际对象不同的R/其它进程FD、双方自报相同inode但G独立child FD不符、
  同对象复制不能区分最初打开者而仍不得冒充provenance证明、参考错误而内部均相符；
- stale/重复/乱序nonce、role/session/source/context更改、wrong SCM credentials、SO_PEERCRED误用、
  MSG_TRUNC/CTRUNC、多FD/ancillary、拒绝FD泄漏、FD和帧/bytes超界；
- 每阶段身份漂移、两钟逆转/过期/暂停、prepare后新观察、时间预算刷新、缺TERM/KILL停止或EOF；
- report截断、stderr/CPU/RAM/task/FD/读总量超界，成功状态提前发布，standalone结果跨PID/未来session采用。

synthetic 测试不执行 host/guest I/O；native test 必须显式区分，unsupported结果为
BLOCKED/SKIP且给准确原因，不能把mocked FD/syscall通过作为native资格。

## NS2：明确 isolated fixture 的 native qualification

fixture 必须已经存在、由固定 manifest/context 准确提供，采用普通非root身份及既有
supervisor/runtime。manifest ≤16KiB，artifact ≤256KiB，绑定准确 D/source/runtime、
Linux x86_64 LP64/ABI、普通UID/GID/groups、fixture来源角色、原deadline/caps及
supervisor/收件/原生审计计费来源；没有free PID/path/command 或自动探测替代设施。
该fixture不被采用为原host来源，不联系guest，不创建namespace/账户/cgroup/mount/config。

每个native case都是一次独立 ≤30s 的session，使用同一 3-task /24-per-process-FD /
72-aggregate-FD /128MiB /5sCPU /40KiBoutput caps。NS2完整批次最多 **12个case**，
顺序运行、不并行；总elapsed≤360s、总CPU≤60s、总输出≤480KiB、合计source status读取
≤2304KiB、artifact重用不重复生成，无失败自动重试。全部case的RAM峰值仍≤128MiB，
新增持久对象/网络仍为0；fixture audit与收件增量成本按准确manifest另登记，未知即停止native批次。

固定case表：

| Case | 目标 |
| --- | --- |
| N01 | 普通身份下真实proc资格、self/status、pid/mnt nsfd、G独立child与双向两轮正常关系 |
| N02 | 活体原pidfd、未reap/真实wait与EOF正确关联；child提前退出真实拒绝 |
| N03 | 匿名SEQPACKET逐帧真实credentials、two-nsfd SCM_RIGHTS与关闭行为 |
| N04 | 使用本进程已有pid/mnt FD颠倒两角色的真实交付，NS_GET_NSTYPE与角色关系拒绝；同对象FD复制不冒称可区分打开者 |
| N05 | 真实nonce replay/乱序帧拒绝，有限排队FD回收 |
| N06 | 准确launcher stdio-only合同、已登记继承关闭表、G21原参考+串行2SOURCE临时FD实际峰值；不扫proc/self/fd，无额外task/thread/exec |
| N07 | 固定leaf可读/失败errno与无fallback；不能访问的fixture明确BLOCKED |
| N08 | status/IPC/report真实超界与EOF处理，失败输出仍在总界内 |
| N09 | 两钟原deadline到期，无刷新/超期观察；暂停语义仅在已 supplied clock fixture 下资格 |
| N10 | TERM/KILL只对原child pidfd；G两control EOF直接观察、cross EOF由pinned child真实观察后正常exit支持，原wait与外部G双EOF分开；缺项UNKNOWN |
| N11 | supplied ordinary supervisor 的RAM/CPU/stop/EOF上界证据与准确增量计费 |
| N12 | artifact/runtime/context/session封装、finite报告、枚举用途与standalone不采用为consumer |

不支持N09暂停fixture或N11资源/停止证明时，只完成其它局部观察，整套namespace native
qualification保持BLOCKED，不临时 provision 或扩大权限。G/R/O真实同namespace时不能
造假宣称检测到不同namespace替代；本固定N04不打开或接收其它fixture namespace来源，
collector不创建新namespace，也不开caller FD通道。不同namespace native负例标
`NOT_PROVEN_BY_THIS_FIXTURE`，由synthetic关系反例与绑定primary接口语义支撑条件论证；
若以后需要已有独立namespace fixture的真实负例，须先准确固定其来源/对象/FD交付边界，
不能把“明确fixture”当空白新增来源权。

NS2 acceptance须全部适用negativecases、真实source/FD/credentials关系、资源/期限、原退出
与EOF齐全，公开保留脱敏来源/摘要/结论及全部失败，raw fixture evidence私有。即便通过也只
产生`FIXTURE_LIVE_REFERENCE_MATCHED`，`field_ready=false`、`allow_run=false`保持。

## NS3：后续原终端local-only采集的准确输入清单

NS3不由本NS1–NS2 B/C发行。只有选择继续并形成准确批准时才：

- 固定准确私有artifact basename/bytes/SHA、source D、已有runtime/context、固定普通身份、
  两项前提的Owner接受记录、原终端直接启动方式与reference有效期；不添加terminal PID/path。
- 固定原host ordinary supervisor/原stdout/stderr收件证据、30s及每项caps、实际RAM/CPU/stop/EOF、
  原生audit/收件增量成本与合法留存；这些来源尚未资格，不能借NS2的fixture值替代。
- Owner以独立稳定NS3 event/ref绑定上述准确artifact与一次local-onlysession，无guest/SSH/
  marker/consumer/P4、失败不自动重试；artifact完成后才有可审阅发行对象。

这不是当前Owner询问，也不要求重交既有K4或storage决定；未具备上述链时保持NS3 NOT AUTHORIZED。

## NS4：另行consumer用途与P4

把standalone O改为实际consumer、继承namespace参考/端点、读写来源、deadline、费用或
权限用途，是material集成。必须先形成准确受影响补充三文档A、OwnerB、独立C，再从其后
实现D，不能将本D直接改consumer。该A须明确实际consumer就是被G持有pidfd并独立对照的O、
活体G/R生命周期覆盖实际准入、前提来源/固定kernelviews、原150s preparation/300s outer
不刷新、全部host资源/audit/stop/EOF计费以及现场failure/replay状态。

NS4如获准确批准与技术qualification，只补一个namespace硬门；H07与FS资格仍独立。
旧producer retry独立Owner P4准确包发行event/ref仍必要。NS3或NS4决定都不是P4消费或运行，
本提案不发行20261002a、改已冻结产品、创建host intent或连接guest。
