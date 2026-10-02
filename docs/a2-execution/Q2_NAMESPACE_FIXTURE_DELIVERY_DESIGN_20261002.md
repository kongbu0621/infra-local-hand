# Q2 namespace fixture 完整交付设计复核（2026-10-02）

本页是新 proposed scope `LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1` 的设计复核。权威候选文档为
[需求](q2-namespace-fixture-delivery/REQUIREMENTS.md)、
[架构](q2-namespace-fixture-delivery/ARCHITECTURE.md)和
[实施计划](q2-namespace-fixture-delivery/IMPLEMENTATION_PLAN.md)。当前Gate仍OPEN；本文不授权源码、
测试、远端请求或system change。

## 为什么旧候选不能直接批准

旧 proposed A `dfdd653dd48388d8ab1a2554d16bf5b610edba10` 只覆盖NS1 standalone模块与
NS2隔离环境验证，却要求准确普通supervisor、资源、暂停、stop/EOF和audit设施已经存在，并
禁止在范围内准备。后续readiness audit准确结论为`NOT_PREPARED`。旧A没有Owner B或CLOSED C，
所以批准它不能补出缺失设施；把准备工作当成“测试前置”也会绕过R→A→B→C→D。

新候选同时覆盖最小runtime fixture、模块、验证、一次交付和收尾，并把旧候选登记为
`SUPERSEDED_PROPOSAL_NOT_APPROVED`。旧文档、摘要和审计不改字节，不描述成CLOSED后reopening。

## 为什么不用systemd transient service

第一版新稿曾考虑每case调用`systemd-run --pipe`。仓库已有
[H07未决请求源码复核](Q2_H07_PENDING_REQUEST_SOURCE_REVIEW.md)：所查systemd路径中，客户端
timeout、断连、一般错误和AddRef消失都不是StartTransientUnit撤销事务；请求入队后仍可能丢失
回执。后来一次Stop/Cancel也不能证明原请求不会晚激活。把该路径用于fixture会重新引入已经
查明的停止缺口。

最终路线不向systemd manager发Start/Stop/Cancel/write；只按F0固定的唯一只读来源、API、字段和
调用次数核对旧allowlist。固定carrier只执行一个RAM bootstrap/guardian L；L在`BATCH_RELEASE`
前自限且只读。`BATCH_RELEASE`后，它在已资格root-only cgroup2 anchor下创建空batch distributor B、guardian
和supervisor sibling leaf。L进入guardian后对outer fd1/fd2保持零write；最多37个pre-action记录各经
一次有界self-only carrier往返取得owner durable ACK，迁回guardian并封口证据后才放行动作，最后再
按实际0或1次进入carrier导出结果。S用`clone3(CLONE_INTO_CGROUP|CLONE_PIDFD)`让每个bootstrap child
原子出生于fresh case leaf；没有数字PID迁移、queued manager job或late transient activation。

carrier请求本身仍可能迟到，因此owner在request前固定三钟outer deadline；bootstrap必须完成同连接
HELLO/`BATCH_RELEASE`、boot、RTT和owner/guest realtime skew核对，且`BATCH_RELEASE`前禁止外部
create/write/fork，唯一例外是W在自身guard已生效后clone L。owner消失、EOF或过期
只能产生有界只读拒绝；不能把SSH/client timeout写成“server未执行”。

既有carrier是`env-bash-literal-ssh-v1`：host把准确argv经`shlex.join`变成唯一远端command
string，远端固定login shell解析一次。新合同把它限制为
`exec /usr/bin/sudo -n -- /usr/bin/env -i LANG=C LC_ALL=C ABS_WATCHDOG WATCHDOG_ARGS -- ABS_RUNTIME -I -B -c FIXED_LOADER TOKEN`。
TOKEN为≤32KiB源码的无padding base64url，整串≤48KiB并保留stdin。`ABS_WATCHDOG` W必须是目标上
已经存在的sealed native对象；本范围不上传、编译、安装或替换它。F0在request前固定W的absolute
path、mount/dev/inode/size/uid/mode/不可写祖先、SHA-256/version、ELF class/machine、PT_INTERP、
loader、完整`DT_NEEDED`、source→binary relation、argv/env/cwd/umask、cap/securebits/seccomp/LSM、
affinity/scheduler、无setid/file-cap、退出映射和资源表。固定来源证明W不存在或不匹配时结果为
`NOT_ISSUED`；只有发SSH后才可观察的失败保持delivery consumed并按原证据分为BLOCKED或UNKNOWN。
local launch env删除`SSH_AUTH_SOCK/SSH_AGENT_PID`，认证只使用固定identity file。wrapper/shell/
sudo/W/runtime/parser、identity或round-trip任一来源不能固定时，F0直接`NOT_ISSUED`。
同一门还必须证明wrapper不读stdin/不重定向、SSH no-PTY且stdin二进制透明、stdout/stderr分离，
并排除ForceCommand、authorized_keys命令/环境、ssh rc、BASH_ENV/ENV、shell startup hook、sudo
use_pty/I/O plugin对协议stdio/argv/env的消费、注入、重定向、合并、替换或额外协议字节；`env -i`
发生太晚，不能替代这些证明。预算内认证、audit/journal和session metadata允许但必须单列。

