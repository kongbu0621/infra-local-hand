# Q2 namespace fixture 完整交付：需求

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1`；拟关闭 **F0–F4 only**。
- Rule R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；直接来源 SHA-256
  `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
  readable direct source、Owner-only authority、mandate、无例外及变更规则继承根 `AGENTS.md`。
- 本文、[架构](ARCHITECTURE.md)和[实施计划](IMPLEMENTATION_PLAN.md)构成新的权威候选文档，
  [设计复核](../Q2_NAMESPACE_FIXTURE_DELIVERY_DESIGN_20261002.md)与它们同在候选 A。当前尚无
  本范围准确 A commit、Owner B、独立 CLOSED C、implementation D 或现场发行。

## 问题、替代关系与目标

旧候选 `LH-Q2-NAMESPACE-REFERENCE-v1` 的 proposed A
`dfdd653dd48388d8ab1a2554d16bf5b610edba10` 要求普通 supervisor、资源、暂停、停止/EOF
和原生审计环境已经存在，同时禁止补建。后续只读复核确认适用资料 `NOT_PREPARED`。旧候选
从未取得 Owner B 或 CLOSED C；其三文档、摘要和审计保持历史原字节，不追认为已关闭范围。

本候选在形成准确新 A 后将旧候选登记为 `SUPERSEDED_PROPOSAL_NOT_APPROVED`，把 standalone
collector、最小 runtime fixture、合成验证、一次隔离 guest 交付、最多十二个 native case、
独立 guardian、停止/EOF/账目和脱敏结论放进同一准确范围。这不是旧 CLOSED scope reopening。

目标只是在一个准确指定且已经结束的 isolated fixture session 内，验证 G/R/O 的活体 pid/mnt
namespace 关系和 procfs PID 视图。成功最多产生 `FIXTURE_LIVE_REFERENCE_MATCHED`。它不证明
原 host terminal、physical host、initial namespace、同 boot、未来进程或实际 consumer。

## 准确 fixture 与允许的 runtime 准备

本范围只选择已有 Q1 隔离 KVM guest，并条件复用其中历史 Q2 准备形成的准确普通账户/主组。
私有 plan 必须固定 guest、预期 boot、账户/组、既有 runtime、一次 management carrier、root-only
cgroup anchor、审计载体和累计容量来源；Public 只保留摘要和脱敏关系。

复用不外推历史成功。允许准确绑定并只读保留历史 `user@UID.service` manager 的 MainPID、
Invocation、cgroup 和固定子树；“没有其它同 UID 工作”只排除该 allowlist 之外的进程、session、
job 和可写端点。旧 manager、七根、ledger、安装、配置和失败实例均不启动、不停止、不重写、
不消费。任一当前关系不符即 `BLOCKED_RETAINED`，不换 guest、UID、runtime、anchor 或第二个 plan。
manager只读核对必须在F0固定唯一来源、准确API、字段和调用次数；现场不得枚举或改用其它
`systemctl`/D-Bus调用，也不得向manager发控制请求。

允许新增对象只有：

1. 一个已存在、绝对路径和字节摘要均固定的native remote watchdog **W**，以及它装载的有界RAM
   bootstrap/guardian **L**。L源码≤32KiB，经无padding base64url形成唯一参数；host以`shlex.join`
   生成唯一远端字符串
   `exec /usr/bin/sudo -n -- /usr/bin/env -i LANG=C LC_ALL=C ABS_WATCHDOG WATCHDOG_ARGS -- ABS_RUNTIME -I -B -c FIXED_LOADER TOKEN`，
   由预先固定的远端login-shell `-c`只解析一次。W必须是SSH顶层远端程序和L的准确parent，完整
   UTF-8 command≤48KiB且stdin保留给L协议；目标没有完全匹配的W即`NOT_ISSUED`，本范围不安装或
   现场生成W；
2. 一个 root-owned `/run` tmpfs stage：完整固定名称集只含≤8个封存bundle文件、一个预分配
   `action.journal`、一个预分配`result.journal`和十二个预分配case intent/context文件；
3. 在准确 root-only cgroup v2 anchor 下，一个 create-only 空 batch distributor **B**、一个
   guardian leaf、一个 supervisor leaf，以及每 case 一个永不复用的 fresh leaf；
4. 一个 root supervisor **S**；每 case 一个先在 fresh leaf 出生、降权并执行封存 collector 的
   bootstrap child，随后为普通身份 G，且只有 G 再 fork R/O；
5. 私有原始 capture/receipt 与 Public 脱敏记录。

不创建账户、user manager、slice、systemd unit/drop-in、mount、namespace、project/quota、包或
系统依赖；不运行 `systemd-run`；不修改既有 cgroup anchor 的 controller/limit、sysctl、LSM、
audit/journald 配置、内核、fstab、现役服务或旧对象。只允许创建、控制和删除本批次的新 cgroup
子树；唯一旧对象写例外是L向启动时held的原carrier leaf `cgroup.procs`写`0`做有界self-only
carrier excursion：最多37个动作往返和按实际0或1次最终进入，动作往返还只可向本批新guardian的
`cgroup.procs`写`0`把自身迁回。每次均须经held对象在写前、写后复核，不写数字PID、不迁移其它
task、不改任一leaf controls且不得重试同一次excursion。身份不明、原leaf不可回迁或清理不完整时
保留并按全额计费。

anchor admission必须通过held dirfd/openat完成，并证明准确mount为cgroup2且fs magic正确、
`cgroup.type=domain`、`cgroup.procs`为空、`cgroup.subtree_control`准确为
`cpu cpuset memory pids`、`cgroup.stat nr_dying_descendants=0`；记录准确live descendant基线D0，
有效`cgroup.max.depth`剩余至少2层，且计入D0后的有效descendant余量至少4项，足以同时容纳B及其
三个leaf，并且没有manager cleanup。原carrier
leaf另须为可接纳进程的domain、`subtree_control`为空，准确parent仍存活并留在该leaf直至L最终返回；
L每次carrier excursion前后须从原held对象重验mount/dev/inode、domain、空subtree control、`cgroup.freeze=0`、
`cgroup.events populated=1/frozen=0`、准确effective cpuset/mems、parent活性以及没有cleanup/改限
竞态；动作往返还须在迁回前后从held guardian对象重验其身份、controls和自身membership。不允许按
路径重开、现场换退域目标或在任何迁移中刷新原期限。旧carrier `cgroup.procs`最多37次action迁出加最多1次final迁入，共38次self-write；新guardian
`cgroup.procs`为1次首次迁入加最多37次action迁回，共38次self-write；全批合计最多76次。

## 候选事实前提

需要 Owner 在 B 明确接受的唯一新事实前提是 **fixture endpoint execution integrity**：准确绑定的
remote watchdog W、RAM bootstrap、bundle、runtime、guardian、supervisor、G/R/O 和收件代码在该 isolated session
按所审字节执行，没有 root、kernel、allowlisted manager 或同 UID 主动替换、注入或伪造端点。

该前提只解释无法从 same-object namespace FD 区分最初打开者、以及受信 root 端点按固定协议
操作的边界；它不能代替实际 clock、ABI、权限、cgroup、停止、原退出、EOF、容量或审计证据。
它不接受原终端 provenance。guest、anchor、carrier 和现场动作仍须由准确 B 直接授权。

## F0–F4

| 阶段 | 必须完成的工作 | 通过/停止边界 |
| --- | --- | --- |
| F0 | 只从保留原件离线固定唯一 target、carrier、root anchor、allowlist、费用前缀、预算来源和私有 plan schema | 不连接 guest；原件不足即不发行，不靠现场枚举补空白 |
| F1 | 实现 standalone G/R/O、RAM bootstrap/guardian、root supervisor、有限收件/账目和 synthetic tests | 仅独立 C 后开始；不修改产品 consumer、K reader、旧 supervisor 或冻结 runtime |
| F2 | 冻结准确 D、bundle/context/runtime 摘要；验证协议、启动、暂停、资源、停止、EOF 和计费实现 | parser/state/cost/source 硬门必须通过；目标 guest 特有事实留给 F3 条件 admission，不把 local skip 当 guest PASS |
| F3 | 发出一次 carrier 请求；经只读 late-start gate 后，最多一次 `BATCH_RELEASE`，并顺序执行最多十二个唯一 case | 首个 case 前写 `fixture_native_batch_issued=true`；每个 case 只发行一次；没有第二个 batch |
| F4 | 保留原进程 wait/stop、空树、三层 EOF、最终 counter/peak、费用和 outer seal | 缺身份、退出、EOF、最终计数或账目为 `UNKNOWN_RETAINED`；只发布 fixture 范围结论 |

## 固定要求