W是SSH顶层远端程序和L的准确parent。W动态loader入口到自身guard arm完成是明确列账的
pre-arm TCB prefix：只在已批准endpoint integrity premise、sealed loader closure和F0/F2静态最坏
envelope下接受，不声称这段已经获得远端kernel CPU或wall hard guard；W唯一clone前没有L、B或
fixture mutation。F0从封存source/loader/launcher关系和独立fault/trace固定
`W_PREFIX_CPU_MAX_NS≤1s`、`W_PREFIX_WALL_MAX_NS≤2s`、单task、userspace AS/RSS与保守物理风险
≤64MiB、入口installed FD≤8、outer read/write=0及pipe/kernel-object/audit bytes/inodes；它们全部进
首次发行前carrier预算，不能资格化即不发。W以`getppid→PR_SET_PDEATHSIG(SIGKILL)→getppid`消除
parent-death race，两次parent必须相同、非1并按manifest固定proc-identity规则资格化；W再定义
`W_BLOCKED_SET={SIGCHLD,SIGUSR1,SIGHUP,SIGTERM,SIGINT,SIGQUIT,DEADLINE_SIGNAL}`。它先把完整signal
mask归一为空、把全部catchable disposition归一为manifest固定初态并逐项readback；其中SIGXCPU为
`SIG_IGN`，该集合中的全部catchable signal为`SIG_DFL`，SIGCHLD的
`SA_NOCLDWAIT/SA_NOCLDSTOP`清零。W随后block并readback准确`W_BLOCKED_SET`，验证stdio后关闭
所有更高FD。它先为自己设置/readback
CPU `(8,9)s`、AS/DATA `(64,64)MiB`、NOFILE `(8,8)`、CORE/FSIZE零、STACK 8MiB及完整固定profile，
再以CLOEXEC signalfd=3接收准确`W_BLOCKED_SET`，取得W0并把CLOEXEC BOOTTIME timerfd=4
absolute arm到不可刷新的`W_KILL_DEADLINE`。`W_REMOTE_EXIT_DEADLINE=W0+830s`；manifest固定有限
`W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS`、`W_KILL_TO_REAP_MARGIN_NS`和
`W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`且三者和≤12s，分别定义更早的kill界与
`W_KILL_DEADLINE=W_REMOTE_EXIT_DEADLINE-W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS-W_KILL_TO_REAP_MARGIN_NS-W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`及
`W_REAP_DEADLINE=W_REMOTE_EXIT_DEADLINE-W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`。
timerfd只提供可读事件，因此F0/F2/F3须分别资格化wake→pidfd kill、kill→typed wait/reap及reap→W
`_exit`/SSH status/EOF。除不可中断kernel wait、W自身被SIGKILL或endpoint premise失效这些明确
UNKNOWN例外外，deadline路径必须证明kill不晚于
`W_KILL_DEADLINE+W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS`、reap不晚于`W_REAP_DEADLINE`、remote
status/EOF不晚于`W_REMOTE_EXIT_DEADLINE`；不能把830s相对界外推到这些例外。

W用完整固定的88-byte `clone_args`、`flags=CLONE_PIDFD`、`exit_signal=SIGCHLD`、有效对齐pidfd输出和
其余零字段创建唯一L。L从出生即继承SIGXCPU ignore及CPU `(8,9)s`，故native stub、runtime loader和
首个user-code前的CPU都受hard 9s backstop。child首段native执行
`getppid→PR_SET_PDEATHSIG(SIGKILL)→getppid→SIGSTOP`；W用
`waitid(P_PIDFD,...,WSTOPPED|WNOHANG)`消费并核`CLD_STOPPED/SIGSTOP`、live pidfd、PPID/starttime。
只在这个stopped window，W用同次clone返回的numeric PID调用固定
`prlimit64`表，复核CPU `(8,9)s`并设置/readback AS/DATA `(64,192)MiB`、NOFILE `(32,64)`、CORE零、
FSIZE 4MiB、STACK 8MiB、NPROC及其余pair；这不是数字PID迁移fallback。W再用pidfd发送唯一SIGCONT。
child关闭继承的W signalfd/timerfd，但从clone起保持并readback继承的`W_BLOCKED_SET` mask；它建立
manifest固定L exec前disposition（SIGXCPU=`SIG_IGN`、其余catchable=`SIG_DFL`）并核FD恰为0–2，
才exec runtime。这样W在loader/首码窗口转发的SIGUSR1只会pending，不会按默认处置提前终止L。

W关闭自己对fd0–2的引用且不读写协议流，steady只持signalfd/timerfd/L pidfd，以单线程`ppoll`并行
观察三者。child放行前收到`W_BLOCKED_SET-{SIGCHLD}`任一stop source、内部完整性错或kill deadline
都只向准确pidfd发SIGKILL；放行后收到该stop set至多一次向准确pidfd转发SIGUSR1，固定grace后仍未
exit才SIGKILL；deadline或internal error不走grace。发出任何kill后，W只以
`waitid(P_PIDFD,...,WEXITED|WNOHANG)`和absolute-time `ppoll`做nonblocking终态循环直到
`W_REAP_DEADLINE`；到界仍未reap即非零退出并把child/B保留UNKNOWN。SIGCHLD只驱动上述typed wait，
deadline与child exit同时ready时deadline优先。W只在准确
`waitid`得到L `CLD_EXITED/0`、从未触发deadline/stop/error且W累计process CPU≤1s时返回0；其它状态
按sealed manifest映射为粗粒度非零，不
冒充raw wait status。owner看到的是W的remote status；只有sealed映射加W status 0才证明原L正常
退出。L可以先关闭两条流，所以双EOF可先于W status，owner必须并行取得二者。W异常死亡由L的
PDEATHSIG fail closed；W/L处于D-state、无法wait/reap或缺状态/EOF闭环时准确保留UNKNOWN。

## 复用与新增边界

| 历史对象 | 新候选怎样使用 | 必须现场重证 |
| --- | --- | --- |
| Q1 isolated KVM guest | 唯一test-only target | guest/boot、carrier、runtime、kernel和容量 |
| Q2 ordinary账户/主组 | G/R/O的固定identity | UID/GID/完整groups及除allowlist外无同UID工作 |
| active `user@UID.service` | 精确allowlist、只读保留 | MainPID/Invocation/cgroup/固定子树；不启动或停止 |
| sealed native remote watchdog W | SSH顶层程序、L准确parent、L从出生后的wall backstop和原退出映射 | 上述对象/loader/source/parent/signal/limit/资源/期限合同；缺失不安装 |
| Q2旧manager/七根/ledger/失败实例 | 禁止修改与累计费用输入 | 当前关系、无本批消费或漂移 |
| cgroup v2 root anchor | 只在其下create-only建本批B | root-only、非ordinary delegation、无其它writer、controllers已由祖先启用、初始dying=0、记录live基线D0、depth余量≥2、计D0后slots≥4；结束复原D0/dying=0 |

新对象只有RAM L、含≤8个bundle/一个固定64KiB action journal/一个固定752KiB result journal/
十二个固定16KiB预分配case intent的完整`/run` stage、
B/guardian/supervisor/fresh case leaves、S、G/R/O、cleanup continuation在verified carrier建立并封印的
一个临时executable memfd及证据记录。该memfd≤bridge size，payload逻辑/RAM/AS≤1MiB，含folio/THP/metadata/allocator的瞬时物理风险≤2MiB/1 shmem inode；FD关闭
后mapping只保留至L退出。
不创建账户、unit、mount、namespace、package或dependency，不改parent controllers、sysctl、LSM、
journald/audit、fstab或旧对象。
新B必须保持空procs并读回`cgroup.controllers`恰含四项：先写/readback固定cpuset与自身cpu/memory/pids limits，再只在B唯一写
`+cpu +cpuset +memory +pids`并严格读回恰四项，才可创建guardian/S/case。三个child均为domain leaf、
`cgroup.subtree_control`空且cpuset/effective mems准确；anchor始终只读。

## 进程与停止关系

```text
delivery owner / carrier
          |
          v
W (sealed native watchdog; exact parent, pidfd + BOOTTIME deadline)
          |
          v
L (root, single-threaded; guardian ↔ bounded original carrier excursions)
          |
          +-- clone3 --> S (supervisor leaf, root, subreaper)
                              |
                              +-- clone3 --> bootstrap --drop/exec--> G (fresh case leaf)
                                                                  +--> R
                                                                  +--> O
```

W从唯一SIGCONT到L被wait/reap始终持准确L pidfd和不可刷新的BOOTTIME deadline；L从native stub到最终
退出始终保持`PDEATHSIG(SIGKILL)`并核W的PPID/starttime。L从clone起继承并在exec/loader中保持
`W_BLOCKED_SET`；W放行后收到其中除SIGCHLD外的stop source时向L至多一次转发SIGUSR1，所以早期转发只会
pending。W异常死亡则由PDEATHSIG直接fail closed。L持S pidfd；每case在`EXEC_GO`前，L还持bootstrap
child pidfd和held leaf fd并回ARMED。L在S失败、carrier EOF、
case/batch deadline时对准确leaf执行`cgroup.kill`。S作为subreaper收回G异常死亡后准确reparent的
R/O；如果S本身死亡，L仍可证明pidfd exit和空树，但缺typed waits的结果只能UNKNOWN。
每个动作的固定顺序是action journal→关闭临时FD→单线程/held资格→迁carrier→membership→stdout
记录/owner fsync ACK→迁guardian→membership/result excursion slot→才放行S，整次≤2s且无重试。
L在entry、首次迁入guardian、每个动作迁出/迁回、需要final迁出时和clone S前，S在entry及每次clone前都须由held procfs证明`Threads=1`；
这同时保护CPython fork hooks和guardian/S各自pids.max=1。

L出生即有W预置并readback的RLIMIT_CPU `(8,9)s`和SIGXCPU ignore；hard 9s加资格化overshoot把
native stub、exec、dynamic loader/import到首个user-code的全部CPU封在carrier physical 10s内。L
入口首个process-clock sample后立即验证准确W parent、PDEATHSIG、继承limit/disposition和准确
`W_BLOCKED_SET` mask，再从同一held procfs核`Threads=1`，随后资格化Q0/limit、建立并arm/readback
fatal timer、紧邻复测并固定G0。它此时再block SIGXCPU、恢复其`SIG_DFL`，创建/readback接收
`W_BLOCKED_SET∪{SIGXCPU}`的新signalfd并优先处理loader窗口已pending的stop；只有无stop、fatal guard
active、CPU仍在最早候选内且CAP_SYS_RESOURCE已资格化，L才把CPU提高/readback为供S继承的
`(20,100)s`。raise后立即再次耗尽signalfd并核pending，任何stop/XCPU都不得进入success。该signalfd
及前后PPID核对观察
准确W parent death、可捕获断线信号和wall deadline；SIGALRM保持unblocked/`SIG_DFL`，只供
process-clock fatal timer；SIGPIPE固定ignore，EPIPE走同一停止机。owner只在原三钟outer deadline
最早值前10s关闭carrier stdin写端、保留双读端，以EOF触发L；到原deadline只kill本地client group，
不冒充远端kill。远端由L原deadline/EOF/cgroup.kill做有证据的正常收口，W deadline是最后的远端
wall kill backstop；该10s容纳最多5s TERM和随后的cgroup.kill/wait/empty/EOF/receipt，local
hard-kill结果本身只能UNKNOWN。S、bootstrap、
G、R/O使用`PDEATHSIG(SIGKILL)`。PDEATHSIG在fork child中初始清零，
凭据变化也会清零，因此各进程在正确阶段设置并核对，bootstrap在setresgid/setresuid后必须重设。
它只补充guardian，不替代
cgroup.kill、wait、empty tree和EOF。kernel D-state或guardian本身失效仍保留UNKNOWN，不承诺
所有内核故障在期限内释放。

L/S从CPython主线程持GIL调用预编译native bridge。它固定88-byte `clone_args`、唯一INTO_CGROUP+
PIDFD flags和SIGCHLD；child首个native syscall设置SIGKILL PDEATH并核PPID，再执行CPython child
fork hook，之后只在native内wait/drop/净化/exec或`_exit`，绝不返回Python。同一bridge还导出cleanup
setup/arm和不返回的`fixture_cleanup_tail`，固定receipt/digest/signal/write/close/exit路径。bridge C source、两个
byte-identical clean build、compiler/flags、SOABI、ELF/loader依赖和完整导出符号全部入manifest；L与
exec后的S各自从held stage fd验摘要并经已资格`/proc/self/fd/N`独立加载。任何after-fork Python
callback、guest build或mapping跨exec假设都使资格BLOCKED。cleanup exec销毁旧mapping；continuation
不得直接重新map可能带B charge的stage inode，而须在carrier复制到新sealed executable memfd并只从
该新inode加载tail mapping。

## 普通身份、dumpability与core

bootstrap仍为root时先清ambient/keepcaps并drop bounding set，再setgroups完整列表、
setresgid/setresuid、清residualcap、设NNP；随后重设PDEATHSIG并核对PPID，最后设dumpable=1。
runtime/collector必须无setuid/setgid/file capabilities；exec后G再次核对全部状态。
F0枚举并固定全部RLIMIT。W在放行L前设置initial profile；L建立fatal guard后凭已资格
CAP_SYS_RESOURCE把CPU提高为`(20,100)s`，AS/DATA与NOFILE保持soft/hard分离，为S保留准确上限。
创建S时child在native gate保持未放行；parent clone返回后，在等待`BOOTSTRAP_READY`或放行S之前，L
立即将自身CPU/AS/DATA/NOFILE收紧并readback为
(19,20)s/(64,64)MiB/(64,64)MiB/(32,32)，失败即kill准确S并停止。S只把已继承的CPU/AS/DATA/
NOFILE soft提高到hard，不依赖CAP_SYS_RESOURCE，独立readback后才回`BOOTSTRAP_READY`。成功另要求
guardian/carrier CPU各≤9s、L process
`CLOCK_PROCESS_CPUTIME_ID≤18s`。L首样本后先从同一held `/proc/self/status`核`Threads=1`，再在任何
 timer前读取同一real UID占用Q0、把RLIMIT_SIGPENDING设/readback为有限`(Q0+8,Q0+8)`。只允许initial