| 编号 | 要求 | 拒绝规则 |
| --- | --- | --- |
| FD01 | 唯一目标和一次发行 | plan 先绑定 guest/boot/普通身份/runtime/carrier/anchor/batch/case/预算；首次请求后断线、BLOCKED 或 UNKNOWN 均不产生第二次 delivery |
| FD02 | 旧事实完整保留 | 旧 proposal、Q1/Q2 证据、两次失败、ledger、roots、deadline、reservation、P4/20261002a 和正常任务计数不改、不清理、不退款、不续期 |
| FD03 | carrier、remote watchdog与late-start gate | F0须固定wrapper/profile SHA、host env/PATH/cwd及解析出的bash/ssh/key/known_hosts对象、已存在的准确host key、`shlex.join`结果、远端login shell/parser、sudo/env、W/runtime绝对对象和命令round-trip；launch env必须明确删除`SSH_AUTH_SOCK/SSH_AGENT_PID`，只准固定identity file认证，并在发request前从授权固定来源证明当前`core_pattern`非pipe。W必须是已存在的sealed native对象，F0固定其absolute path及mount/dev/inode/size/uid/mode/不可写祖先、SHA-256、version、ELF class/machine/PT_INTERP/loader/`DT_NEEDED`完整摘要、source→binary relation、argv/env/cwd/umask、caps/securebits/seccomp/LSM/affinity/scheduler、无setid/file-cap、退出映射和准确资源表；缺失在request前可读固定来源中已证实时为`NOT_ISSUED`，若只能在已发SSH后发现则保持delivery consumed并按证据为BLOCKED/UNKNOWN，均不得上传、编译或替换。W的ELF入口至guard-arm属于明确列账的pre-carrier TCB prefix；本范围不把该prefix称为已获远端kernel hard wall，且在W唯一clone前没有L、B或fixture mutation。F0必须从封存source/loader/launcher关系和独立fault/trace固定有限数值：`W_PREFIX_CPU_MAX_NS≤1s`、`W_PREFIX_WALL_MAX_NS≤2s`、单task、userspace AS/RSS及保守物理风险≤64MiB、入口installed FD≤8、outer read/write=0，以及pipe/kernel-object/audit bytes/inodes；它们全部进入首次发行前carrier预算，不能资格化即不发，wall项只是在fixture endpoint execution integrity前提下的admission envelope而非kernel强制。W入口先取得绝对process CPU累计样本；再按`parent_before=getppid()`→`PR_SET_PDEATHSIG(SIGKILL)`并readback→`parent_after=getppid()`顺序证明两次都等于同一非1且按manifest固定proc-identity规则资格化的parent，避免parent-death race。W先把完整signal mask归一为空，并把全部catchable disposition归一为manifest固定初态，其中SIGXCPU=`SIG_IGN`、SIGCHLD/SIGUSR1/HUP/TERM/INT/QUIT/`DEADLINE_SIGNAL`=`SIG_DFL`且SIGCHLD flags清除`SA_NOCLDWAIT/SA_NOCLDSTOP`；逐项readback后再block并readback准确`W_BLOCKED_SET={SIGCHLD,SIGUSR1,SIGHUP,SIGTERM,SIGINT,SIGQUIT,DEADLINE_SIGNAL}`，signalfd只接收该set。它先验证fd0/1/2真实类型、access/status flags与协议预期，`close_range(3,UINT_MAX,0)`后核自己恰有stdio，再设置/readback CPU `(8,9)s`、AS/DATA `(64,64)MiB`、NOFILE `(8,8)`、CORE `(0,0)`、FSIZE `(0,0)`、STACK `(8,8)MiB`及固定零limits；随后固定创建CLOEXEC signalfd=3，取得W0 BOOTTIME并固定创建/absolute arm/readback CLOEXEC timerfd=4，clone返回pidfd=5，身份/proc临时FD严格串行使用6后立即关闭。固定`W_REMOTE_EXIT_DEADLINE=W0+830s`；manifest分别给出有限`W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS`、`W_KILL_TO_REAP_MARGIN_NS`和`W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`且三者之和≤12s，定义`W_KILL_DEADLINE=W_REMOTE_EXIT_DEADLINE-W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS-W_KILL_TO_REAP_MARGIN_NS-W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`、`W_REAP_DEADLINE=W_REMOTE_EXIT_DEADLINE-W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`，timerfd不可刷新地arm到`W_KILL_DEADLINE`。F0/F2须资格化timer readable至W被调度并发出pidfd SIGKILL的最坏overshoot、kill至typed wait/reap的margin、reap至W `_exit`/SSH status与EOF的margin；timerfd本身不杀进程。除已明确保留UNKNOWN的不可中断内核等待、W自身被SIGKILL或endpoint premise失效外，deadline路径须证明kill不晚于`W_KILL_DEADLINE+W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS`、reap不晚于`W_REAP_DEADLINE`、remote status/EOF不晚于`W_REMOTE_EXIT_DEADLINE`。完成上述W本地self-gates后，W才用88-byte全零初始化`struct clone_args`创建唯一L child：flags仅`CLONE_PIDFD`、`exit_signal=SIGCHLD`、`pidfd`为有效对齐输出地址，`child_tid/parent_tid/stack/stack_size/tls/set_tid/set_tid_size/cgroup`均为0；没有fork或数字PID fallback。L从出生即继承SIGXCPU ignore、累计CPU `(8,9)s`和W的最小native-stub profile；完整L非CPU profile只在child stopped/live-pidfd window由W设置并在runtime前生效。child首段native严格执行`parent_before=getppid()`→设/readback`PDEATHSIG(SIGKILL)`→`parent_after=getppid()`并要求两次等于W→自停`SIGSTOP`。W以`ppoll`同时观察signalfd、timerfd、pidfd；SIGCHLD ready后用`waitid(P_PIDFD,pidfd,...,WSTOPPED\|WNOHANG)`消费且严格核唯一`CLD_STOPPED/SIGSTOP`、未exit和PPID/starttime，timer同时ready时deadline优先；SIGCONT以后所有终态只用`waitid(P_PIDFD,pidfd,...,WEXITED\|WNOHANG)`，不让旧stop/continued event混入。只有在同次clone返回numeric PID、live pidfd和已消费的stopped event共同成立时，W才用固定调用表的`prlimit64(pid,...)`复核继承CPU `(8,9)s`，并为stopped child设置/readback AS/DATA `(64,192)MiB`、NOFILE `(32,64)`、CORE `(0,0)`、FSIZE `(4,4)MiB`、STACK `(8,8)MiB`、NPROC及其余准确pair；CPU hard从出生已生效，其它profile在runtime前生效；这不是数字PID迁移fallback。clone时child准确继承fd0–4（stdio、W signalfd、W timerfd）；W关闭自己的fd0–2且从不读写它们，只留signalfd/timerfd/pidfd，随后只发一次pidfd SIGCONT。child恢复后先关闭继承fd3/4，再建立并readback manifest固定L入口signal状态（mask恰为`W_BLOCKED_SET`、SIGXCPU=`SIG_IGN`、其余catchable=`SIG_DFL`），并在exec前核准确0–2，才exec runtime。W保持单线程，以固定`ppoll`同时观察三者；child放行前的任何stop source、deadline或内部完整性错误立即只向准确pidfd发SIGKILL；放行后signalfd收到SIGUSR1/HUP/TERM/INT/QUIT/`DEADLINE_SIGNAL`时至多一次向准确pidfd转发SIGUSR1，固定grace到界仍未exit才发SIGKILL；deadline或内部错误不走grace。发kill后只按上述终态selector做nonblocking waitid/ppoll直至`W_REAP_DEADLINE`；到界仍未reap则W非零退出并把child/B状态保留UNKNOWN，deadline与child exit同时ready时deadline优先。W只有准确child为`CLD_EXITED/0`、从未触发deadline/stop/error、最终绝对process CPU累计≤1s且早于W期限才`_exit(0)`；其它状态按manifest固定非零粗粒度映射，不冒充完整raw wait status。owner所见remote status是W状态，sealed W语义加W status 0才证明原L status 0；L关闭流后可先出现双EOF，owner还必须取得随后W status。W被SIGKILL、W/L处于不可中断内核等待或上述margin证据失效时准确保留UNKNOWN，不声称L/B树已收口。还须证明no PTY、stdin二进制透明、stdout/stderr分离，且sshd/account/authorized_keys/ssh rc/shell startup/ForceCommand/BASH_ENV/ENV/sudo use_pty或I/O plugin不会消费、注入、重定向、合并或替换协议stdio/argv/env；预算内认证、W、audit/journal和session metadata允许但须单列。任一协议影响未知或新host-key adoption即`NOT_ISSUED`。owner在启动local client前只证明W static identity、pre-carrier prefix、transport和资源预算并一次固定HELLO发送原点；actual W PID/starttime/W0/arm record只能在已clone L后由HELLO带回，且完整HELLO须自owner固定发送原点起≤10s；若postlaunch HELLO/RTT/三钟/actual-W/limit/slack门失败则不得发送`BATCH_RELEASE`，delivery保持consumed并按完整clean rejection/status/EOF证据为BLOCKED，否则为UNKNOWN。W把自身identity、W0/expiry/arm-readback摘要和准确PID/starttime封入child固定argv，L首码验证W parent、继承profile和该snapshot后，完成首个process sample→同一held procfs `Threads=1`→Q0/limit→fatal timer arm/readback→紧邻复测的initial CPU guard并立即取得不可刷新的G0原双钟；`initial_exec_gap_wall_ns`只作正常路径/admission界，L自出生后的远端wall强制由W timer承担。HELLO/release及全部后续期限都取W界与既有界的较早者；必须实证`W0→G0≤10s`、`G0→BATCH_RELEASE≤48s`、release→containment≤760s，合计≤818s，并以剩余至少12s闭合上述wake/kill/reap/status/EOF margin。整个DECLARE/HELLO/等待完整`BATCH_RELEASE`须≤G0+48s。RAM bootstrap只可先做自身RLIMIT/prctl/signal自限，读取一个≤16KiB封闭`DECLARE`并输出有界HELLO；除W唯一clone L外，任何外部/持久对象mutation、额外fork/clone或cgroup迁移前，必须核对预置UTC not-after、预期boot、同连接frame、offset区间和原外层余量；owner在同一issued动作后紧随release只发送一次已承诺bundle frames，L可在RAM验总≤1MiB/8 files但live admission前不落盘；无完整frame、EOF、过期或时钟不一致只读退出 |
| FD04 | 独立 direct cgroup 路径 | 不向 manager 发 Start/Stop/Cancel/write。只可使用F0预先绑定的一个只读来源、准确API/字段/调用次数核对allowlist；缺该来源即BLOCKED。anchor须为合格cgroup2 domain、root-only、空`cgroup.procs`、非ordinary delegate、无其它writer，准确四个controller已启用，初始`nr_dying_descendants=0`；记录live descendant基线D0，有效depth余量≥2且计入D0后的descendant余量≥4。L不得写anchor。新B create-only后保持空procs并读回`cgroup.controllers`恰含四项，先写/readback plan固定的`cpuset.cpus`/`cpuset.mems`与B自身cpu/memory/pids limits并核effective值；再只向B的`cgroup.subtree_control`写一次固定token `+cpu +cpuset +memory +pids`并以严格set parser读回恰好四项。只有该门及B严格零initial schema通过后才可建guardian、supervisor和唯一active case三个domain leaf；每个leaf须在首task前证明`cgroup.subtree_control`空、固定cpuset/effective mems和全部limits准确。B删除后必须复原D0且dying=0。原carrier leaf须由held fd固定，并在最多37个动作往返及按实际0或1次final进入的每次迁入前后重验准确身份、domain/空subtree control、freeze/events、effective cpuset/mems、parent活性和无cleanup/改限竞态；动作往返还须重验held guardian和自身membership。不满足即BLOCKED，不写旧parent controls、不迁移旧任务、不使用数字PID或重试同一excursion |
| FD05 | 原子出生和唯一 exec | L在首个user-code、首次迁入guardian、每个action往返的迁出/迁回、需要执行final迁出时和clone S前，S在entry及每次clone前，都须由held procfs证明`Threads=1`；L/S只从该唯一CPython主线程、持GIL调用封存native bridge。bridge按88-byte `struct clone_args`调用`clone3`，flags严格为`CLONE_INTO_CGROUP\|CLONE_PIDFD`、`exit_signal=SIGCHLD`、`pidfd`为有效对齐输出地址、`cgroup`为held目标leaf FD，且`child_tid/parent_tid/stack/stack_size/tls/set_tid/set_tid_size=0`。bridge执行CPython fork hooks；child首个native syscall先设置SIGKILL PDEATHSIG并核PPID，再执行child hook，随后在native内完成设置/等待/降权/净化/`execve`或`_exit`，绝不返回Python。S和case child均无数字PID迁移fallback；每case的clone、`EXEC_GO`、`G_GO`各只有一次且发送/调用前持久置各自issued位；G entry后只有两次fork R/O |
| FD06 | 准确普通身份与exec净化 | bootstrap在root时清ambient/keepcaps和bounding，再以准确supplementary vector执行`setgroups`、以主组执行`setresgid`、以普通账户执行`setresuid`并核对fsuid/fsgid，清residual caps、设NNP，重设PDEATHSIG、核对PPID并设dumpable=1；`execve`前固定`cwd=/`、`umask=077`、全signal mask/disposition、完整RLIMIT profile、personality、scheduler/nice/单CPU affinity及仅`LANG=C`/`LC_ALL=C`的envp，无`LD_*`/`PYTHON*`。L从W继承SIGXCPU ignore及CPU `(8,9)s`；首码须核准确parent/PDEATHSIG/limit/disposition，fatal timer active/readback并紧邻CPU样本通过后，先block SIGXCPU、恢复`SIG_DFL`并创建/readback接收`W_BLOCKED_SET+SIGXCPU`的signalfd；耗尽它并核pending，无任何stop/XCPU时才可凭F0已资格的root CAP_SYS_RESOURCE把CPU提高并readback为供S继承的`(20,100)s`，raise后立即再耗尽并核pending。创建S时child在native gate保持未放行；parent clone返回后必须在等待READY或放行S前立即把自身CPU/AS/DATA/NOFILE降为`(19,20)s`/`(64,64)MiB`/`(64,64)MiB`/`(32,32)`并readback，失败即kill准确S、stop。S只把soft提高到已继承hard，不依赖CAP_SYS_RESOURCE，并独立readback后回`BOOTSTRAP_READY`。NPROC/LOCKS/RSS/SIGPENDING按F0准确pair验证，其余limit按本文固定，未知limit即BLOCKED。只有S的固定0–7表和L cleanup continuation的固定0–11表可在各自唯一exec前清除CLOEXEC；后者只含stdio、signalfd、held procfs/cgroup mount/original carrier/anchor/B/guardian/stage/`/run` parent，先归一化编号并`close_range(12,UINT_MAX,0)`，再逐项核对FD身份/flags。其它control/cgroup writable FD始终CLOEXEC；G entry只见stdio，G/R/O无后续凭据变化 |
| FD07 | dumpability 与 core | G/R/O 活体读取期间 dumpable=1；`RLIMIT_CORE=0`且 live admission 必须证明既有 `core_pattern` 不是 pipe、不会启动 leaf 外 helper；否则 BLOCKED，不改 sysctl |
| FD08 | 封闭 FD 起点 | G entry只继承stdin/stdout/stderr；`RLIMIT_NOFILE=24`且在context/proc前成功`close_range(3,UINT_MAX,0)`；读完唯一context frame后保持fd0到唯一`G_GO`，随后要求S write-close、读取真实EOF并关闭fd0，再创建IPC；CLOEXEC或`/proc/self/fd`扫描不能替代 |
| FD09 | 固定 namespace 关系 | 只读 G/R/O own status、pid/mnt nsfd及G的两个原direct-child对象；held procfs、NSFS/type、pidfd活性、SCM credentials/rights、nonce和两轮对照全部成立 |
| FD10 | 原三钟与guest双钟 | owner在request前一次取得REALTIME/BOOTTIME/紧邻MONOTONIC并固定三个outer deadline；request、`BATCH_RELEASE`、batch和每case均引用这些未刷新的值。HELLO以RTT区间证明owner/guest offset全落在±2s，owner/L分别核对REALTIME相对BOOTTIME/MONOTONIC无step。F0须从双方准确`adjtimex`/clocksource固定相对频率误差上界；`BATCH_RELEASE`还绑定owner紧邻写出前取得的第二组三钟和同步状态，L用原点→该组的delta复核owner无step。release到达时按HELLO guest采样至当前的实际双钟elapsed扩大offset区间，扩大后的整个当前区间仍须落在±2s，再以其最坏端证明owner剩余下界≥780s（guest原始UTC余量至少782s）。先前RTT不作为未来传输上界；缺第二组、频率上界、unsynchronized/clock step或扩大后越界即在mutation前clean reject。另须证明随后760s最坏相对漂移≤2s。L从当前guest双钟派生work `+750s`与containment `+760s`，UTC只可缩短；成功须早于work，stop/receipt须早于containment。固定`FINAL_SUCCESS_RESERVE=110s`完整位于work内。每个case在任何intent、leaf或pre-action之前固定同一双钟原点`CASE_T0`并派生不可刷新的`CASE_T0+20/25/30/40s`边界；每次开始case及其每个pre-action门均须证明`remaining_work ≥ CASE_T0+40s-current + 110s`，否则不开始/不放行动作。首case的native-batch/clone/EXEC_GO/G_GO四项和后续case三项都属于本case `CASE_T0→CASE_T0+20s`共享窗口。work到期后的10s containment只可stop/receipt，不能补做或恢复成功。G严格解码context后、任何身份/parent/proc观察前先核对原期限 |
| FD11 | 独立 guardian、watchdog 与停止 | L在supervisor/case leaf外，`EXEC_GO`前持原pidfd和held leaf身份并回`ARMED`；W从放行L前到wait/reap始终持准确pidfd和不可刷新BOOTTIME deadline，deadline只对该pidfd发SIGKILL。L从child首段到最终退出全程保持并在cleanup exec后readback W-bound `PDEATHSIG(SIGKILL)`与准确PPID/starttime；它从child entry起继承并readback `W_BLOCKED_SET`，使W在loader/首码窗口转发的SIGUSR1只形成pending；完成initial CPU guard并立即固定G0后，再block SIGXCPU、恢复其`SIG_DFL`并创建/readback接收`W_BLOCKED_SET+SIGXCPU`的signalfd，任何已pending stop只能进入同一stop状态机；只有无stop/XCPU时才raise/readback CPU `(20,100)s`并立即复查，随后才继续success路径；SIGALRM保持unblocked/`SIG_DFL`且只供fatal process-clock timer，SIGPROF通常为unblocked/`SIG_DFL`且只在cleanup跨exec guard短时启用。SIGUSR1只作为W用held pidfd转发的graceful-stop signal；W异常死亡由PDEATHSIG SIGKILL fail closed，HUP/TERM/INT/QUIT/XCPU、carrier EOF/EPIPE和原deadline走同一stop状态机，SIGPIPE固定ignore并以EPIPE处理。outer owner在最早原三钟deadline前10s关闭carrier stdin写端并保留两条读端；到原deadlinehard-kill本地client process group，但远端wall containment另由W证明，不能用local kill替代。远端L以本地work/containment deadline负责有证据的正常停止；W deadline是最后物理kill backstop。10s容纳最多5s TERM、cgroup.kill、wait/empty/EOF/receipt；不可中断kernel wait或缺闭环一律UNKNOWN；S/G/R/O的SIGKILL PDEATHSIG只是补充。最终success gate须证明W未触发且仍有固定退出余量，耗尽signalfd并确认stop latch及`SIGUSR1/HUP/TERM/INT/QUIT/XCPU/DEADLINE_SIGNAL`的pending集合均为空，还须核`ITIMER_PROF`已disarm、SIGPROF无pending；gate后固定tail把catchable stop/deadline signal恢复`SIG_DFL`并unblock，任何新到signal因此产生非零或signal wait，不能被owner接受为success |
| FD12 | 资源配置加最终实测 | B在创建任何child leaf前、每个leaf在首个task前，分别须有空procs、populated/frozen=0、descendants/dying=0，且固定schema的cpu累积项、memory.current/peak/events(.local)、pids.current/peak/events全部严格为0；不采用delta或白名单非零。每个case、supervisor、guardian及B均须在empty后、rmdir前读取同一完整final集合：空procs、events populated/frozen、stat descendants/dying、完整cpu.stat、memory.current/peak/events(.local)、pids.current/peak/events及全部controls；final须`memory.current=0`、`pids.current=0`、descendants/dying=0，缺项UNKNOWN。每层remove后关闭最后held FD，并在进入下一步前证明其parent `nr_dying_descendants=0`；B删除后anchor还须恢复准确live descendant基线D0。迁移不转移旧memory charge，leaf peak不得冒称全部物理RAM |
| FD13 | 有界暂停 | N09只暂停已绑定G/R/O调度最多2s；guardian仍运行并持原期限。它不证明VM/system suspend、host pause或两种clock的suspend差异 |
| FD14 | 输出与FD回收 | G写前计数；L/S/G三层原pipe分开且raw外层封顶。L基础13项含held stage父目录，持S后steady 18、当前case 20，S clone瞬时或串行临时/N09 pidfd时installed峰值≤22；S exec固定8，case clone瞬时≤18、steady≤14、串行临时≤16。N09的R/O两pidfd单帧queued≤2，L/S在resume确认后立即关闭。G在IPC前已关闭fd0，故G/R/O峰值分别22/13/13、installed合计≤48；固定15帧协议使queued SCM引用≤2、三进程含queue≤50。L任一点installed+queued引用≤24；carrier excursion不增加常驻FD，`cgroup.procs`、proc membership和journal的临时`openat`严格串行、同时≤2并计入L既有峰值。所有case结束及首错/异常分支关闭gate/streams/pidfd/leaf/临时FD并等dying=0。完成S wait/EOF并关闭其5项，再完成supervisor reclaim/final/remove/last-FD close后，L恰剩12项并原位归一化为cleanup 0–11；continuation启动瞬时串行临时FD≤2、首个user-code时必须复原恰12项，所以仍受L installed≤22/含queue≤24原界约束。continuation在删除stage前按FD17把同一sealed bridge字节复制到carrier-owned sealed executable memfd，从该新inode加载mapping，关闭临时FD但保留mapping至`_exit`；它启动时即预分配固定32KiB `CLEANUP_FINAL` buffer且不增加常驻FD。最终cleanup、该frame durable ACK与全部可失败验证结束后，`SUCCESS_RECEIPT`固定模板已在另一个预分配≤512-byte buffer内成形；在final gate前把buffer、固定offset/length、fd0–fd2、一字节stdin probe scratch和全部immutable gate输入预注册给bridge的non-returning native tail入口。该入口取得最终CPU/三钟样本、完成最后pending/额度门、固定宽度原位填充和封存digest，再恢复signal、执行唯一write/close/`_exit`；其post-gate固定路径不打开FD、不分配内存、不导入模块、不进入Python、不循环或执行cleanup |
| FD15 | 完整费用 | pre-carrier prefix、最多38次carrier进入、carrier、cgroupfs、stage、guardian/S、runtime/shared页、audit/journal、capture/receipt、失败与封存都列账；stage收尾只经held stage dirfd按完整stage manifest的bundle、`action.journal`、`result.journal`和十二个intent basename逐项复核/unlink，任何ENOENT均为UNKNOWN；动态文件须以owner capture中的最终digest/counter复核。关闭stage FD后经held `/run` parent删目录，不枚举或删除额外名，unexpected entry/ENOTEMPTY保留UNKNOWN；净增长、删除或“零业务文件”不能单独证明费用 |
| FD16 | 结果不外推 | fixture通过不接受原terminal provenance、actual consumer、H07、FS、field/P4或normal chain；报告关闭后仅是本次已结束exchange的历史事实 |
| FD17 | native artifact closure | bundle须含一个预编译bridge及C source→binary manifest，固定compiler/flags、CPython SOABI、ELF/loader/`DT_NEEDED`和完整导出符号；除clone/fork入口外，同一artifact必须导出setup、arm及non-returning `fixture_cleanup_tail`，后者的固定receipt布局、无分配digest实现、signal/write/close/`_exit`路径和错误exit表均入manifest。两个clean build byte-identical。L与S各自从held stage fd验摘要后经已资格`/proc/self/fd/N`以持GIL方式加载并关闭临时FD；cleanup exec销毁旧mapping。continuation不得直接加载stage inode：它在已验证carrier中经FD10 `openat`固定bridge，复核fstat/digest后以manifest固定`memfd_create` executable/sealing flags新建carrier-owned inode，按固定上界复制并逐页触达，复读全字节/digest，核size，再施加并readback `F_SEAL_WRITE\|F_SEAL_GROW\|F_SEAL_SHRINK\|F_SEAL_SEAL`；copy阶段artifact FD与memfd恰为两个临时FD且不得另开；复制后先关原artifact，load阶段由source/F2证明memfd加loader/procfd临时对象的installed峰值仍≤2。再对memfd复核ELF/SOABI/loader/`DT_NEEDED`/exports并经已资格procfd路径加载，关闭memfd及全部loader临时FD，mapping保留至`_exit`。F0/F2/F3须资格化准确kernel flags、seal与exec policy；bridge payload的额外瞬时RAM/AS≤1MiB；含folio/THP/metadata/allocator的物理风险≤2MiB且有1个瞬时shmem inode，全部计carrier/shared，H绑定预期flags/size/digest/API，`CLEANUP_FINAL`记录实际copy/seal/load。guest不编译，mapping不假定跨exec继承；sealed import closure须证明无after-fork Python callback，tail source/source-test须证明进入最终native sample后无Python、allocation、import、可变路径或loop |
| FD18 | 动作前commit链 | `fixture_native_batch_issued`以及每case的`clone_issued/exec_go_issued/g_go_issued`都须在动作前形成单调hash-chain记录。每项开始前先满足FD10的时间reserve及L累计CPU<19s、无observed/pending `SIGXCPU`门。唯一L写者先在guardian内按准确offset/length覆写`action.journal`下一个未用固定slot并`fdatasync`，再用held对象复核原carrier并只写`0`把自身迁入；只有从held procfs/cgroup视图证明自身已位于准确原carrier leaf后，才可经nonblocking状态机向outer stdout发送唯一≤1KiB logical frame，stderr保持零字节。owner须先append+fsync固定private capture并回含counter/digest/capture head的≤256-byte `ACTION_COMMITTED`。L严格验证后重验held guardian、只写`0`迁回并复核membership，把本次结果写入`result.journal`对应固定excursion slot并`fdatasync`；关闭临时FD后、向S放行动作前，必须再次读取process CPU、耗尽signalfd并核pending，仍须累计<19s且无SIGXCPU，否则该issued项保持consumed、动作不执行并锁定UNKNOWN。整个迁出、membership、write、owner fsync/ACK、迁回、membership和slot seal须≤2s且受原期限约束。最多37项/37个往返，不重试、不刷新期限；slot有固定阶段字段，迁出、outer write、ACK、迁回任一步失败也须在L当前所在域封口唯一错误枚举；能封口却未封口同样UNKNOWN且不执行动作。已发记录对应issued位保持consumed；ACK/write失败时L留在carrier进入terminal stop，迁出失败时留在guardian且只能有限stop，迁回失败时留在carrier。stage两个journal及intent/context全部固定动态页须在L进入B前逐页实写为确定EMPTY内容；case intent/context只可在对应预分配文件的固定slot内按准确offset/length pwrite、fdatasync，不延长/打洞/新建，由L复核完整slot/final digest并随首个对应commit写入owner capture；tmpfs fsync不能替代owner durable ACK |
| FD19 | memcg charge teardown | B及全部leaf固定`memory.min=0`、`memory.low=0`、`memory.high=max`并要求目标存在可写`memory.reclaim`。stage全部页（包括固定两个journal）须在L仍位于原carrier leaf时分配/逐页触达；bridge及准确runtime/import file-backed页也在该处预热并计入共享池，但不得假定它们不会被回收后在B内重新charge，最终只认逐层reclaim和`memory.current=0`。case/S退出后先关闭全部mapping关联进程、streams、proc/ns/pidfd、重复leaf和临时FD，只留L的最后held leaf；每轮先读准确C=`memory.current`，C=0即完成，否则把十进制C写入`memory.reclaim`，最多4轮。每轮写的errno/bytes均留证；EAGAIN后立即复读，若current=0仍成功，只有复读非零才消耗一个未完成轮次。最多4轮后最终必须`memory.current=0`才读final/rmdir。case/S清完后，L按FD20从guardian做至多一次final迁移，或在此前失败已留carrier时以零次迁移重验当前域；随后冻结并导出`result.journal`，取得owner final capture ACK，再按FD06归一化、close_range并复核准确0–11表。canonical `CLEANUP_HANDOFF` H（≤16KiB）绑定准确batch/session/boot、D/tree/plan/bundle/cleanup-source摘要、bridge及其setup/arm/tail API、carrier-memfd flags/size/digest预期摘要、D0、FD0–11的fstat/access-mode/status flags/CLOEXEC期望（FD3另含signalfd sigmask）、W absolute identity/PID/starttime/W0/BOOTTIME expiry/arm摘要、W status mapping摘要、L的PDEATHSIG(SIGKILL)与W PPID、原work/containment双钟绝对期限、UTC not-after、stop/success latch、case位图、最终action counter/hash、37个动作excursion status/摘要向量、final carrier ready记录、owner action-ACK capture heads、sealed `result.journal`最终摘要/slot状态、两路final marker counter/digest、final ACK/capture head/status、全部stage final/EMPTY digest、`process_cpu_at_handoff_ns`及紧邻的`handoff_boottime_ns/handoff_monotonic_ns/handoff_realtime_ns`与采样顺序、guardian/carrier累计、membership边界样本摘要、`CPU_SAMPLE_ROUND_NS`/归属/迁移双计规则、segment/stop/overshoot catalog摘要、两域剩余CPU、两个exec gap的CPU硬界与wall admission界及已观测摘要、ITIMER_PROF resolution/向下timeval量化/最小非零值/允许readback误差/expiry/requested/actual、临时RLIMIT_CPU pair及readback、sealed `CP_MAX_NS`及preparse公式、`Q0`/有限RLIMIT_SIGPENDING pair/`SigQ=Q0…Q0+4`转换摘要/两代各四timer的固定create/rebuild顺序、fatal/deadline timer身份/absolute expiry/状态、`DEADLINE_SIGNAL`、全部protocol FD `O_NONBLOCK`预期、cleanup-final schema/对象/ceiling及`TC_MAX_NS/TW_MAX_NS`；H不内联excursion slot/capture records，也不得预填exec后raw cleanup值或写回`result.journal`，避免超过16KiB或自引用。H及SHA-256(H)作为只读argv，只尝试一次`execve(ABS_RUNTIME,[ABS_RUNTIME,"-I","-B","-c",CLEANUP_SOURCE,H,H_SHA256],{LANG=C,LC_ALL=C})`；固定`CLEANUP_SOURCE`≤16KiB并与H schema一起由原plan/manifest封存。exec前先耗尽signalfd并确认全部blocked stop/deadline pending为空，复核W identity/PID/starttime、W expiry余量、 `PDEATHSIG(SIGKILL)`和PPID。L先形成H的固定前缀，再按本文通用公式取handoff process/三钟样本、 资格化ITIMER_PROF与临时RLIMIT hard候选。F0固定ITIMER_PROF有效resolution、timeval微秒表示、向下量化 规则、最小非零值和readback误差；量化不得把expiry推迟，误差及signal generation/delivery到terminal exit的全部CPU纳入`EXEC_GUARD_DELIVERY_OVERSHOOT_NS`，量化后非正即不得exec。L arm/readback ITIMER_PROF并一次原子设置/readback临时CPU soft/hard后，才把pre-exec requested/actual填入H并完成 canonical encode/SHA。P0 remaining、restore/disarm等未来值不得写入H。L再发送至多一个logical `CLEANUP_EXEC_BEGIN{H_digest}`；它预构造且≤atomic-write bound，零字节EAGAIN只可在原deadline/W expiry内回ppoll继续同一未发送frame，完整raw write时H不变，partial/EPIPE/其它错误或deadline把 success latch永久锁UNKNOWN；如仍有guard余量，只可重算带该latch的H/SHA并继续唯一cleanup exec， 不得从frame头重发或发送第二帧。该frame结束后不再做FD mutation并立即exec。 exec后首个user-code按固定顺序读取同一process clock为P0、`getitimer(ITIMER_PROF)`核armed且remaining 非零/SIGPROF DFL+unblocked、从继承FD4核`Threads=1`、readback临时RLIMIT_CPU和 `PDEATHSIG(SIGKILL)`/W PPID；preparse阶段只以sealed最小余量判断，不读取未解析H的expected字段。 任一步失败不得创建timer或继续。随后由继承RLIMIT派生Q0，以sealed source/manifest常量把preparse fatal expiry设为`min(P0+CP_MAX_NS,20s-STOP_CPU_MAX_NS[PROCESS])-FATAL_DELIVERY_OVERSHOOT_NS`， 完成SIGALRM默认/unblock、cleanup-generation fatal timer重建/arm/readback；候选不晚于P0或正常 pre-arm/parse/full-rearm不能严格早于expiry即停止。立即耗尽继承signalfd并核全部blocked stop/deadline pending为空及`SigQ=Q0+1`，任何旧event只可stop。preparse guard生效后才严格解析并验 source/H；紧邻取P1，验证P0/P1不小于H handoff且P1早于两个CPU guard expiry，把 `P1-process_cpu_at_handoff_ns+CPU_SAMPLE_ROUND_NS`只追加一次到carrier并更新last；使用H的arm actual及P0/P1 delta核ITIMER remaining/candidate，立即按完整ledger/catalog full rearm/readback fatal timer，且P0→readback≤CP_MAX_NS。 只有full-ledger fatal已生效并早于ITIMER expiry，L才凭已资格CAP_SYS_RESOURCE恢复/readback RLIMIT_CPU `(19,20)s`，再disarm/readback ITIMER_PROF为零并核SIGPROF无pending；任一步失败让更早 guard保持并只能UNKNOWN。随后读取当前相邻三钟并对H handoff三钟验证wall elapsed/step，再按 BOOTTIME、MONOTONIC、REALTIME顺序重建/arm/readback原absolute wall timer且逐项核`SigQ`至 `Q0+4`；紧邻复测P2/三钟，只追加`P2-P1+CPU_SAMPLE_ROUND_NS`并再次按完整公式rearm。 handoff→P2 CPU须在cleanup CPU gap内，三钟elapsed须在cleanup wall admission界内；zero-CPU stall由W expiry/PDEATHSIG收口。最后复核原期限、boot、W PPID/starttime/expiry、PDEATHSIG、单线程、 RLIMIT/affinity、signal mask/signalfd/SIGPIPE、FD数量/身份/flags及自身在FD6 carrier leaf。失败不 重试、不写成功并只在原containment/W deadline内有限收尾。该exec释放guardian内旧CPython mm/bridge；continuation完成上述startup资格后，先在已验证carrier按FD17从FD10复制bridge到新carrier-owned sealed executable memfd，再只从该memfd资格化并加载mapping；copy/seal/load的CPU、payload逻辑/RAM/AS≤1MiB、含folio/THP/metadata/allocator的瞬时物理风险≤2MiB/1 shmem inode及file-backed/shared charge全计carrier/shared，实际记录留给`CLEANUP_FINAL`。关闭stage artifact及memfd临时FD后，在任何stage unlink前向setup入口注册固定receipt buffer、layout、fd0–fd2及一字节stdin probe scratch；当cleanup-final ACK取得后、进入最终sample前再由arm入口一次性补齐counter/digest/ACK head等最终immutable inputs，mapping保留至`_exit`。随后才复核并清理含bridge和两个journal的完整stage并关闭FD10/11，再依次把guardian、B reclaim至0、读final、remove、关闭FD9/8并等parent dying=0，最后证明anchor D0/dying=0。不得假定css_offline/reparent自动释放folio。F2须完成该路线的source/synthetic/fault硬门；若已有适用本机native fixture则运行同类tmpfs/runtime workload，否则准确保留NOT_RUN而不冒充目标PASS。F3必须在准确目标内核逐层实证接口、controls、reclaim、current=0和cleanup exec，任一步不成立不得写成功 |
| FD20 | guardian零outer输出与有界carrier excursion | L首次进入guardian后直至每次实际迁出前，所有正常、stop、异常、traceback、diagnostic和signal路径对fd1/fd2均须保持零write调用/零字节；禁止`write/writev/send/sendmsg/sendfile/splice`及任何缓冲层绕过。任何额外outer byte或不能把每个允许frame绑定到准确carrier membership的观察都立即锁定UNKNOWN，即使随后`memory.current=0`也不能恢复成功资格。guardian期非action的case/result/error只写预分配`result.journal`固定slot：文件固定752KiB（770048 bytes），offset 0为8KiB header；offset 8192起为十二个48KiB case区（各stdout 32KiB、stderr 8KiB、structured metadata 8KiB）；offset 598016起为38个4KiB excursion区；offset 753664起为16KiB terminal/global区；终点770048。每区只按manifest固定offset/length `pwrite`、`fdatasync`，不得append、延长、打洞或动态增加slot，overflow即UNKNOWN。前37个excursion区分别冻结FD18动作往返的前后membership、原期限、counter/digest、ACK/capture head、迁回结果、CPU和错误枚举；第38区在任何导出前冻结`FINAL_CARRIER_READY`、`final_migration_write_count=0\|1`、`action.journal`最终摘要、result slot bitmap/counters和固定占位，不能声称再次进入guardian，也不得自含result全文件摘要或导出后ACK。supervisor reclaim/final/remove、最后FD关闭且B dying=0后，每个可返回控制的final-success分段前后都须复核L累计CPU<19s及无observed/pending `SIGXCPU`；若L仍在guardian则静默重验held原carrier、只尝试一次final self-migration并复核实际membership；若此前action write/ACK/迁回失败已把L留在carrier，则只重验当前membership，final write count=0且不得再次写`cgroup.procs`或恢复success。随后冻结第38区并`fdatasync`，再冻结整个journal并计算全文件摘要，从此不修改该文件，最后从carrier导出全部固定frame。向stdout/stderr各写唯一≤256-byte `FINAL_CAPTURE` marker；owner把两路全部延迟frame和marker append+fsync private capture后，经原stdin回唯一≤256-byte `FINAL_CAPTURE_ACK`。final carrier entry、journal freeze、752KiB导出及ACK合计≤15s，其中marker后ACK≤5s，并全部占用110s final-success reserve。H绑定result全文件摘要及ACK/capture head但不写回journal；只内联固定status/bitmap/摘要向量，不内联4KiB slot或capture记录，F2须用37项及22个stage entry的最大编码证明H≤16KiB。导出/marker/ACK任一步失败锁定UNKNOWN且不重发；仍只可做同一次cleanup。动作往返≤37、final carrier write≤1；成功最大为旧carrier、新guardian各38次、合计76次self-write，失败按实际≤76。动作回到guardian后才可放行S；每次门、outer bytes、CPU/内存/audit费用和原deadline均留证且不得刷新。cleanup continuation须在carrier fd1/fd2两端仍打开时实测guardian `memory.current=0`。F0固定整数`TAIL_CPU_MAX_NS=TC_MAX_NS`和`TAIL_WALL_MAX_NS=TW_MAX_NS`，其中`0<TC_MAX_NS<1000000000`、`0<TW_MAX_NS≤1000000000`；F0/F2以源码和目标资格化最坏路径证明从native入口取得最终CPU sample到进程退出的post-gate tail实际process CPU≤`TC_MAX_NS`，`TW_MAX_NS`为owner强制的elapsed接受界。全部cleanup和可失败验证完成、≤512-byte `SUCCESS_RECEIPT`固定模板已预分配、fd1 `O_NONBLOCK`已readback且owner刚以`CLEANUP_FINAL_ACK`证明先前stdout已读尽后，continuation把最终immutable inputs交给已setup的bridge arm入口，随后只调用一次不返回的`fixture_cleanup_tail`。该native入口先按固定顺序取得最终process/BOOTTIME/MONOTONIC/REALTIME样本，把last→sample加rounding计入carrier，并完成最终gate：证明`process_cpu_ns+TC_MAX_NS≤18000000000`、`carrier_cpu_ns+TC_MAX_NS≤9000000000`、guardian usage≤9s，两个guest clock的`now+TW_MAX_NS`仍早于work与UTC最坏边界、REALTIME相对双钟无step，耗尽既有signalfd并确认stop latch及stop-set pending均为空；再以预注册一字节scratch对nonblocking fd0执行一次raw `read`，只接受`-1/EAGAIN`，EOF、额外byte或其它结果均走nonzero exit。gate通过后它只把最终样本、counter/previous digest/H digest/cleanup-final digest及ACK capture head按固定offset原位填入模板，以manifest固定的无分配、无loop路径封口digest，恢复`SIGUSR1/HUP/TERM/INT/QUIT/XCPU/DEADLINE_SIGNAL`默认处置并unblock catchable stop/deadline set；SIGPIPE保持ignore直到对fd1完成一次长度≤512且不超过已资格`_PC_PIPE_BUF`的raw nonblocking `write`并取得返回值，随后恢复SIGPIPE默认处置、关闭fd1/fd2并`_exit`。最终sample之后禁止Python、allocation、import、loop、cleanup、重写或第二帧。仅准确全写且两次close均成功才`_exit(0)`；短写/EAGAIN/EPIPE/其它write或close错误均在恢复SIGPIPE默认处置并尽力关闭两端后`_exit(nonzero)`，新到catchable stop/deadline signal可直接产生signal wait。owner只有在固定private capture取得完整且唯一的`CLEANUP_FINAL`/ACK及`SUCCESS_RECEIPT` frame、按绑定offset/clock证明frame/W remote status/exit/双EOF均早于guest gate+TW_MAX_NS及全部原成功期限、sealed W映射与W remote status 0证明原L为CLD_EXITED/0、原local client正常wait 0、stdout/stderr真实EOF并完成capture最终fsync/seal时才接受success；由`+TC_MAX_NS`门保持最终guardian/carrier/process成功界≤9s/≤9s/≤18s。成功不依赖pipe对象销毁或缓存页释放 |