和cleanup-continuation两个timer generation，每代按fatal/BOOTTIME/MONOTONIC/REALTIME固定四个
call site create且同时live≤4；完整success路径每代四项、总计八次，失败只停在固定序列前缀且全程
create≤8，禁止额外或第九次create。四项reservation加四项event margin覆盖每代live timer和exec竞态。
cleanup短时启用的`ITIMER_PROF`不是`timer_create`对象，不计入上述八次，也不占Q0的POSIX timer
reservation；其SIGPROF pending另由跨exec guard合同独立核对。
initial顺序为process sample→W/PDEATH/profile/继承`W_BLOCKED_SET`→Threads=1→Q0/limit→fatal
arm/readback→相邻复测→G0→block SIGXCPU/恢复DFL→新signalfd接收`W_BLOCKED_SET∪{SIGXCPU}`并处理
pending stop→CPU raise/readback→再次耗尽并核pending→三个wall timer create/readback；
BOOTTIME/MONOTONIC先arm到G0+48s，
REALTIME在DECLARE含UTC字段且验证
前保持已创建但disarmed。exec前排空全部blocked stop/deadline pending；continuation先取得P0并从继承FD4核
`Threads=1`，但cleanup exec另有跨exec的ITIMER_PROF与临时RLIMIT_CPU guard，不能只依靠随后重建的
POSIX fatal timer。continuation在这些guard仍active时按preparse公式重建fatal，排空继承event并核
SigQ=Q0+1，之后才验H并建立其余三项。

L以同一process-clock连续样本作为域CPU主账，`CPU_SAMPLE_ROUND_NS`向上计；明确区间计本域，迁移
歧义区间向guardian/carrier双计，guardian `cpu.stat`只作交叉核对。F0固定每段domain/process
envelope、stop reserve、fatal delivery overshoot、RLIMIT hard-kill overshoot、exec-guard delivery
overshoot、initial/cleanup两个CPU+wall exec gap、`CLEANUP_PREPARSE_CPU_MAX_NS=CP_MAX_NS`及
`TC_MAX_NS/TW_MAX_NS`。initial固定soft/hard 8/9s并证明`9s+RLIMIT_CPU_KILL_OVERSHOOT_NS≤10s`；
cleanup满足`0<EXEC_GUARD_DELIVERY_OVERSHOOT_NS<CP_MAX_NS<cleanup_exec_gap_cpu_ns`，POSIX fatal
另满足`0<FATAL_DELIVERY_OVERSHOOT_NS<CP_MAX_NS`。每段进入与verified membership边界以`Pnow`对
segment envelope、`limit-accum-stop`及success的`limit-accum-remaining-tail`候选取最小，迁移同时
取两域，再扣overshoot作为absolute fatal expiry并readback；无正余量或正常路径不能严格早于expiry
即停止。initial从W SIGCONT到正常门的wall gap只作admission/success bound；zero-CPU stall由W的
BOOTTIME deadline收口。initial loader CPU则由出生即生效的RLIMIT_CPU hard 9s封口，不能以首码
事后采样代替。

cleanup exec前，可信账本先证明carrier累计+cleanup gap+stop≤10s、process handoff+cleanup gap+
stop≤20s，success路径还保留其余固定段和TC。L形成H前缀并取handoff process/三钟样本，确认旧
`ITIMER_PROF`为零、SIGPROF无pending，再把SIGPROF置为unblocked/`SIG_DFL`。F0固定ITIMER_PROF的
有效resolution、timeval微秒表示、向下量化、最小非零值和readback误差；L从cleanup gap、carrier/
process physical候选及success候选取最早值，扣完整`EXEC_GUARD_DELIVERY_OVERSHOOT_NS`，只在
H encode/hash/BEGIN/exec/P0/preparse/full-rearm的正常最坏CPU严格早于expiry时唯一arm/readback。
同一gate按当前absolute process CPU保守向下选择整数`CLEANUP_RLIMIT_HARD_S`，使
`HARD_S*1s+RLIMIT_CPU_KILL_OVERSHOOT_NS`不晚于最早physical候选，soft为`min(19,HARD_S)`；当前
CPU和完整guard transition必须严格早于两个cutoff。无可用整数或任一set/readback失败则不得exec。
pre-exec requested/actual、临时pair、候选和当时`W remaining`写入H；BEGIN完整发送后立即唯一exec。ITIMER_PROF和
RLIMIT_CPU跨exec保留，两个wall gap数值只作normal/admission界，physical wall仍由W承担。

continuation首个user-code严格按P0→`getitimer(ITIMER_PROF)`核armed且remaining非零、SIGPROF
default/unblocked→held procfs `Threads=1`→临时RLIMIT/PDEATH/W parent readback执行，任何失败不建
timer。它只用sealed常量把preparse fatal expiry固定为
`min(P0+CP_MAX_NS,20s-STOP_CPU_MAX_NS[PROCESS])-FATAL_DELIVERY_OVERSHOOT_NS`并建立/readback
cleanup-generation SIGALRM fatal guard，之后
才验H并取P1；handoff→P1只追加一次到carrier。它以H actual及P0/P1 delta复核ITIMER candidate，并
按完整ledger首次full rearm。只有该guard已生效且严格早于ITIMER expiry，才凭CAP_SYS_RESOURCE恢复
并readback RLIMIT_CPU `(19,20)s`，随后disarm/readback ITIMER_PROF为零并核SIGPROF无pending。
任一步失败保留更早guard并锁UNKNOWN。然后重建三个wall timer并取得P2；handoff→P2 CPU和双钟
elapsed分别落在cleanup gap界内才结束正常gap，后续raw actual只进`CLEANUP_FINAL`/capture。每个
pre-action/final-success段前后还须累计<19s且无
observed/pending `SIGXCPU`，19→20s只用于stop。G固定CPU/AS/DATA/FSIZE/NOFILE/CORE/STACK及零limits；
NPROC按ordinary UID current tasks+3固定，LOCKS/RSS采用未使用的plan pair；其余继承项必须匹配plan，
未知limit即BLOCKED。F0/F2静态资格或initial首mutation前失败可BLOCKED/clean reject；accepted或已
mutation后的运行故障、cleanup generation故障只能锁定UNKNOWN并有限收尾。

G以普通身份独立打开R/O的`/proc/<pid>/ns/{pid,mnt}`。Linux权限检查要求目标可被ptrace read；
在零CAP_SYS_PTRACE下把R/O设为non-dumpable会使设计自相矛盾。因此活体观察期间明确保持
dumpable=1，并由endpoint integrity premise和准确allowlist解释同UID信任边界。

`RLIMIT_CORE=0`不能阻止pipe形式`core_pattern`启动root helper。request前须从授权固定来源证明当前
值不是pipe，live admission再按固定接口复核；不支持时`NOT_ISSUED`或按实际已发状态BLOCKED，不改
sysctl也不把helper费用漏出范围。

## FD与协议闭合

旧严格relationship语义保留，但消息顺序重排为15帧：R SOURCE在O SETUP前被G接收/关闭，O
SOURCE在START_CHALLENGE前被接收/关闭，之后cross FD逐次收取。这样不增加ACK帧，SOURCE方向
准确为R/O→G，queued SCM reference上界为2。

guest outer fd0/fd1/fd2、全部internal protocol pipe/socket及owner侧local client三条pipe均固定真实
类型并设置/readback `O_NONBLOCK`。guest actor以单线程`ppoll`同时观察I/O、signalfd/stop和pidfd；
L另有共用blocked `DEADLINE_SIGNAL`的BOOTTIME/MONOTONIC/REALTIME absolute POSIX timer，双钟
expiry取原absolute界与保守映射UTC cutoff的较早者，REALTIME取UTC not-after。owner以单线程状态机
在启动client前按固定顺序创建、absolute arm并readback三个nonblocking timerfd，任一失败不启动；
运行中同时poll stdin可写、stdout/stderr可读、client pidfd/wait及三个timerfd，持续
并行drain双流，每流独立offset/counter/digest；REALTIME timerfd用`TFD_TIMER_CANCEL_ON_SET`。
partial read及允许chunk/remainder的大frame只推进同一logical frame remainder，large result/
`CLEANUP_FINAL`按固定≤4KiB chunk；action/marker/ACK/BEGIN小帧不超过资格化atomic-write bound，
写前零字节EAGAIN可等待，raw write partial即UNKNOWN；最终receipt单次EAGAIN也失败。owner只在完整
frame append+fsync private capture后ACK。一流反压、
另一流有数据、stdin partial、EAGAIN/EINTR、suspend、clock step或client exit都不能刷新期限或造成
stdout→stderr顺序死锁。

G在IPC前关闭fd0，故常驻20、SOURCE临时2、峰值22；R/O只继承stdout/stderr，常驻12、单一临时FD
峰值13。installed table slots合计≤48，queue引用≤2，总引用≤50；每进程RLIMIT_NOFILE=24。L基础13含stage parent dirfd，
持S后steady 18、当前case 20、S clone/临时或N09峰值22，含queue总引用≤24；S exec固定8，
case clone峰18、steady14、临时16。N09的R/O两pidfd同一帧交付且在resume确认后双方关闭。第15帧后
G用control half-close作为FINISH，不能隐式增加第16/17帧。

L的stage固定result file为752KiB：8KiB header、十二个48KiB case区、38个4KiB excursion区及16KiB
terminal/global区；准确offset是0、8192、598016、753664和EOF 770048。每case区只容纳stdout32KiB、
stderr8KiB及固定metadata8KiB，溢出不能截断成成功。加bundle≤1MiB、action journal64KiB和十二个
intent各16KiB后，stage最大逻辑2,080,768 bytes（2032KiB），22 regular/连目录23 inode。所有页在
首次进入B前从carrier逐页实写EMPTY；物理≤3MiB/48 inode仍须另证tmpfs folio/THP/metadata。

S wait/三条EOF及supervisor reclaim/final/remove完成后，L恰剩12项。action excursion不增加常驻FD；
`cgroup.procs`、membership和journal临时open严格串行、同时≤2并在门结束前关闭。L在guardian内零
outer write地完成最后收口；若仍在guardian，最多一次迁入原carrier，若早先失败已把L留在carrier，
只重验且final migration write count=0。第38 slot先冻结`FINAL_CARRIER_READY`、action摘要及result
slot bitmap/counters，不含result全文件摘要、H或导出后ACK。随后冻结result，算全文件digest并从
carrier导出固定双流frame；owner durable capture后回唯一ACK。result/H均不自引用。

L关闭result临时FD后把对象规范化成cleanup 0–11：carrier stdio、signalfd、procfs root、cgroup2
root、原carrier leaf、anchor、B、guardian、stage和`/run` parent；0–11外close，只有这组清CLOEXEC。
canonical H只内联固定status/bitmap/摘要向量，绑定37个excursion、result digest、final capture ACK、
stage摘要、bridge setup/arm/tail API及carrier-memfd flags/size/digest预期；另绑定process/guardian/
carrier CPU ledger、handoff process及相邻三钟样本/顺序、rounding/迁移双计、segment/stop/overshoot
catalog、两个exec gap的CPU hard与wall admission界、W absolute identity/PID/starttime/W0/expiry/
arm摘要/status mapping及handoff时`W remaining`、L的PDEATHSIG与W PPID、ITIMER_PROF resolution/量化/expiry/requested/actual、
临时RLIMIT_CPU pair/readback、sealed CP_MAX/preparse公式、Q0/有限SIGPENDING/SigQ转换、两generation
固定call-site/expiry、protocol nonblocking预期、cleanup-final schema/对象/ceiling和TC/TW。H不预填exec后
才出现的copy/seal/load、stage删除/final/reclaim值；F2用最大37项/22 stage entry证明H≤16KiB。