L的域CPU账以同一`CLOCK_PROCESS_CPUTIME_ID`连续样本为准。F0固定`CPU_SAMPLE_ROUND_NS`，每个
verified membership边界取样；明确区间向上计入所在域，migration syscall至新membership核验的
不确定区间连同rounding向guardian/carrier双计。37个excursion slot、第38 slot及H按FD19保存样本、
累计和摘要；guardian `cpu.stat`只作独立上界交叉核对，禁止用`process−guardian`反推carrier。
cleanup exec后只把首个guard-active复测与handoff之差加rounding追加一次并更新last；以后只追加
相邻`sample_i-last`加rounding，不得每次减handoff重复累计。

F0还冻结每个可进入/可失败L segment的process及两域CPU硬envelope、
`STOP_CPU_MAX_NS[GUARDIAN,CARRIER,PROCESS]`、`FATAL_DELIVERY_OVERSHOOT_NS`、
`RLIMIT_CPU_KILL_OVERSHOOT_NS`、`EXEC_GUARD_DELIVERY_OVERSHOOT_NS`、
`initial_exec_gap_cpu_ns/initial_exec_gap_wall_ns`和
`cleanup_exec_gap_cpu_ns/cleanup_exec_gap_wall_ns`，以及封存在`CLEANUP_SOURCE`/manifest中的
`CLEANUP_PREPARSE_CPU_MAX_NS=CP_MAX_NS`。initial direct launcher固定
`INITIAL_CPU_SOFT_S=8`、`INITIAL_CPU_HARD_S=9`，且目标资格必须证明
`0≤RLIMIT_CPU_KILL_OVERSHOOT_NS≤1s`和
`9s+RLIMIT_CPU_KILL_OVERSHOOT_NS≤10s`。cleanup guard须满足
`0<EXEC_GUARD_DELIVERY_OVERSHOOT_NS<CP_MAX_NS<cleanup_exec_gap_cpu_ns`；POSIX fatal guard另满足
`0<FATAL_DELIVERY_OVERSHOOT_NS<CP_MAX_NS`。source/fault资格化证明continuation首样本到H验真后按
完整账本首次rearm的正常最坏CPU严格早于两个适用guard expiry。