exec前可信账本证明carrier当前累计+cleanup gap+carrier stop≤10s、process handoff+cleanup gap+process
stop≤20s，success还为全部剩余段和TC保留guardian/carrier/process 9/9/18s，wall gap早于原期限。
随后排空全部blocked stop/deadline pending，复核W identity/PID/starttime/expiry余量与PDEATHSIG/PPID，
按上一节唯一arm/readback ITIMER_PROF并设置/readback临时RLIMIT_CPU，再把actual写入H并完成canonical
encode/SHA。预构造`CLEANUP_EXEC_BEGIN`≤atomic bound；零字节EAGAIN可在原deadline/W expiry内等待
同一未发送logical frame；完整raw write时H不变。partial/EPIPE/其它错误或deadline永久锁UNKNOWN；
若guard仍有余量，只可重算带该latch的H/SHA并继续唯一cleanup exec，不能重发BEGIN。完整输出后不再
改变FD并立即exec。

continuation按P0→ITIMER/SIGPROF→继承FD4 `Threads=1`→临时RLIMIT/PDEATH/W parent顺序核验，失败
不得建timer。它按上述sealed preparse公式设置SIGALRM default/unblocked、重建/arm/readback fatal timer，
排空继承event并核SigQ=Q0+1；guard生效后才验source/H，紧邻取P1，把P1-handoff+rounding只计carrier
一次，复核ITIMER actual/remaining并立即按完整ledger full rearm，P0→readback≤CP_MAX_NS。随后恢复
RLIMIT `(19,20)s`、disarm/readback ITIMER并核SIGPROF无pending；然后按BOOTTIME/MONOTONIC/REALTIME
重建至Q0+4，紧邻取P2/三钟，只追加P2-P1+rounding并再次full rearm。handoff→P2 CPU/wall分别不超
cleanup exec gap，再复核原期限/boot/W parent/root/RLIMIT/affinity/signal/FD/membership。
startup临时FD≤2、首个user-code复原恰12项，所以不改变L的22/24全程上界。任何cleanup generation
create/arm/readback、Q0/pending或H错误发生在已mutation之后，只能UNKNOWN并有限收尾。

## 资源与物理费用

case leaf设memory.max=96MiB，但验收读取空树后的memory.peak并要求≤128MiB；这只是leaf的
kernel-accounted charge。cgroup v2迁移不会搬迁旧memory charge，file-backed runtime/page cache
也可能被回收后在另一个域重新charge。设计因此使用clone3原子出生+一次exec，另列≤64MiB
imported/shared pool和≤3MiB stage风险；预热不冒充永久归属，也不把leaf peak写成全部physical RAM。
cleanup continuation在verified carrier把bridge复制并逐页触达到新的sealed executable memfd，故tail
mapping来自carrier首次分配的新inode；其payload逻辑/RAM/AS≤1MiB、含folio/THP/metadata/allocator的瞬时物理风险≤2MiB/1 shmem inode，copy/load CPU及shared charge全部计carrier。它不直接load可能仍带guardian/B charge的stage inode。
除非准确共享池明示覆盖，该memfd义务与carrier/shared风险相加。

W是原carrier中的独立单线程task，不计入B的`pids.max=5`；现场须证明既有parent、W、L可同时存在。
W入口先取绝对process CPU样本；随后设置的8/9s RLIMIT按完整process lifetime累计，故pre-arm CPU已
包含在W出生至退出的资格化physical风险≤10s中，success累计≤1s；
L的carrier CPU≤10s另按其连续process clock计，不得拿原carrier `cpu.stat`混账，二者新增CPU风险合计
≤20s。认证/提权与audit/journal另有合计≤10s的accepted-endpoint envelope，所以整项attributable CPU
ceiling≤30s；pre-arm wall及资源仍不是kernel hard guard，不能静态资格化就不发request。W的prefix
和guard后AS/DATA/STACK、loader/image/shared pages及kernel objects共同按独立≤64MiB
物理风险计。既有carrier/audit/journal持久分配/保留风险≤64MiB/1024 inode；只有准确page/extent归属
证明时才可与W去重，否则carrier/W聚合上界为≤128MiB/1024 inode再加固定kernel objects。W pre-clone installed FD为stdio+signalfd+timerfd共5；clone返回后加pidfd为6，
身份/proc临时FD严格串行使瞬时≤7。child停止时继承0–4，恢复后关3/4并核只剩stdio；W关闭stdio后
steady恰有signalfd/timerfd/pidfd三项。F0另列pidfd/timerfd/signalfd slab、pipe pages、W source/loader
前缀、认证/session/audit的bytes/inodes；W不新建文件或网络连接，outer read/write为零。

B保持空进程，先固定/readback cpuset与limits并唯一启用`cpu cpuset memory pids`给children，统一限制
guardian+S+active G/R/O：memory.max=320MiB、pids.max=5、单CPU，最终
cpu≤170s。guardian、S和case各有更窄leaf上界。guardian absolute CPU≤10s/成功≤9s；L在guardian
外的原carrier prefix、最多37个action往返和final tail用同一进程CPU基线连续计量，absolute≤10s/
成功≤9s且不因迁移或exec重置；verified membership边界更新账并按最早候选fatal rearm，最终gate以
`process+TC≤18s`、`carrier+TC≤9s`和guardian≤9s闭合不可回读tail；pipe/socket/runtime/ACK
分配进同一carrier/shared费用，不拿B counter覆盖。B与全部leaf固定memory.min/low=0、high=max、swap=0并要求可写
`memory.reclaim`。case/S退出且关联mapping/streams/proc/ns/pidfd/重复leaf FD关闭后，每轮先读
C=`memory.current`，非零才写十进制C并复读；EAGAIN后复读0仍成功，最多4轮后必须current=0，
再读完整final、remove、关闭最后held FD并等parent dying=0。case/S清完后L按上述0|1 final分支在
carrier完成export/ACK。唯一cleanup
exec释放guardian中的旧CPython mm/bridge；不得依赖css_offline或charge reparent。

L首次进入guardian后，所有正常、stop、异常、traceback、diagnostic和signal路径对fd1/fd2均为零
write调用/零字节。action record只在证明carrier membership后写stdout；其它case/error进入固定result
slot。final在carrier导出752KiB固定frame，stdout/stderr各以唯一≤256-byte `FINAL_CAPTURE` marker
结尾，owner append+fsync后回ACK；整个final carrier/freeze/export/ACK≤15s，marker后ACK≤5s。
任何guardian额外byte、membership缺口、slot overflow、large chunk未在deadline前按remainder补齐或
atomic marker/ACK partial/ACK错均永久UNKNOWN且不重发。
cleanup continuation在fd1/fd2两端仍打开时要求guardian `memory.current=0`；成功不依赖pipe读尽后的
缓存页释放或pipe对象销毁。

continuation在startup资格通过后预分配32KiB cleanup-final与≤512-byte receipt buffer。它在verified
carrier从FD10打开固定bridge并复核fstat/size/digest，以固定flags建立新的executable/sealable memfd；
artifact FD+memfd瞬时仅2项，按固定chunk复制、逐页触达、复读全字节/digest，施加并readback
`F_SEAL_WRITE|F_SEAL_GROW|F_SEAL_SHRINK|F_SEAL_SEAL`，再关原artifact。load阶段memfd+loader/procfd
临时对象峰值仍≤2；随后从memfd复核ELF/SOABI/loader/dependencies/setup/arm/tail exports，经资格化
procfd load并关memfd及loader临时FD；mapping留至`_exit`。
调用setup注册receipt buffer/layout/fd0–fd2及一字节stdin probe scratch并核摘要。任一kernel exec/seal policy、copy、digest、seal、
load或setup不符都锁UNKNOWN；实际记录进入cleanup-final。

carrier-owned mapping固定后才核对全部预分配stage文件；两个journal/intent固定slot按准确offset/length
pwrite，动态项核owner capture final digest，未发行项须匹配EMPTY digest，任一basename ENOENT都为
UNKNOWN。它删除stage并关闭stage/parent FD，随后依次把guardian、B reclaim到current=0、读完整
final、remove/close/dying，最后要求anchor恢复D0/dying=0。bridge copy/digest/page-touch/seal/load/setup
加完整stage验证/删除共同受110s reserve中的固定15s段约束，F0/F2以最大1MiB路线证明。exec/source/H/
FD/期限复核、reclaim或收尾任一步失败均保留UNKNOWN且不得写成功。

上述raw值不能由H预言。收尾完成后形成唯一canonical `CLEANUP_FINAL`：内含canonical H bytes/digest、
continuation P0/P1/P2及FD验证、carrier bridge copy/memfd size/digest/seals/load/setup实际记录、stage
verify/delete、guardian/B完整final/control raw bytes、reclaim/remove/close/dying、anchor复原及CPU/
timer账。frame含counter/previous digest，不自含自身digest/ACK/head；按≤4KiB chunks从carrier发送。
owner并行drain、append+fsync后回唯一≤256-byte ACK，exchange≤5s且不重发。

全部可失败验证和ACK后，fd1 nonblocking且cleanup ACK已读尽旧stdout。continuation以bridge arm入口
一次性注册counter/digest/ACK head、last process sample、CPU账、stop latch、原deadline及TC/TW等
immutable inputs，随后只调用一次不返回的`fixture_cleanup_tail`。native入口首动作按固定顺序取得
process/BOOTTIME/MONOTONIC/REALTIME sample，把last→sample+rounding计carrier并执行final gate：
`process+TC≤18s`、`carrier+TC≤9s`、guardian≤9s，双钟`now+TW`早于work/UTC且REALTIME无step，
stop latch和全部blocked stop/deadline pending为空，再以一字节scratch对nonblocking fd0 raw read且只接受`-1/EAGAIN`；EOF、额外byte或其它结果失败。通过后只按固定offset原位填充receipt并以无分配、
无loop路径封digest，恢复/unblock catchable stop/deadline signal；SIGPIPE保持ignore直到唯一raw atomic
write取得返回值，随后恢复SIGPIPE默认、close fd1/fd2并`_exit`。最终sample后禁止Python/allocation/
import/loop/cleanup/第二frame；partial/EAGAIN/EPIPE/write/close错在恢复SIGPIPE并尽力close后非零退出。
owner仅在完整cleanup-final/ACK与native receipt、sealed W映射加W remote status 0证明原L为
`CLD_EXITED/0`、local client wait 0、双EOF和capture final fsync/seal齐全时接受success；L关闭流后
双EOF可以先于W wait/reap/status，因此owner须并行等待且不能以EOF替代W状态。receipt、W remote status/exit
和双EOF须早于gate+TW及原成功期限，local wait
与capture final fsync/seal使用最后15s分段剩余并须早于work/UTC/outer原成功期限，不纳入≤1s TW。

storage按物理设备计算unique current allocation、unreleased future、new peak和metadata/allocator/
sync/audit margin。同一obligation已实现部分取max而不双加，不同obligation仍相加；partial/final
同inode取同时峰值。删除、rotation或净增长不会产生退款。

## 一次发行和准确结论

一次发行使用五个不混写的状态字段：

- `fixture_delivery_issued`在首次carrier request前为false，发出任何request即永久true；
- `fixture_batch_release_issued`在写出任何`BATCH_RELEASE`字节前由owner持久置true，短写、断线或
  receipt丢失不清零；
- `fixture_batch_release_accepted`只在L收齐并严格验证完整frame后于RAM置true，owner仅凭原
  `BATCH_ACCEPTED`或同一状态链后续证据登记；并以
  `batch_release_outcome=NOT_SENT|CLEAN_REJECTED|ACCEPTED|UNKNOWN`区分结果；
- `fixture_native_batch_issued`在首个case `clone3`前持久置true；每case另有先于相应动作提交的
  `clone_issued/exec_go_issued/g_go_issued`，任一已发位不重置；
- `fixture_qualification=NOT_RUN|BLOCKED_RETAINED|UNKNOWN_RETAINED|FAILED_RETAINED|FIXTURE_LIVE_REFERENCE_MATCHED`。

`batch_release_outcome`初始化为`NOT_SENT`。owner只有把原`BATCH_ACCEPTED`或证明同一RAM accepted状态的
后续链证据append+fsync进固定private capture，才持久登记`fixture_batch_release_accepted=true`和
`batch_release_outcome=ACCEPTED`，并且须在允许任何native-batch动作前完成。`NOT_SENT`只能单调进入
`CLEAN_REJECTED`、`ACCEPTED`或`UNKNOWN`之一；任何终态都不回退、不互换，也不由迟到ACK改写。已经
证明release accepted后发生的case或收尾失败只改变`fixture_qualification`，不把outcome改成UNKNOWN。