除initial loader、cleanup exec gap与post-gate tail外，一个未block且`SIG_DFL`的SIGALRM
process-clock POSIX timer在扣除`FATAL_DELIVERY_OVERSHOOT_NS`的absolute process-clock点
fail closed；timer开销计入envelope，signal wait只能UNKNOWN。进入任一segment前须对
`GUARDIAN/CARRIER`分别证明`accum[domain]+segment_envelope[domain]+STOP_CPU_MAX_NS[domain]≤10s`
并对`PROCESS`证明≤20s；否则不进入，只走已预留stop。仍可成功的segment还须为全部固定剩余段及
tail预留guardian/carrier/process≤9s/≤9s/≤18s。每个segment进入及每个verified membership边界都
以同一process-clock `Pnow`用`TIMER_ABSTIME` rearm fatal timer。对该segment可能计费的每个域
（迁移歧义同时取guardian与carrier）及PROCESS，先形成本段候选
`Pnow+segment_envelope[domain_or_process]`；physical候选为
`Pnow+limit-accum-STOP_CPU_MAX_NS`，其中域limit=10s、PROCESS limit=20s；仍可success时另取
`Pnow+success_limit-accum-remaining_success_envelopes_after_segment-tail_reserve`，success limit为
guardian/carrier/process的9s/9s/18s，tail reserve向量为`[0,TC_MAX_NS,TC_MAX_NS]`。从全部适用候选
的最早值再减fatal overshoot作为实际expiry并readback。任何最小候选余量≤overshoot、catalog不能
证明正常路径严格早于expiry、arm/readback失败或timer到期均锁UNKNOWN并停止success。