一次Owner B/C最多授权一个carrier request：owner原REALTIME/BOOTTIME/紧邻MONOTONIC outer
deadline均≤840s。启动local client前只能证明W static identity、pre-arm TCB prefix和资源预算，并固定
HELLO发送原点；W的准确PID/starttime/W0/expiry/arm-readback/status mapping由W封入L的固定argv，L
首码验证后通过HELLO带回。W在放行L前已经arm不可刷新的BOOTTIME kill/reap/exit链。L完成首个
process sample→W/PDEATH/profile/继承`W_BLOCKED_SET`→同一held procfs `Threads=1`→Q0/limit→fatal
arm/readback→紧邻复测的initial CPU guard后立即固定G0；随后把SIGXCPU加入blocked mask并让新
signalfd接收`W_BLOCKED_SET∪{SIGXCPU}`。从W SIGCONT到该正常门、两次pending-stop门及三个本地wall
timer的create/readback（其中BOOTTIME/MONOTONIC首次arm、REALTIME保持disarmed）的initial wall gap
只作admission/success界。只有W timer提供L出生后的远端wall backstop。

完整HELLO须在owner原点+10s内，且实测`W0→G0≤10s`；DECLARE/HELLO/完整release须在G0+48s内。
从release派生的containment≤760s，因此W0起正常最长路径≤818s；到W remote exit cap 830s保留至少
12s给资格化wake→kill→reap/exit/EOF margin。HELLO/RTT/三钟映射若不能证明实际W界早于owner最早
outer cutoff，则delivery保持consumed，但在任何fixture mutation及`BATCH_RELEASE`前clean reject；
prelaunch static门失败才是不启动client。HELLO时realtime offset整个区间在±2s，并从双方准确
`adjtimex`/clocksource固定相对频率误差上界；owner
三个outer deadline及guest UTC均剩余≥792s后，owner紧邻issued动作前取得第二组三钟/同步状态并
连同原点封入frame，先持久置`fixture_batch_release_issued=true`才尝试一次`BATCH_RELEASE`。L收齐并验证frame后，以HELLO guest
采样以来的实际双钟elapsed和相对频率界扩大offset区间；当前整个区间仍须在±2s，并以最坏端确认
UTC原始余量≥782s、owner当前剩余下界≥780s。owner原点→frame第二组及guest三钟还须证明无step，
双方不得unsynchronized，并另证随后760s最坏
相对漂移≤2s；否则在mutation前clean reject。通过后才在RAM置accepted、先回`BATCH_ACCEPTED`并从guest BOOTTIME/MONOTONIC派生
work `+750s`和containment `+760s`；ACK丢失不能重发。过去的HELLO RTT不冒充后续release单程
上界；20s outer margin覆盖漂移、远端收口到owner EOF和local hard cutoff。
`fixture_delivery_issued=true`而`fixture_batch_release_issued=false`时，只有从原连接取得L完整
`CLEAN_REJECTED` frame、sealed W映射加W remote status 0→L `CLD_EXITED/0`、local client wait 0、
stdout/stderr双EOF与准确账目形成闭环，才可把`batch_release_outcome`记为`CLEAN_REJECTED`并置
`BLOCKED_RETAINED`；W是唯一remote status来源，不能以L自报exit、L frame或单独EOF替代，否则为
UNKNOWN。
`fixture_batch_release_issued=true`后，accepted与clean rejection均不可证即
`batch_release_outcome=UNKNOWN`/`UNKNOWN_RETAINED`。若从原连接取得L完整`CLEAN_REJECTED` frame，
并同样取得sealed W映射加W remote status 0→L `CLD_EXITED/0`、local client wait 0、双EOF和准确账目
闭环，则可把`batch_release_outcome`记为`CLEAN_REJECTED`并置`BLOCKED_RETAINED`；两个issued位保持
consumed且绝不重发。
`BATCH_RELEASE`后的live admission/stage/S≤160s、最多12个顺序case≤480s、固定final-success
reserve=110s，合计≤750s；异常containment≤760s。110s分成S/supervisor≤15、final carrier/export/
ACK≤15、H/exec≤10、carrier bridge copy/digest/page-touch/seal/load/setup加完整stage验证/删除≤15、
guardian/B/anchor≤35；最后20s中cleanup-final/ACK≤5，native tail/
remote exit/双EOF/owner seal≤15。每case在任何intent/leaf/action前固定同一`CASE_T0`：首例四项、
后续三项excursion及intent/clone/drop/exec/bootstrap/N09/observe共享`CASE_T0→+20s`；+20→+25只
stop，+25→+30只exit/EOF/report，+30→+40只reclaim/final/remove。case及每个pre-action须保留
`CASE_T0+40s-current+110s`，并在动作/每个可返回final段边界更新CPU账、fatal rearm及pending门。
最终gate用+TC/+TW闭合receipt/exit；work后的containment只stop/receipt，不能补成功。
每case的clone、
`EXEC_GO`、`G_GO`以及首个case前的native-batch位，都必须先由唯一L写入stage hash-chain journal
下一个预分配EMPTY slot、
fdatasync，再完成迁carrier/membership、owner append+fsync/匹配ACK、迁guardian/membership及固定
excursion slot seal，之后才执行动作；每项≤2s、最多37项。成功最大为旧carrier的37次action迁出+1次final、新guardian的1次首次迁入+37次action迁回，
各38次、合计76次self-write；失败按实际≤76，若已留在carrier则final migration为0次而不是重试。ACK
丢失时动作不发生但owner已commit位保持consumed，任一动作只尝试一次；12个case属于同一
native batch，不是12次重试。任何失败停止后续项。

完整N01–N12、三层typed exit/EOF、guardian零outer byte、全部action往返、final carrier result
export/ACK、original stop、逐层memory.current=0/empty tree、final resources、完整唯一
`CLEANUP_FINAL`/ACK与native success receipt、sealed W映射加W remote status 0证明原L
`CLD_EXITED/0`、local wait 0、双EOF、physical bill和
capture final fsync/seal齐全，且TC/TW期限通过，才可写`FIXTURE_LIVE_REFERENCE_MATCHED`。这仍不改变`field_ready=false`、
`allow_run=false`、`consumer_namespace_admitted=false`、`normal_chain_executions=0`或任何
P4/20261002a状态；NS3、NS4、actual consumer和正常任务继续排除。

本页只完成文档设计。没有运行proc/nsfd/cgroup probe，没有连接guest，没有创建stage/cgroup，
没有修改系统配置，也没有生成source/test。