initial远端command必须使用FD03的W。W在clone L前设置/readback自身RLIMIT_CPU `(8,9)s`，使child从出生即继承同一累计guard；stopped window只独立readback该CPU pair并设置其它initial profile；SIGXCPU由W在clone前设为`SIG_IGN`并跨exec继承，因此soft 8s不产生core或helper，
physical CPU由不可捕获的hard 9s SIGKILL加已资格kill overshoot闭合在carrier 10s内。child的
PDEATHSIG/PPID/SIGSTOP前缀、W的pidfd/prlimit/readback/timer arm和唯一SIGCONT次序都由sealed W与F2
fault test固定；L从出生到复测的全部CPU连同rounding均计carrier。L首个user-code先读process clock，
立即核准确W parent、`PDEATHSIG(SIGKILL)`、同一held procfs `Threads=1`、RLIMIT_CPU `(8,9)s`、
SIGXCPU ignore和准确继承的`W_BLOCKED_SET`，随后在任何timer创建前读取/资格化Q0、设置并readback有限RLIMIT_SIGPENDING；再完成
SIGALRM `SIG_DFL`/unblock、fatal timer create/arm/readback和紧邻复测。该值须落在
`initial_exec_gap_cpu_ns`，runtime/loader/import closure须证明首个user-code前不改变RLIMIT_CPU、
SIGXCPU、PDEATHSIG或W关系。只有fatal timer已active/readback、当前CPU仍在最早候选内且目标已
资格化root CAP_SYS_RESOURCE，L先block SIGXCPU、恢复`SIG_DFL`，再创建/readback接收它与已继承
`W_BLOCKED_SET`的signalfd，耗尽并核pending；此前已经pending的SIGUSR1、SIGXCPU或其它stop event只能
使initial clean-stop。只有没有stop/XCPU时才把CPU提高并readback为供S继承的`(20,100)s`，raise仍受
已生效fatal timer约束；raise后立即再耗尽signalfd并核pending，不能继续的路径不得进入success。

从W唯一SIGCONT到initial正常门完成的`initial_exec_gap_wall_ns`是admission/success bound；它包含
runtime启动、CPU guard、G0、继承signal mask复核/SIGXCPU block/signalfd、三个wall timer create/readback及
BOOTTIME/MONOTONIC在G0+48s的首次arm。REALTIME保持disarmed，直至完整DECLARE给出UTC/outer字段且
验证后才arm/rearm三者。物理远端wall backstop是W在放行前已arm/readback且不可刷新的BOOTTIME
deadline，不用正常gap或owner local kill冒充。owner启动client前只证明W static identity/pre-carrier prefix/资源预算；任一prelaunch资格不成立即不启动client。actual W PID/starttime/W0/arm record由HELLO带回，并在`BATCH_RELEASE`前与两个initial gap一并证明落在原双钟/外层余量内；任一postlaunch W/limit/slack/CAP/raise资格不成立即不release，delivery保持consumed并按完整clean rejection、W status和EOF证据判BLOCKED，否则判UNKNOWN。

cleanup exec前，L以尚可信的parent账本证明
`carrier_accum+cleanup_exec_gap_cpu_ns+STOP_CPU_MAX_NS[CARRIER]≤10s`和
`process_at_handoff+cleanup_exec_gap_cpu_ns+STOP_CPU_MAX_NS[PROCESS]≤20s`，success路径还保留后续
固定段与TC后的9s/18s，并证明正常路径`now+cleanup_exec_gap_wall_ns`早于work/containment/UTC及W
deadline。它先形成除cross-exec guard actual外的canonical H字段并耗尽既有stop/deadline event；再取
handoff process sample并更新carrier/process账，确认原`ITIMER_PROF`为零、SIGPROF无pending，把
SIGPROF设为unblocked/`SIG_DFL`。它按通用公式从本gap envelope、carrier/process physical候选和仍
适用success候选中取最早值：physical候选扣除从expiry到terminal exit的完整
`EXEC_GUARD_DELIVERY_OVERSHOOT_NS`，success候选扣除gap后的全部remaining-success envelopes与TC。
只有正常H最终编码/hash/BEGIN/exec/P0/preparse/full-ledger rearm严格早于该expiry时，才用唯一一次
`setitimer(ITIMER_PROF)`设置相对CPU guard并readback。

同一pre-exec gate还按当前absolute process CPU和carrier/process最早physical候选，保守向下取一个
整数`CLEANUP_RLIMIT_HARD_S`，使
`HARD_S*1s+RLIMIT_CPU_KILL_OVERSHOOT_NS`不晚于最早physical候选；soft设为
`min(19,HARD_S)`，且当前CPU、正常gap envelope和guard transition必须严格早于soft/hard cutoff。
L以CAP_SYS_RESOURCE降低并readback该pair。没有可用整数、set/readback失败或任何候选无正余量均
不得exec。随后把ITIMER requested/actual、handoff sample、absolute候选、临时RLIMIT pair/readback及
W remaining写入H，最终canonical encode/hash；arm后全部H编码/hash/BEGIN费用仍计cleanup gap。
`CLEANUP_EXEC_BEGIN`完整发送后立即唯一exec。ITIMER_PROF与RLIMIT都跨`execve`保留；前者不属于两代
八次`timer_create`，也不消耗Q0的POSIX timer reservation。sealed runtime/loader closure须证明首个
user-code前不修改ITIMER_PROF、SIGPROF、RLIMIT_CPU或W/PDEATH关系。cleanup gap的wall数值仅是
admission/success bound，zero-CPU loader stall由W的全生命周期deadline最终SIGKILL。

continuation首个user-code按P0→`getitimer(ITIMER_PROF)`核仍armed、非零remaining、SIGPROF
`SIG_DFL`/unblocked→held procfs `Threads=1`→临时RLIMIT readback的顺序执行；preparse阶段只用sealed
最小余量判断，尚不引用未解析H的expected值。任何失败不得创建timer或继续。它随后按sealed
preparse公式建立/readback cleanup-generation SIGALRM fatal timer，验H并取得P1，把handoff→P1只
追加一次到carrier，使用H的arm actual与P0/P1 delta核ITIMER remaining/candidate，再按完整ledger首次
rearm/readback。只有该full-ledger guard已生效且严格早于ITIMER expiry，才凭CAP_SYS_RESOURCE恢复并
readback RLIMIT_CPU `(19,20)s`，再把ITIMER_PROF disarm/readback为零并确认SIGPROF无pending；任一步
失败让更早guard继续生效并只能UNKNOWN。之后重建三个wall timer并取得P2。handoff→P2 CPU和双钟
elapsed分别落在cleanup gap界内才结束正常gap。H只绑定pre-exec handoff/candidate/request/arm/readback/
临时RLIMIT actual；`CLEANUP_FINAL`与private capture绑定P0 remaining、H核对、RLIMIT restore、disarm及
pending actual，避免时间自引用。catalog、W、两种CPU kernel guard、exec-survival、runtime不篡改或
overshoot在F0/F2/F3任一层不能资格化，即mutation前BLOCKED；不得以事后P0/P2或success gate替代
跨exec强制。

guest侧outer fd0/fd1/fd2、L/S/G/R/O protocol pipe/socket，以及delivery owner持有的local client
stdin/stdout/stderr三端都须由F0固定真实类型，进入协议前成功设置并readback `O_NONBLOCK`；不支持即
BLOCKED。每个guest actor只用单线程固定状态机，以`ppoll`同时等待当前protocol FD、signalfd/stop
source和pidfd。owner同样用一个单线程poll状态机同时观察client stdin可写、stdout/stderr可读、client
pidfd/wait和三个独立的nonblocking/CLOEXEC owner timerfd；三个timerfd分别以
`TFD_TIMER_ABSTIME`绑定原REALTIME/BOOTTIME/MONOTONIC outer deadline，REALTIME另用
`TFD_TIMER_CANCEL_ON_SET`把clock step变成失败；owner在启动local client前必须按固定顺序创建、
absolute arm并readback三者，任何失败都不得启动client。owner必须持续并行drain两条输出，每流各持固定
offset/counter/digest，只在stdin可写时推进同一input frame remainder；不能按stdout→stderr或
write→read的阻塞顺序。每个action/final/cleanup frame都须先完整append+fsync到对应private capture，
再允许ACK。owner FD表、timerfd/pidfd/capture临时FD峰值和费用由F0封存，不计入guest FD/RLIMIT表。
L另外创建不占FD、共用一个plan-fixed blocked
realtime `DEADLINE_SIGNAL`的BOOTTIME、MONOTONIC和REALTIME三个POSIX absolute timer；连同唯一
`CLOCK_PROCESS_CPUTIME_ID`/SIGALRM fatal timer，只允许initial与cleanup-continuation两个固定generation，每代仅有按固定顺序排列的四个
`timer_create` call site且同时live≤4。success-capable完整路径在每代建成四项、总计八次create；任一
失败路径只能停在对应固定序列前缀，且全生命周期create≤8。任一generation第五个live timer、固定
两组之外的额外create或第九次create均拒绝。
每次rearm
先把`UTC_not_after-now_REALTIME`按封存offset/skew/drift最坏界映射成两个双钟cutoff；BOOTTIME和
MONOTONIC timer各取`min(original_absolute_deadline,mapped_UTC_cutoff)`，REALTIME timer取原UTC
not-after，因而REALTIME后退不能延长双钟保护，前跳由REALTIME timer唤醒。四者身份、signal queue和absolute expiry都进H/证据。
F0固定`SIGPENDING_TIMER_RESERVATIONS=4`和`SIGPENDING_EVENT_MARGIN=4`；L在任何timer创建前从已资格
`/proc/self/status`的`SigQ`读取同一real UID准确当前占用`Q0`，同时读取并资格化原limit，确认非本协议
占用不漂移，并在initial generation第一次`timer_create`前把soft/hard均设为有限`Q0+8`且readback。
四项覆盖success-capable完整generation的四个同时live timer reservation；失败前缀只占其前缀，另四项保守覆盖跨exec旧event与新generation
event同时pending。initial entry按fatal、BOOTTIME、
MONOTONIC、REALTIME顺序创建并在每次create及其当时应有的arm/disarm readback后核对
`SigQ=Q0+1…Q0+4`；前两项wall timer先保护本地G0+48s，第三项wall timer在DECLARE验证前保持
disarmed。cleanup exec前须耗尽signalfd并确认全部blocked stop/deadline pending为空；exec删除四个POSIX
timer，但不删除已经arm/readback的`ITIMER_PROF`或临时RLIMIT_CPU。continuation首段固定按P0→
`getitimer(ITIMER_PROF)`/SIGPROF状态→继承FD4的`Threads=1`→临时RLIMIT/PDEATHSIG/W parent readback
执行，再按sealed preparse公式重建fatal POSIX timer并立即耗尽继承signalfd/核pending且要求
`SigQ=Q0+1`；任何旧deadline event都只可stop。严格验H、P1和ITIMER余量后按完整ledger首次rearm
fatal timer；只有该guard已经active/readback且早于ITIMER expiry，才恢复/readback RLIMIT_CPU
`(19,20)s`、disarm/readback ITIMER并核SIGPROF无pending。随后按BOOTTIME、MONOTONIC、REALTIME固定
顺序重建三个wall timer并逐次核对至`Q0+4`。ITIMER_PROF不属于这两代四项POSIX timer，既不增加
`timer_create`次数也不占Q0 reservation；该顺序和`Q0+8`同时覆盖exec竞态中最多三个旧wall event
pending加一个新fatal reservation。任一create/arm/
readback失败、Q0漂移或额度算术不一致时，F0/F2静态资格缺失或initial首个mutation前的现场失败为
BLOCKED/CLEAN_REJECTED；accepted或已mutation后的运行故障以及cleanup generation故障只能锁定
UNKNOWN_RETAINED并有限收尾。任一generation可能出现第五个live timer，或可能走第九次及其它额外
`timer_create`的源码路径，必须在F2或首mutation前BLOCKED。任一wall
timer使signalfd readable；每次wake、EINTR、partial I/O
前后都重读双钟/REALTIME并验证无step，不能只给`ppoll`一个MONOTONIC relative timeout。

所有read/write都有固定frame/chunk/buffer上界；partial read及manifest明确允许chunk/remainder的
large write只可推进同一logical frame remainder，遇stop/deadline/error后永久锁UNKNOWN且不得从
frame头重发。action/marker/ACK/`CLEANUP_EXEC_BEGIN`等小帧不超过F0资格化的actual atomic-write界：
写前可因零字节EAGAIN回ppoll，raw write一旦发生必须全写，partial即错误并锁UNKNOWN；752KiB result
export及≤32KiB `CLEANUP_FINAL`使用固定≤4KiB chunk表与counter/digest，success receipt仍是唯一一次
≤512-byte raw write且EAGAIN/非全写即失败。DECLARE/release
48s、action 2s、export 15s、marker ACK 5s、cleanup-final 5s及全部stop/containment上界都必须由该
状态机执行；阻塞I/O、过去RTT或process-CPU timer不能替代墙钟期限。F0/F2对pipe满、对端停读、
单流反压而另一流持续有数据、stdin同时partial、partial、EAGAIN、EINTR、signal、suspend/resume、
owner timerfd到期/REALTIME cancel、client先退出/迟退出、EOF及双钟边界做fault test，F3再资格化
实际transport。

cleanup exec后、final gate前，continuation须用启动时预分配的固定32KiB buffer形成唯一canonical
`CLEANUP_FINAL`（≤32KiB）：包含canonical H bytes/digest、continuation启动/H/FD验证、完整stage
manifest复核与删除、stage parent remove、guardian/B完整final/control raw bytes、reclaim/remove/
last-FD/dying、anchor D0/dying复原及CPU样本/累计/catalog/timer状态。frame带counter/previous digest，
不自含其digest、ACK或capture head。L从已验证carrier只发这一logical frame；owner append+fsync既有
private capture后经fd0回唯一≤256-byte `CLEANUP_FINAL_ACK(counter,frame_digest,capture_head)`。
exchange≤5s、失败锁UNKNOWN且不重发；复用fd0/fd1、固定buffer和现有capture，CPU/RAM/pipe/audit费用
全计carrier/shared。随后≤512-byte `SUCCESS_RECEIPT`必须绑定cleanup-final digest、ACK和capture head；
H只预绑schema/对象/上界，不能把未来digest冒充raw cleanup证据。

## collector 固定合同

- `Threads=1`，唯一单级 `NStgid`/`NSpid` 与 own getpid 或 G 的原 fork PID精确相等；
- held `/proc` 的 procfs/mount 资格；只有 `self`、`ns/pid`和`ns/mnt`为固定 magiclink例外；
  nsfd须为NSFS_MAGIC且`NS_GET_NSTYPE`角色正确；
- G持原R/O pidfd且不提前reap；S预先设child-subreaper，G异常死亡时只对准确reparent的R/O
  取得typed wait，缺失不补造；
- 三个匿名`SOCK_SEQPACKET` socketpair逐帧核对`SCM_CREDENTIALS`；R/O各一个32-byte nonce；
  SOURCE和cross FD与G独立打开的direct-child对象一致；
- 固定15帧、role/counter/session/source/runtime/context摘要；拒绝截断、重复、乱序、旧session、
  unexpected ancillary/FD、对象替换、PID reuse和无原活性关系的数字PID/inode；
- G只向原child pidfd发TERM/KILL并取得原wait；control/cross EOF、G typed wait、S wait、L wait和
  owner所见stdout/stderr EOF逐层分列。

接口语义依据 Linux man-pages 的
[proc_pid_status(5)](https://man7.org/linux/man-pages/man5/proc_pid_status.5.html)、
[pidfd_open(2)](https://man7.org/linux/man-pages/man2/pidfd_open.2.html)、
[clone3(2)](https://man7.org/linux/man-pages/man2/clone3.2.html)、
[waitid(2)](https://man7.org/linux/man-pages/man2/wait.2.html)、
[prlimit(2)](https://man7.org/linux/man-pages/man2/getrlimit.2.html)、
[execve(2)](https://man7.org/linux/man-pages/man2/execve.2.html)、
[setitimer(2)](https://man7.org/linux/man-pages/man2/setitimer.2.html)、
[timer_create(2)](https://man7.org/linux/man-pages/man2/timer_create.2.html)、
[timerfd_create(2)](https://man7.org/linux/man-pages/man2/timerfd_create.2.html)、
[signalfd(2)](https://man7.org/linux/man-pages/man2/signalfd.2.html)、
[ioctl_nsfs(2)](https://man7.org/linux/man-pages/man2/ioctl_nsfs.2.html)、
[unix(7)](https://man7.org/linux/man-pages/man7/unix.7.html)、
[PR_SET_DUMPABLE(2)](https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html)、
[PR_SET_PDEATHSIG(2)](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html)和
[core(5)](https://man7.org/linux/man-pages/man5/core.5.html)。文档语义不证明guest实际支持。

## 每个 G/R/O session 的 ceilings

| 资源 | 固定 ceiling 与必要证据 |
| --- | --- |
| task | case leaf同时恰好G/R/O三项；`pids.max=3`、`pids.peak≤3`、G源码恰好fork两次且无thread/exec；bootstrap在exec前固定CPU(5,5)s、AS/DATA(96,96)MiB、FSIZE(0,0)、NOFILE(24,24)、CORE(0,0)、STACK(8,8)MiB、MEMLOCK/MSGQUEUE/NICE/RTPRIO/RTTIME(0,0)，并准确继承已验证的NPROC/LOCKS/RSS/SIGPENDING pair |
| FD | 每进程≤24；G在IPC前关闭fd0，安装table slots峰值G≤22、R≤13、O≤13，合计≤48；协议同时queued SCM引用≤2，含queue总引用≤50；失败路径同界 |
| artifact/context | G artifact+context逻辑bytes≤256KiB，context≤16KiB；无guest dependency install |
| status/ns open | status每读≤16KiB、最多12次/合计≤192KiB；namespace open/rebind≤40；失败不循环probe |
| randomness/IPC | getrandom总计64 bytes；≤15帧、≤4KiB/帧、payload≤60KiB；每帧恰一credentials，带权帧各最多2 nsfd |
| output | G stdout≤32KiB、stderr≤8KiB；R/O无外部输出；内外计数，截断不能变成功 |
| cgroup memory | `memory.max=96MiB`、`memory.swap.max=0`、`memory.min=0`、`memory.low=0`、`memory.high=max`；fresh leaf最终`memory.peak≤128MiB`且退出/关FD/reclaim后`memory.current=0`。固定runtime/shared映射池≤64MiB，stage物理风险≤3MiB，保守session物理暴露≤195MiB |
| CPU | `cpu.max=5000 100000`、`cpu.max.burst=0`、单一固定effective CPU；fresh leaf完整区间`cpu.stat usage_usec≤5,000,000` |
| time | 每case在intent/leaf/action前固定同一不可刷新原点`CASE_T0`。`CASE_T0→+20s`共同容纳intent、leaf create/config/zero readback、首例最多四项/后续三项carrier excursion、clone/ARMED/drop/exec、G bootstrap、N09≤2s及活体observe；不是各项上界相加，G越晚启动可用observe越短。`+20→+25s`只stop，`+25→+30s`只exit/EOF/report/`CASE_DRAINED`，`+30→+40s`只做最多四轮reclaim、final/`CASE_FINAL` fdatasync、unlink、last-FD close和B dying=0；各absolute边界不刷新、不借时，完整case≤40s |
| files/network | G/R/O新文件0 bytes/0 inode，网络连接0；只允许匿名AF_UNIX socketpair，不bind/connect；stage/audit/capture另计 |

Linux cgroup v2明确说明task migration不会迁移既有memory charge，因此case leaf只证明本leaf
kernel-accounted peak；runtime共享页、pre-exec/bootstrap和tmpfs另行保守计费。依据见
[cgroup v2 memory ownership](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-ownership)。

## 一次完整 batch 的 ceilings 与账法

一个B/C只授权一次carrier request。owner在request前一次取得REALTIME、BOOTTIME、紧邻
MONOTONIC并各自固定outer≤840s deadline；bootstrap握手和只读拒绝前缀≤48s，HELLO RTT≤10s、
owner/guest realtime offset区间完整落在±2s，且owner三个outer clock及guest UTC not-after的
剩余均≥792s时才可`BATCH_RELEASE`。过去的RTT不约束release单程；L收到完整frame时按F0固定的
双方相对频率误差上界和HELLO guest采样后的实际双钟elapsed扩大offset区间，要求当前整个区间仍在
±2s，并据其最坏端独立要求guest UTC原始余量≥782s、owner剩余下界≥780s；同时核对双方三钟delta
无step、没有unsynchronized状态，并另证adjtimex/clocksource给出的随后760s最坏相对漂移≤2s。
随后从当时guest BOOTTIME和紧邻MONOTONIC各派生
不可刷新的work `+750s`和containment `+760s` deadline；成功必须同时早于两个
work clock和原UTC not-after，停止/receipt必须早于两个containment clock和原UTC not-after。
work内部固定保留`FINAL_SUCCESS_RESERVE=110s`：S关闭及supervisor final/remove≤15s，final carrier
entry、journal freeze/导出和owner ACK≤15s，FD/H/BEGIN与cleanup exec启动≤10s，carrier bridge
copy/digest/page-touch/seal/load/setup加完整stage验证/删除≤15s，
guardian/B最多四轮reclaim、final/remove和anchor复原≤35s，最后20s中`CLEANUP_FINAL`/durable ACK
≤5s，success receipt tail、进程退出、两路EOF和owner最终capture seal≤15s。每项只可缩短，不能互借超过110s总界；任何success-producing步骤不得移入随后
containment。每case从intent、leaf或action之前的同一`CASE_T0`派生20/25/30/40秒边界；首例四个、后续
三个最长2s的excursion都在`CASE_T0+20s`前完成，且不延长G observe边界。四个case边界之后分别
禁止observe、stop、exit/report和case收尾；未用余量不借给下一阶段。每个case开始和每个pre-action门
都须保留本case到`CASE_T0+40s`的剩余containment再加完整110s。
owner以原三个outer deadline的最早者为local client-group hard cutoff，并在其前10s只关闭carrier
stdin写端且保留stdout/stderr读端，以EOF触发L；两者
均不刷新。owner剩余下界780s到guest containment 760s的20s中，最多2s给相对漂移，至少8s保留在
远端containment完成与owner EOF stop之间，随后仍有10s到local hard cutoff；不扩大work。
除W在guard已生效后唯一clone L外，迟达且未获
`BATCH_RELEASE`的bootstrap不得创建、写入或
fork；transport仍可能留下的只读拒绝前缀按全额计费，不据此重发。

| 类别 | 整批上界 |
| --- | --- |
| remote watchdog W / 原carrier聚合 | W为单线程、全程至L退出只多一个task，B与其`pids.max=5`不含W；原carrier须现场证明可同时容纳既有parent/W/L。W从进程出生累计的RLIMIT_CPU在guard-arm时设/readback为`(8,9)s`，F0另以endpoint前提资格化guard前`W_PREFIX_CPU_MAX_NS≤1s`；hard-kill加资格化overshoot使W完整失败CPU风险≤10s，status 0还绑定最终绝对process CPU累计≤1s。L的carrier≤10s是独立process-clock账，W不混入且原carrier`cpu.stat`不得冒充L账，aggregate新增CPU风险≤20s。W guard前userspace AS/RSS及保守物理风险≤64MiB、入口installed FD≤8；guard后AS/DATA hard≤64MiB、STACK≤8MiB，image/file-backed/shared及kernel object也须闭合在同一64MiB风险内。该64MiB与既有64MiB carrier/shared pool只有准确extent/page归属证明时才去重，否则显式相加。entry至close_range峰值≤8；guard后的pre-clone installed FD峰值5（stdio 3+signalfd+timerfd），clone返回pidfd后基础峰值6；身份/proc临时FD=6严格串行使W瞬时峰值≤7；child停止时瞬时继承0–4共5项，恢复后关3/4并复核恰0–2，W关闭0–2后steady 3（signalfd/timerfd/pidfd）。聚合installed references、pidfd/timerfd/signalfd slab及pipe页另按F0固定字节上界列账。W不建文件/网络连接、outer read/write均0；认证/session/audit/journal归入carrier项但须单列W bytes/inodes。W0后的不可刷新BOOTTIME cap≤830s，wake→kill、kill→reap、reap→remote status/EOF三项固定margin合计≤12s；guard前`W_PREFIX_WALL_MAX_NS≤2s`只是accepted endpoint下的admission envelope，不冒充kernel hard界 |
| fresh batch cgroup B | 空distributor；固定`cpuset.cpus/mems`及effective值，`cpu.max=100000 100000`、burst=0、`memory.max=320MiB`、swap=0、min/low=0、high=max、`pids.max=5`；建leaf前唯一写`+cpu +cpuset +memory +pids`并readback subtree-control恰四项。子层清完后reclaim至`memory.current=0`，最终同一controls/subtree-control仍准确且`cpu.stat≤170s`、`memory.peak≤320MiB`、`pids.peak≤5` |
| guardian leaf / 全部carrier区段 | guardian为`cpu.max=20000 100000`/burst=0、memory.max=64MiB、swap=0、min/low=0、high=max、pids.max=1，L移出并唯一cleanup exec后reclaim至`memory.current=0`，绝对CPU≤10s/peak≤64MiB/pids.peak≤1；成功资格另要求guardian usage≤9s。L在guardian外的原carrier prefix、≤37个动作往返和最终tail以同一进程累计CPU连续计量，绝对合计≤10s、成功合计≤9s且每次迁移不归零；F0固定`TAIL_CPU_MAX_NS=TC_MAX_NS<1s`，最终gate要求`process_cpu_ns+TC_MAX_NS≤18s`、`carrier_cpu_ns+TC_MAX_NS≤9s`和guardian≤9s，并由F0/F2证明tail实际CPU≤TC_MAX_NS，故退出后的成功界仍为guardian/carrier/process≤9s/≤9s/≤18s。L由W在runtime前取得AS/DATA=(64,192)MiB、NOFILE=(32,64)、FSIZE4MiB，并在initial exact fatal active后把CPU从继承(8,9)s提高为(20,100)s；clone S返回时child仍在native gate，L在等待READY或放行前立即把自身降为CPU(19,20)s、AS/DATA=(64,64)MiB、NOFILE=(32,32)；CORE=(0,0)、FSIZE=(4,4)MiB、STACK=(8,8)MiB及固定零limits不变。每个pre-action及每个可返回控制的final-success分段前后都须读取固定语义的`CLOCK_PROCESS_CPUTIME_ID`并耗尽signalfd/核对pending，只有累计<19s且无已观察或pending `SIGXCPU`才可继续；达到或可能达到19s立即stop且永不写success。最终post-gate tail不返回控制，以`+TC_MAX_NS`门闭合并按FD20恢复默认signal处置；19→20s只供stop，不能由两项≤10s各自上界侵占。不在S继承前降低其所需hard limit。全部carrier窗口产生的transport pipe/socket、runtime和ACK分配进入同一shared physical/carrier风险，不按窗口重置 |
| supervisor leaf | `cpu.max=50000 100000`、burst=0、memory.max=192MiB、swap=0、min/low=0、high=max、pids.max=1；native S child只把CPU/AS/DATA/NOFILE soft提高到已继承hard，形成(100,100)s/(192,192)MiB/(64,64)，保留CORE0、FSIZE4MiB、STACK8MiB和完整已验证profile；S退出及相关FD关闭后reclaim至`memory.current=0`，最终CPU≤100s/peak≤192MiB/pids.peak≤1；不含直接出生在case leaf的child |
| native cases | 最多12且不并行；case leaf总CPU≤60s、每例intent/leaf/action/clone/bootstrap/N09/observe只共享`CASE_T0→CASE_T0+20s`工作窗，`+20→+25s`只stop、`+25→+30s`只exit/EOF/report、`+30→+40s`只reclaim/final/remove；十二例case containment合计≤480s、输出≤480KiB、status读取≤2304KiB |
| imported/shared runtime pool | batch固定映射/已有page-cache保守上界≤64MiB；不能因未计入fresh leaf而写零 |
| carrier/audit/journal | admitted attributable CPU ceiling≤30s：W从进程出生累计的完整风险≤10s、L全部carrier区段≤10s、认证/提权/audit/journal资格化envelope合计≤10s；W pre-arm CPU已包含在W的完整10s且另以`W_PREFIX_CPU_MAX_NS≤1s`资格化；最后一项是accepted endpoint premise下的封存路径界，不冒充kernel guard，不能资格化即不发。既有持久分配/保留风险≤64MiB/1024 inode；W独立物理风险≤64MiB并默认相加，故无共享归属证明时carrier/W聚合≤128MiB/1024 inode外加固定kernel objects；首次连接和初始读取已包含 |
| cleanup carrier memfd | bridge payload逻辑/RAM/AS≤1MiB；含folio/THP/metadata/allocator的瞬时物理风险≤2MiB/1 shmem inode；只在verified carrier分配/触达，FD关闭后mapping留至退出。除非准确已批准共享池明示覆盖，否则与carrier/shared风险相加 |
| guest volatile stage | 逻辑≤2MiB/32 inode；完整allowlist为bundle≤8个/总计≤1MiB、`action.journal`一个/固定64KiB、`result.journal`一个/固定752KiB、十二个case intent/context/各固定16KiB，故最大逻辑2,080,768 bytes（2032KiB），最多22个regular/连stage目录23 inode；全部文件在L进入B前create-only并逐页实写确定EMPTY内容，不延长/打洞/新增stage对象。只有已资格base-page=4KiB且bundle文件达到各自上限时，data-page rounding上界才可按2,109,440 bytes计算；仍须以F0/F3的tmpfs folio/THP、metadata/dentry/xattr/allocator/sync完整机制证明总物理风险≤3MiB/48 inode，未知即BLOCKED。清理不明时保留到reboot |
| private raw capture/receipt | 逻辑≤8MiB/256 inode；含parent/metadata/sync/allocator的物理风险≤12MiB/320 inode；raw不进Public |
| Public脱敏记录 | 逻辑≤1MiB/64 inode；物理风险≤2MiB/80 inode |

F0枚举目标runtime支持的全部RLIMIT并固定每项soft/hard。MEMLOCK、MSGQUEUE、NICE、RTPRIO、RTTIME
对L/S/G均为(0,0)；L/S的CORE=(0,0)、FSIZE=(4,4)MiB、STACK=(8,8)MiB。NPROC固定为有限
`N=allowlisted ordinary UID当前总task+3`并设(N,N)。LOCKS/RSS本范围不使用，须等于plan固定pair并
可使用明确登记的infinity sentinel；SIGPENDING由协议主动使用，必须按上文同一real UID当前占用
`Q0`加恰好四个timer reservation和固定四项pending-event margin，设为有限`(Q0+8,Q0+8)`，不得使用
infinity sentinel。任何未知resource、
未登记pair或并发UID task变化均在mutation前BLOCKED。cgroup
`pids.max`仍是本批新task的硬边界，不能用较大的NPROC替代。

F0在首次carrier前必须已有prefix可容纳证明：固定carrier最大输入/输出/进程、认证/提权/sshd、
audit/journal规则、capture父目录和各自物理设备上界。来源不足即`NOT_ISSUED`。F3再用有限live
读取核对实际anchor、capacity和配置；不能先产生未计费记录再决定是否有预算。

每个物理设备按以下规则计算：唯一现存对象的allocated blocks/inodes + 尚未实例化且未释放的
future obligation + 本批次新峰值 + parent/metadata/attr/allocator/sync/audit margin。同一obligation
已实现部分取`max(current, approved future ceiling)`，不重复相加；不同obligation仍相加，除非
既有准确批准明示共享池。同一partial/final inode只计其最大同时峰值，保留失败不退款。hardlink
仅以同`(device,inode)`去重；reflink/sparse无extent证明时不扣减。tmpfs同时核对内存与inode。
无法排除concurrent writers、rotation掩盖、未知carrier或不完整counter时，在首个mutation前
`ACCOUNTING_NOT_PROVEN`。不得删旧证据、关日志或改配置腾预算。

## 结果、发行状态与排除项

新批次单独维护：

- `fixture_delivery_issued`：首次carrier request前false，发出即true；
- `fixture_batch_release_issued`：同连接late-start/clock/费用门通过后、写出任何`BATCH_RELEASE`
  字节前由owner持久置true；短写、断线或回执丢失仍保持true；
- `fixture_batch_release_accepted`：只有L收齐、严格验证完整frame后在RAM置true并先输出有界
  `BATCH_ACCEPTED` receipt；owner只有取得该原frame或后续同一状态链证据才可登记true；另以
  `batch_release_outcome=NOT_SENT|CLEAN_REJECTED|ACCEPTED|UNKNOWN`区分结果；
- `fixture_native_batch_issued`：首个case的`clone3`调用前true；每个case另有
  `clone_issued/exec_go_issued/g_go_issued`，均经FD18的stage journal→owner fsync→ACK链在对应调用或
  写出任何frame字节前持久置true；短写、断线或回执丢失不清零、不重发；
- `fixture_qualification`：`NOT_RUN | BLOCKED_RETAINED | UNKNOWN_RETAINED | FAILED_RETAINED | FIXTURE_LIVE_REFERENCE_MATCHED`。

`batch_release_outcome`初始化为`NOT_SENT`。owner把原`BATCH_ACCEPTED`或能够证明同一RAM accepted
状态的后续链证据append+fsync进固定private capture后，必须在允许任何native-batch动作前持久登记
`fixture_batch_release_accepted=true`和`batch_release_outcome=ACCEPTED`。从`NOT_SENT`写入
`CLEAN_REJECTED`、`ACCEPTED`或`UNKNOWN`中的任一终态后不得回退、互换或由迟到ACK改写；后续运行
失败只改变`fixture_qualification`，不能把已经证明的release acceptance改成`UNKNOWN`。

delivery已发、`fixture_batch_release_issued=false`且从原连接取得L完整`CLEAN_REJECTED` frame、
sealed W mapping与W remote status 0证明L `CLD_EXITED/0`、local client wait 0、双EOF及准确账目时可
写`batch_release_outcome=CLEAN_REJECTED`/`BLOCKED_RETAINED`。release issued=true且同样取得完整clean
rejection/W status/local wait/双EOF/账目时也写`CLEAN_REJECTED`/`BLOCKED_RETAINED`，但issued bits保持true且绝不重发；W是唯一remote status来源，L自报exit或单独EOF
不能替代。release issued=true但无法证明L完整接受或上述clean rejection闭环时必须
`batch_release_outcome=UNKNOWN`和`UNKNOWN_RETAINED`；不得因短写、ACK丢失或观察不到accepted而把
其余位回填false，也不产生第二次请求。
只有N01–N12、每层typed wait/EOF、guardian期零outer byte、全部已用action carrier往返、final carrier export/ACK、private capture中完整唯一的`CLEANUP_FINAL` raw frame/ACK和success receipt、sealed W映射与W remote status 0证明原L为CLD_EXITED/0、原local client正常wait 0、双流真实EOF及capture最终fsync/seal、原stop/空树、最终counter/peak、费用和outer seal完整时才写
`FIXTURE_LIVE_REFERENCE_MATCHED`。kernel D-state、guardian失效或任何不可证明收尾保留
`UNKNOWN_RETAINED`；本文不承诺所有内核故障均在期限内释放。

NS3 original-host terminal collection、NS4 actual consumer integration、P4/20261002a发行或消费、
旧producer、H07/FS资格、产品runtime、Q2 business chain、GX10、S1/生产和E4–E6均排除。
旧字段`field_ready=false`、`allow_run=false`、`consumer_namespace_admitted=false`、
`normal_chain_executions=0`及旧batch/window状态不因本fixture改变。
