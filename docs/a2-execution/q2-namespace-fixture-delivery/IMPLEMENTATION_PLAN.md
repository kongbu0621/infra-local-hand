# Q2 namespace fixture 完整交付：实施计划

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope：`LH-Q2-NAMESPACE-FIXTURE-DELIVERY-v1`；拟关闭 **F0–F4 only**。
- [需求](REQUIREMENTS.md) → [架构](ARCHITECTURE.md) → 本计划；R 与两文档一致。
- 当前没有本范围准确 A commit、Owner B、独立 C、implementation D 或现场发行。

## 治理顺序和旧提案处理

严格顺序为：

1. 三份权威文档及设计复核四文件形成准确 documentation commit **A**；
2. Owner B 绑定 R、A、scope、F0–F4、唯一事实前提、对象/预算和一次发行；
3. 单独 bookkeeping-only commit **C** 记录 `CLOSED at exact R/A/B/scope`，不含源码、测试、
   dependency、配置或现场动作；
4. implementation **D** 必须以C为祖先；
5. 独立验证后冻结D、RAM bootstrap、bundle、runtime/context和私有plan；
6. 只在全部发行门满足时执行一次carrier request和最多一次`BATCH_RELEASE`后的native batch。

B留存必须包含Owner身份、准确决定原文、time或event ID、稳定reference、R、A和scope；可变来源
须保留verifiable copy。C不与D squash；A的三份权威文档和设计复核四文件保持原字节和历史OPEN标签。旧 proposed A
`dfdd653…`、baseline和readiness audit保留，并登记`SUPERSEDED_PROPOSAL_NOT_APPROVED`；这不
追认旧B/C，也不是reopening。

Owner可一次批准准确A的完整conditional implementation、verification、delivery和one batch，
无需逐文件/逐case询问。材料不满足时停止；target/source/premise/property/cap/budget/use的
material change仍按R重开。

## F0：离线plan与pre-carrier费用门

只用已保留私有原件和Public摘要形成唯一plan，不连接guest：

- 固定原Q1 guest、预期boot、历史Q2 ordinary账户/主组/完整groups来源；
- 固定allowlisted `user@UID.service` 的唯一read source/API、字段和调用次数及旧manager/roots/ledger/
  失败实例禁止修改表；禁止其它`systemctl`/D-Bus枚举和所有manager Start/Stop/Cancel/write；
- 固定root-only cgroup anchor来源，明确它不是ordinary delegation；固定cgroup2 mount ID/dev/inode/
  fs magic、anchor domain/空procs/准确四项subtree control、初始dying=0及live descendant基线D0、
  有效depth余量≥2、计入D0后的descendant余量≥4、CPU/mems和“不得修改旧parent controls”的规则；另行固定原carrier leaf的
  mount/dev/inode、domain/空subtree control、freeze/events、effective cpuset/mems、持续存活parent、
  held dirfd、无cleanup/改限竞态，以及最多37个action往返与按实际0或1次final进入各自迁入/迁出前后的完整
  重验；固定旧carrier/new guardian各最多38次、全批最多76次self-write且不写数字PID；
- 固定新B在空procs且`cgroup.controllers`恰含四项时的唯一配置序列：先写/readback `cpuset.cpus/mems`和B cpu/memory/pids limits，
  再唯一写`+cpu +cpuset +memory +pids`并严格读回subtree-control恰四项，随后才建children；固定
  guardian/supervisor/case均为domain leaf、`cgroup.subtree_control`空且cpuset/effective mems准确；
- 固定`env-bash-literal-ssh-v1` wrapper/profile SHA、`shlex.join`远端字符串、remote login
  shell/parser、sudo/env、已存在sealed native watchdog W、runtime绝对对象、RAM bootstrap schema/
  ≤32KiB source/≤48KiB command及准确
  `exec /usr/bin/sudo -n -- /usr/bin/env -i LANG=C LC_ALL=C ABS_WATCHDOG WATCHDOG_ARGS -- ABS_RUNTIME -I -B -c FIXED_LOADER TOKEN`
  round-trip；W必须为SSH顶层远端程序和L的准确parent，stdin保留给L协议，目标没有完全匹配的W即
  `NOT_ISSUED`，不得上传、编译、生成或替换W；固定原owner三钟/outer deadlines、HELLO/
  `BATCH_RELEASE`、双方`adjtimex`/clocksource相对频率误差上界、W-bound L parent关系、原carrier
  leaf身份/返回资格和owner外层stop/EOF；
- 从授权的pre-request固定来源证明`core_pattern`非pipe；离线固定W的absolute path、mount/dev/inode/
  size/uid/mode/不可写祖先、SHA-256/version、source→binary relation、ELF class/machine/PT_INTERP/
  loader/完整`DT_NEEDED`、argv/env/cwd/umask、caps/securebits/seccomp/LSM/affinity/scheduler、无setid/
  file-cap、准确退出映射和完整资源表。W ELF入口至guard-arm是单列的pre-carrier TCB prefix：接受的
  endpoint premise须由sealed source/loader/launcher relation及独立fault/trace资格化固定
  `W_PREFIX_CPU_MAX_NS≤1s`、`W_PREFIX_WALL_MAX_NS≤2s`、单task、userspace AS/RSS及保守物理
  风险≤64MiB、入口installed FD≤8、outer read/write=0和pipe/kernel-object/audit bytes/inodes；全部进入
  首次发行前carrier预算，不能资格化即不发。wall项不得称作已有远端kernel hard wall，且在该prefix
  完成及W唯一clone前没有L、B或fixture mutation；
- 固定host env/PATH/cwd、实际解析的env/bash/ssh、identity与known_hosts对象；known_hosts须已含
  准确host key且本批不采用新key；launch env删除`SSH_AUTH_SOCK/SSH_AGENT_PID`，只使用固定
  identity file，相关read/metadata/audit费用进入pre-carrier prefix；
- 固定并证明no PTY、wrapper不读stdin/不重定向、SSH stdin二进制透明且stdout/stderr分离；固定
  sshd/account/authorized_keys/ssh rc/shell startup环境没有ForceCommand、BASH_ENV/ENV、pre-command
  hook或sudo use_pty/I/O plugin/lecture/password对协议stdio/argv/env的消费、注入、重定向、合并、
  替换或额外协议字节；预算内认证、audit/journal/session metadata仍允许并单列；
- 固定W的native状态机和ABI：入口先取absolute process CPU累计样本；按
  `parent_before=getppid()`→set/readback `PDEATHSIG(SIGKILL)`→`parent_after=getppid()`执行，要求两次
  parent相同、非1且满足manifest固定proc-identity规则。完整signal mask先归一为空，全部catchable
  disposition归一为manifest初态，其中SIGXCPU=`SIG_IGN`、SIGCHLD/SIGUSR1/HUP/TERM/INT/QUIT/
  `DEADLINE_SIGNAL`=`SIG_DFL`且SIGCHLD清除`SA_NOCLDWAIT/SA_NOCLDSTOP`；逐项readback后才block并
  readback准确`W_BLOCKED_SET={SIGCHLD,SIGUSR1,SIGHUP,SIGTERM,SIGINT,SIGQUIT,DEADLINE_SIGNAL}`，
  signalfd只接收该set。核fd0/1/2真实类型/
  flags，`close_range(3,UINT_MAX,0)`后确认恰stdio；设置/readback W
  CPU `(8,9)s`、AS/DATA `(64,64)MiB`、NOFILE `(8,8)`、CORE/FSIZE `(0,0)`、STACK `(8,8)MiB`
  及固定零limits；依次创建CLOEXEC signalfd=3、取得W0、创建并
  absolute arm/readback CLOEXEC BOOTTIME timerfd=4。固定
  `W_REMOTE_EXIT_DEADLINE=W0+830s`，分别固定有限`W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS`、
  `W_KILL_TO_REAP_MARGIN_NS`、`W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`且三项和≤12s；定义
  `W_KILL_DEADLINE=W_REMOTE_EXIT_DEADLINE-W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS-W_KILL_TO_REAP_MARGIN_NS-W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`
  和`W_REAP_DEADLINE=W_REMOTE_EXIT_DEADLINE-W_REAP_TO_REMOTE_STATUS_EOF_MARGIN_NS`，timerfd只arm到
  W_KILL_DEADLINE。F0/F2分别资格化timer readable→W scheduled/pidfd kill、kill→typed wait/reap、
  reap→W `_exit`/SSH status/EOF的最坏界；timerfd本身不杀进程，同一费用只扣一次；
- 固定W唯一`clone3`使用88-byte全零初始化`struct clone_args`：flags仅`CLONE_PIDFD`、
  `exit_signal=SIGCHLD`、pidfd为有效对齐输出地址，child_tid/parent_tid/stack/stack_size/tls/set_tid/
  set_tid_size/cgroup全0，无fork或数字PID fallback。
  child继承fd0–4、SIGXCPU ignore和CPU `(8,9)s`，native首段核PPID、设/readback
  `PDEATHSIG(SIGKILL)`、再核PPID，两次均须为W，然后自停SIGSTOP；W以signalfd/timerfd/pidfd的单线程
  `ppoll`和`waitid(P_PIDFD,...,WSTOPPED|WNOHANG)`消费且核唯一`CLD_STOPPED/SIGSTOP`、未exit及
  PPID/starttime，timer同时ready时deadline优先。只在同次clone的numeric PID、live pidfd及已消费的
  stopped event共同成立时，W以固定`prlimit64`表复核CPU并设置/readback child
  AS/DATA `(64,192)MiB`、NOFILE `(32,64)`、CORE0、FSIZE4MiB、STACK8MiB、NPROC和全部其余pair；
  W关闭自己的fd0–2、保持outer零read/zero write，再唯一pidfd SIGCONT；child关闭继承fd3/4，建立并
  readback固定L入口signal状态（mask恰为`W_BLOCKED_SET`、SIGXCPU=`SIG_IGN`、其余catchable=
  `SIG_DFL`），核恰0–2后才
  exec runtime；
- 固定W的deadline/grace/reap/status状态机：child放行前任一stop source、deadline或完整性错误直接只向
  held pidfd发SIGKILL；放行后signalfd收到SIGUSR1/HUP/TERM/INT/QUIT/`DEADLINE_SIGNAL`时至多一次
  转发SIGUSR1，固定grace后仍存活才
  SIGKILL，deadline/内部错误不走grace。SIGCONT后终态只用
  `waitid(P_PIDFD,...,WEXITED|WNOHANG)`，不混入旧stop/continued event；deadline与exit同时ready时
  deadline优先。kill须不晚于
  `W_KILL_DEADLINE+W_WAKE_TO_PIDFD_KILL_OVERSHOOT_NS`，typed wait/reap须不晚于W_REAP_DEADLINE，
  W `_exit`/SSH status/EOF须不晚于W_REMOTE_EXIT_DEADLINE。只有准确child `CLD_EXITED/0`、从未触发
  deadline/stop/error、W最终absolute process CPU累计≤1s且早于W期限才`_exit(0)`；其它状态按manifest作非零
  粗粒度映射，不伪造raw wait status。owner所见remote status是W status；sealed W语义加status 0才
  证明原L status 0。L关闭流后允许双EOF先到，owner仍须取得随后W status；W被kill、reap超时或W/L
  D-state只能`UNKNOWN_RETAINED`；
- 固定runtime/import closure、core配置允许值、已资格且全程held的`/run` parent dirfd、≤8个bundle
  名称、固定64KiB `action.journal`、固定752KiB `result.journal`准确offset/slot布局和十二个固定16KiB
  预分配case intent/context的完整stage manifest；固定最大逻辑2,080,768 bytes、22 regular/连目录23
  inode及tmpfs folio/THP/metadata物理资格；固定同一bridge的clone/setup/arm/non-returning tail API、
  `memfd_create` executable/sealing flags、copy/page-touch/digest/seal/load路线及payload逻辑/RAM/AS≤1MiB、
  含folio/THP/metadata/allocator的瞬时物理风险≤2MiB/1 shmem inode上界；除非准确共享池明示覆盖，
  该义务与carrier/shared风险相加；
- 固定private capture的create/fsync/ACK责任、最多37项pre-action commit链、每项≤2s的carrier往返、
  guardian期fd1/fd2零write、final carrier进入/result freeze/752KiB双流导出/ACK，以及≤16KiB
  `CLEANUP_SOURCE`/canonical H schema、cleanup 0–11 FD表、sealed `CP_MAX_NS` preparse guard和唯一exec
  合同；H绑定bridge/memfd预期，cleanup-final保存copy/seal/load实际记录；final marker后的唯一ACK≤5s，
  H/ACK不得写回result journal；
- 枚举并固定目标支持的全部RLIMIT pair：W在clone前先设置/readback自身CPU `(8,9)s`及上述最小
  native profile，使L从出生即有hard-9s CPU guard；W在stopped/live-pidfd window只readback该CPU pair，
  并在runtime前把L非CPU profile设置/readback为AS/DATA `(64,192)MiB`、NOFILE `(32,64)`、CORE0、
  FSIZE4MiB、STACK8MiB及其余准确pair。L首码继承并核`W_BLOCKED_SET`与SIGXCPU ignore；fatal timer
  active/readback、紧邻CPU复测通过并固定G0后，才block SIGXCPU、恢复`SIG_DFL`，创建/readback接收
  `W_BLOCKED_SET+SIGXCPU`的signalfd并先drain/核pending。无stop/XCPU时才凭已资格
  CAP_SYS_RESOURCE把CPU提高/readback为供S继承的`(20,100)s`，raise后立即再drain/核pending；任何
  pending stop永久关闭success。L先保留S所需hard，S只提高soft；S clone返回且child仍在native gate时，
  L必须在等待READY/放行前立即把自身CPU/AS/DATA/NOFILE收紧为
  (19,20)s/(64,64)MiB/(64,64)MiB/(32,32)，失败则kill准确S并stop；G按需求降到固定pair；
  NPROC=`allowlisted UID current tasks+3`；LOCKS/RSS为未使用的固定pair，可明示infinity sentinel；
  SIGPENDING不得用infinity：固定同一real UID在任何timer前的`SigQ`占用`Q0`、
  `SIGPENDING_TIMER_RESERVATIONS=4`和`SIGPENDING_EVENT_MARGIN=4`，L pair恰为有限
  `(Q0+8,Q0+8)`。仅允许initial与cleanup-continuation两个timer generation；每代唯一process-CPU
  fatal与BOOTTIME/MONOTONIC/REALTIME三wall timer按固定1–4 call site顺序create、逐次arm/disarm
  readback并核`SigQ=Q0+1…Q0+4`，同时live≤4。完整success路径共8次create；失败只停在固定序列
  前缀且全程≤8次，额外/第9次create在syscall前拒绝。初始两个双钟timer先arm到
  G0+48s，REALTIME在DECLARE验证前保持disarmed，之后三者才按原期限/UTC cutoff rearm；
  cleanup exec前耗尽signalfd并确认全部blocked stop/deadline pending为空；continuation在P0/FD4
  `Threads=1`门后才按preparse公式重建fatal timer、耗尽继承signalfd并核全部blocked stop/deadline pending为空及
  `SigQ=Q0+1`，再重建三个wall timer。未知limit或静态timer资格缺失、initial首mutation前的Q0/UID
  task漂移/创建失败即BLOCKED/CLEAN_REJECTED；accepted或已mutation后的运行故障及cleanup generation
  故障只能UNKNOWN_RETAINED并有限收尾；
- 固定initial entry首个process sample后立即核W parent/PDEATH/profile、继承`W_BLOCKED_SET`和SIGXCPU
  ignore，再从同一held procfs核`Threads=1`，之后才读Q0/改限/建timer；
  cleanup continuation则在P0和只读`getitimer(ITIMER_PROF)`/SIGPROF状态核验后、任何timer create或
  signal mutation前从继承FD4核`Threads=1`。两次读取分别计入initial/preparse gap，失败不得继续create；
- 固定L同一`CLOCK_PROCESS_CPUTIME_ID`的`CPU_SAMPLE_ROUND_NS`、verified-membership样本全序和归属；
  明确域间隔加rounding计本域，migration歧义间隔加rounding向guardian/carrier双计，禁止
  `process−guardian cpu.stat`推算。固定全部可进入/失败segment的两域/process CPU envelope、
  `STOP_CPU_MAX_NS[GUARDIAN,CARRIER,PROCESS]`、`FATAL_DELIVERY_OVERSHOOT_NS`、
  `RLIMIT_CPU_KILL_OVERSHOOT_NS`、`EXEC_GUARD_DELIVERY_OVERSHOOT_NS`及
  `initial_exec_gap_cpu_ns/initial_exec_gap_wall_ns`、
  `cleanup_exec_gap_cpu_ns/cleanup_exec_gap_wall_ns`和sealed
  `CLEANUP_PREPARSE_CPU_MAX_NS=CP_MAX_NS`，满足
  initial固定`INITIAL_CPU_SOFT_S=8`、`INITIAL_CPU_HARD_S=9`，目标须证明
  `0≤RLIMIT_CPU_KILL_OVERSHOOT_NS≤1s`且`9s+RLIMIT_CPU_KILL_OVERSHOOT_NS≤10s`；cleanup须满足
  `0<EXEC_GUARD_DELIVERY_OVERSHOOT_NS<CP_MAX_NS<cleanup_exec_gap_cpu_ns`，POSIX fatal另满足
  `0<FATAL_DELIVERY_OVERSHOOT_NS<CP_MAX_NS`；source/fault须证明P0到H验真后
  full-ledger首次rearm的正常最坏CPU严格小于`CP_MAX_NS-overshoot`。每段进入前保留两域≤10s/
  process≤20s stop界，
  success路径还保留全部剩余段与tail后的9s/9s/18s界。fatal timer以unblocked `SIG_DFL` SIGALRM
  fail closed：每段进入/verified membership边界以`Pnow`对适用segment envelope、
  `limit-accum-STOP_CPU_MAX_NS`及success的`limit-accum-remaining_after-tail`取最小候选，再扣
  `FATAL_DELIVERY_OVERSHOOT_NS`后absolute rearm/readback；迁移段同时取两域，非正余量或正常最坏CPU
  不能严格早于expiry即BLOCKED。signal wait为UNKNOWN；
- 固定cleanup跨exec双CPU guard：exec前确认旧`ITIMER_PROF`为零/SIGPROF无pending并将SIGPROF设为
  unblocked/`SIG_DFL`；按carrier/process最早physical候选（含从expiry到terminal exit的完整
  `EXEC_GUARD_DELIVERY_OVERSHOOT_NS`）和success剩余段/TC候选取最早值，资格化`ITIMER_PROF`
  resolution、timeval微秒表示、向下量化、最小非零值及readback误差，唯一arm/readback且不得把expiry
  推迟；以唯一`setitimer(ITIMER_PROF)`设置/readback相对CPU guard。再按当前absolute process CPU
  保守向下取整数`CLEANUP_RLIMIT_HARD_S`，使
  `HARD_S*1s+RLIMIT_CPU_KILL_OVERSHOOT_NS`不晚于最早physical候选，soft=`min(19,HARD_S)`，以
  CAP_SYS_RESOURCE原子set/readback；无正余量、无可用整数或任一set/readback失败均不得exec；
- H只保存handoff样本、两guard候选/requested/actual、临时RLIMIT pair/readback及W remaining，不预言
  P0 remaining/restore/disarm。continuation首码严格按P0→`getitimer(ITIMER_PROF)`仍armed/nonzero且
  SIGPROF DFL+unblocked→FD4 `Threads=1`→临时RLIMIT/PDEATHSIG/W parent readback；随后才以sealed
  最小公式重建cleanup-generation fatal timer、strict parse H、P1/full-ledger rearm。仅在后者已生效且
  早于ITIMER expiry时恢复/readbackRLIMIT `(19,20)s`，再disarm/readback ITIMER并核SIGPROF无pending，
  然后重建三wall timer并取P2；P0 remaining和全部postexec actual只进`CLEANUP_FINAL`；
- cleanup exec会删除旧generation四个POSIX `timer_create`对象并释放其四项SigQ reservation，但不删除
  已arm/readback的`ITIMER_PROF`或临时RLIMIT_CPU；ITIMER_PROF不属于两代四项POSIX timer且不消耗Q0
  reservation。sealed runtime/loader须证明continuation首个user-code前不篡改ITIMER/SIGPROF/RLIMIT或
  W/PDEATH关系；
- 固定guest outer及全部internal protocol FD、owner侧local client stdin/stdout/stderr真实类型、
  `O_NONBLOCK` set/readback、单线程poll状态机及frame/chunk/buffer表。owner固定三pipe、client pidfd/
  wait、三个absolute nonblocking timerfd与capture临时FD的峰值和费用；owner在启动client前按固定
  顺序create、absolute arm并readback三timerfd，失败不得启动。运行中并行drain双流、每流独立
  offset/counter/digest且durable append+fsync后才ACK。三个guest wall timer共用blocked realtime
  `DEADLINE_SIGNAL`，其BOOTTIME与
  MONOTONIC expiry取原absolute界和保守映射UTC cutoff的较早者，REALTIME expiry取UTC not-after；
  每次wake/EINTR/partial重采三钟。partial read及manifest允许chunk/remainder的大frame write只推进
  同一logical frame remainder，错误/stop/deadline后锁UNKNOWN且不从头重发；action/marker/ACK/
  BEGIN等atomic小帧写前零字节EAGAIN可回poll，raw write partial即UNKNOWN；result和
  `CLEANUP_FINAL`使用≤4KiB固定chunk，最终receipt只做一次≤512-byte raw nonblocking write且
  EAGAIN也失败；
- 固定每case唯一`CASE_T0`及`+20/+25/+30/+40s`绝对边界：首例四项、后续三项excursion连同
  intent/leaf/clone/drop/exec/bootstrap/N09/observe都在共享前20s；20→25只stop，25→30只
  exit/EOF/report，30→40只reclaim/final/remove。每个case和pre-action门须保留本例至+40的余量
  加完整110s；F0须以首例四次近2s excursion的最长路径证明前20s和最后10s收尾可行，否则BLOCKED；
- 固定continuation启动即预分配≤32KiB canonical `CLEANUP_FINAL` buffer及≤512-byte
  `SUCCESS_RECEIPT`模板。H只绑定cleanup-final schema/对象/ceiling；continuation把H、启动/FD验证、
  carrier-owned memfd copy/seal/load/setup、stage删除、guardian/B完整final、reclaim/remove/close/dying、anchor复原及CPU/timer实值写入唯一
  cleanup-final logical frame，owner append+fsync后回唯一≤256-byte ACK，exchange≤5s。最后20s中
  cleanup-final/ACK≤5s，tail/remote exit/双EOF/final capture seal≤15s；F0固定
  `0<TAIL_CPU_MAX_NS=TC_MAX_NS<1s`与`0<TAIL_WALL_MAX_NS=TW_MAX_NS≤1s`，并资格化bridge setup/arm/
  non-returning native tail：最终process/BOOTTIME/MONOTONIC/REALTIME sample与gate、无分配无loop的
  fixed-width填充/digest、SIGPIPE在write返回前保持ignore、一次atomic raw write、close与`_exit`最坏
  CPU/wall界；
- 建立每个物理设备的old actual、unreleased future、新peak、metadata/allocator/sync margin账表，
  明确hardlink/reflink/sparse及partial/final去重规则；
- 在资源表单列W和原carrier聚合：W在L存活期新增1 task，原carrier须可同时容纳既有parent/W/L；W
  从进程出生累计的完整失败CPU风险≤10s，其中pre-arm另证`W_PREFIX_CPU_MAX_NS≤1s`，status0绑定最终
  absolute process CPU≤1s；L carrier≤10s另账，W+L aggregate新增CPU风险≤20s；认证/提权/audit/
  journal envelope≤10s，故admitted
  attributable CPU≤30s且W prefix不重复相加。W guard前userspace AS/RSS及保守物理风险≤64MiB、入口
  installed FD≤8；guard后AS/DATA hard64MiB、STACK8MiB，image/file-backed/shared/kernel-object仍闭合在
  同一64MiB风险内；既有carrier持久分配/保留上界为64MiB/1024 inode，W独立物理风险默认再加
  64MiB；没有准确共享证明时二者聚合上界为128MiB/1024 inode另加fixed kernel objects，只有准确
  extent/page归属才去重。entry至
  close_range峰值≤8；guard后的pre-clone installed FD=5，pidfd后基础6、串行身份/proc临时FD使峰值≤7；
  child stopped时继承5，恢复后关3/4；W关0–2后steady=3。另列聚合references、signalfd/timerfd/pidfd
  slab、pipe页、认证/session/audit/journal bytes/inodes及cleanup memfd≤2MiB/1 shmem inode；W不建文件/
  网络连接且outer read/write=0；W0后cap≤830s，三项margin和≤12s，guard前
  `W_PREFIX_WALL_MAX_NS≤2s`仅是accepted endpoint下的admission envelope；
- 在发出carrier前证明认证/提权/sshd/bootstrap/初始audit/capture前缀可容纳；
- 初始化`fixture_delivery_issued=false`、`fixture_batch_release_issued=false`、
  `fixture_batch_release_accepted=false`、`batch_release_outcome=NOT_SENT`、
  `fixture_native_batch_issued=false`、所有case三枚issued位=false和qualification=`NOT_RUN`。

plan同时固定outcome单调状态机：owner把原`BATCH_ACCEPTED`或证明同一RAM accepted状态的后续链证据
append+fsync进固定private capture后，须在允许任何native-batch动作前持久登记
`fixture_batch_release_accepted=true`和`batch_release_outcome=ACCEPTED`；完整clean-rejection闭环登记
`CLEAN_REJECTED`；既不能证明accepted也不能证明clean rejection的已发动作登记`UNKNOWN`。
`NOT_SENT`进入任一终态后不得回退、互换或由迟到ACK改写；release后的运行失败只更新
`fixture_qualification`。

plan字段只能实例化A已授权的source role、枚举和ceiling，不能新增路径探测或把空字段交给现场
补值。F0不声称当前boot、account、anchor、runtime、capacity或audit仍相符；这些事实在唯一F3
请求的只读阶段核对。离线原件或prefix费用不足即不发行。

## F1：独立source与synthetic验证

只在C后新增test-only路径，不改`tools/local_hand_jobs/runner.py`、产品broker/consumer、K reader、
旧supervisor、冻结wheel或配置。候选组件：

| 组件 | 责任 | 禁止依赖 |
| --- | --- | --- |
| `tests/e3_host/q2_namespace_reference.py` | exec后G entry、R/O、native ABI、15帧协议和有限报告 | 不导入产品runner/broker，不接受自由PID/path/command |
| `tests/e3_host/q2_namespace_fixture.py` | root S、fresh leaf、clone3、身份drop、pause、收件、stop/final counters | 不运行Q2 business，不改旧manager/roots/ledger |
| `tools/q2_namespace_delivery.py` | RAM bootstrap/guardian L、plan/bundle、HELLO/`BATCH_RELEASE`、action journal→carrier往返→owner fsync/ACK、固定result journal、guardian零outer write、final carrier export/ACK、cleanup handoff/continuation和outer receipt | 不含guest默认值，不自行重发，不把bundle或tmpfs journal存在解释为发行 |
| `tests/e3_host/q2_namespace_clone_bridge.c`及封存CPython扩展 | native `clone3`/fork hooks/child-only setup，以及cleanup setup/arm/non-returning tail；支持continuation从carrier-owned sealed executable memfd重载同一artifact | guest不编译；child绝不返回Python；tail不返回Python；不提供PID迁移fallback |
| 四个对应test模块 | strict parser/state/property/cost/fault回归和显式native capability结果 | mocked/synthetic PASS不冒充guest native qualification |

W不是本范围新实现或bundle member。F1只为plan verifier、owner状态机和fault harness增加对该既有sealed
native对象的准确manifest/ABI/资源/status contract验证；任何测试替身只可验证拒绝和协议状态机，不能
代替W原字节、source→binary relation或目标上的live资格。

Python部分只用固定stdlib/import closure；`clone3`只由封存CPython native bridge执行。bridge固定
编译器/flags、CPython runtime/headers/ABI、glibc/kernel ABI和artifact source relation，从主线程
持GIL调用，并围绕syscall执行`PyOS_BeforeFork`、parent success/failure的
`PyOS_AfterFork_Parent`和child的`PyOS_AfterFork_Child`。准确x86_64 LP64 `struct clone_args`大小
88 bytes；flags只有`CLONE_INTO_CGROUP|CLONE_PIDFD`，`exit_signal=SIGCHLD`，pidfd为有效对齐输出
地址、cgroup为held leaf FD，七个其余字段为零。child在native内完成全部设置和`execve`/`_exit`，
绝不返回Python。缺符号/ABI/hooks即BLOCKED；不提供guest compiler、数字PID迁移、自迁移或syscall
number fallback。`close_range`必须真正关闭3以上全部FD。

bridge build须在两个干净隔离build中产生byte-identical `.so`（禁用非确定build-id），manifest
固定C source、compiler/flags、CPython SOABI、ELF class/machine、允许`DT_NEEDED`/loader和clone/
setup/arm/tail完整导出符号及native receipt/digest/signal/write/close/exit合同。
L与exec后的S分别从held stage dirfd `openat`固定basename、验fstat/digest/ELF/ABI，再经已资格
`/proc/self/fd/N`用`ctypes.PyDLL`/NOW/LOCAL加载并关闭临时FD；不假定mapping跨exec继承，也不按
路径重开stage。cleanup continuation必须在verified carrier把stage bridge字节复制到固定flags的新
memfd，逐页触达/复读digest、施加并readback四个seal，关原artifact后只从memfd复核/load并关memfd；
mapping留至`_exit`。准确import closure须证明无`os.register_at_fork` callback，启动期guard拒绝后续
注册；否则native child“无Python回调”不成立并BLOCKED。

实施顺序：

1. W静态manifest/verifier、准确remote command、W0/830s timer、pidfd child-stop/prlimit/release、
   signal/grace/kill/reap/status mapping和W/L parent snapshot；owner状态机须允许双EOF先于W status，且仅
   sealed W映射+W status0证明原L `CLD_EXITED/0`；
2. strict plan/context/report/frame parsers、counter、三钟状态机、一次发行位、最多37项pre-action
   hash-chain、carrier往返/fsync/ACK、38个excursion slot和结果枚举；同时实现同一process-clock样本
   ledger、segment/stop/overshoot catalog、两个exec gap、CP_MAX preparse guard、
   `CASE_T0+20/25/30/40s`状态机和固定TC/TW tail envelope；
3. RAM bootstrap的pre-`BATCH_RELEASE` read-only gate、完整RLIMIT/signalfd/PDEATHSIG、HELLO和outer
   framing；实现两generation各四call-site/总create≤8的固定create/rebuild顺序、SigQ `Q0+8`账、三个absolute wall timer，
   cleanup跨exec `ITIMER_PROF`+临时RLIMIT backstop，以及全部protocol FD的`O_NONBLOCK`/`ppoll`/
   partial-frame状态机；
4. fd级cgroup2 anchor/B/leaf资格、controls、initial/final counter、cgroup.kill、bounded
   `memory.reclaim`/current=0和物理账法；
5. native bridge、L guardian、S subreaper、clone3+pidfd、ARMED、`EXEC_GO`、credential/cap/drop/core、
   唯一exec、carrier-owned sealed memfd reload及non-returning native tail；
6. procfs/mount/nsfs、status、pidfd、G/R/O fork关闭表和15帧nonce/FD交换；
7. pause、cooperative/emergency stop、typed wait、三层EOF、guardian零outer write、final carrier
   result export/双stream marker→owner fsync/ACK、固定cleanup 0–11 FD handoff、唯一exec、
   bridge copy/seal/load/setup及stage→guardian→B收尾；随后形成唯一`CLEANUP_FINAL`/durable ACK，
   以arm+non-returning native入口执行固定≤512-byte
   `SUCCESS_RECEIPT` post-gate tail、remote wait/双EOF及owner capture seal；
8. final seal、W status/CPU/timer/I/O证据与Public摘要。

synthetic/fault矩阵至少覆盖：

- plan自由字段、旧A/新A混淆、late UTC、boot变化、clock skew/逆转、HELLO后相对频率误差扩大当前
  offset区间、unsynchronized/step、未来760s漂移、`BATCH_RELEASE`重放和EOF；
- action journal partial fixed-slot write、迁出前journal FD未关、carrier/guardian资格或membership错、
  self-migration失败、outer partial write、owner capture partial append/fsync失败、ACK丢失/重复/错counter/
  digest/head、迁回失败、excursion slot未封口或动作早于成功迁回，以及37项/单项2s/全批76次
  self-write上界；上述故障不得执行或重发对应动作，留在carrier的terminal路径不得再做final迁移write；
- wrapper/shell/sshd rc或ForceCommand、BASH_ENV/ENV、PTY、sudo use_pty/I/O plugin、banner/额外字节、
  stdin消费与stdout/stderr合并；
- W缺失/字节或祖先身份漂移、ELF/loader/`DT_NEEDED`/source relation/caps/securebits/seccomp/LSM/
  scheduler/affinity/profile不符、pre-request `core_pattern`为pipe、现场上传/生成W尝试、W pre-arm prefix
  超`W_PREFIX_CPU_MAX_NS≤1s`/`W_PREFIX_WALL_MAX_NS≤2s`/单task/64MiB/入口8FD/zero-I/O/audit
  envelope，及W guard前出现L/B/mutation；这些均须在request前
  `NOT_ISSUED`，已发后发现则保留consumed并准确BLOCKED/UNKNOWN；
- W入口process CPU sample、parent-before/PDEATH readback/parent-after或非1/同一identity门错，signal mask/
  catchable dispositions归一化或SIGCHLD flags错；fd0–2身份/flags错、close_range后不恰为stdio、RLIMIT
  `(8,9)`或最小profile set/readback错、SIGXCPU非ignore、signalfd/timerfd/pidfd编号/flags/峰值错、W0/
  absolute arm/readback错，wake→kill/kill→reap/reap→status+EOF三项margin或≤12s总和
  不闭合、额外task/thread/FD/network/file/outer read/write；原carrier不能同时容纳parent/W/L或W资源与
  carrier/shared错误去重均须fail closed；
- W clone3 flags/exit_signal/零字段错，child未准确继承0–4、PPID/PDEATHSIG/SIGSTOP次序错，未用
  signalfd+`waitid(P_PIDFD,...WSTOPPED|WNOHANG)`消费唯一`CLD_STOPPED/SIGSTOP`，或在非同次numeric
  PID/live pidfd/已消费stopped event内prlimit；覆盖child完整RLIMIT readback、W关闭0–2、child关闭3/4
  并建立准确`W_BLOCKED_SET` mask/SIGXCPU ignore/其余catchable default后exec、唯一SIGCONT以及PID reuse；
- W deadline/grace/internal-error/同时ready路径只kill held pidfd；SIGUSR1/HUP/TERM/INT/QUIT/
  `DEADLINE_SIGNAL`至多一次转发SIGUSR1，
  child放行前stop source与deadline/内部错误不走grace，SIGCONT后只以`WEXITED|WNOHANG`收终态；deadline
  同时ready优先、三段margin到界、D-state、W被kill、child signal/nonzero、W status映射、L双EOF先于W
  status都要覆盖。只有W从未触发deadline/stop/error、准确child `CLD_EXITED/0`且W最终absolute process
  CPU≤1s可映射0；其余不得接受；
- anchor为ordinary delegate、有其它writer、旧parent controller缺失、初始dying非零、depth<2、
  计入live基线D0后slots<4或结束时未复原D0/dying=0、
  B非空即配置、B cpuset/limits write或readback错、未唯一写`+cpu +cpuset +memory +pids`、subtree-control
  缺项/多项、写旧anchor，或leaf非domain/subtree-control非空/effective cpuset-mems错、
  原carrier leaf每次进入前后身份/controls/freeze/events/cpuset/mems/parent漂移、guardian返回门漂移、
  B/leaf预存在、初始counter非零；
- clone3 ENOSYS/EINVAL/EPERM、88-byte/字段/hooks/at-fork callback错误、bridge ELF/SOABI/dependency/
  双build/dlopen/exports错误；carrier memfd flags/exec policy不支持、create/truncate/copy/page-touch/
  复读digest/seal/readback/procfd load任一步失败或extra FD、stage inode被直接load、copy超过1MiB、
  mapping未保留到exit，及错误cgroup fd、PID reuse、parent死、
  ARMED丢失、`EXEC_GO`/`G_GO`短读；
- L initial sample后、任何timer/signal操作前或continuation P0后从FD4核得`Threads!=1`，以及首次迁移/
  每个action迁出迁回/需要final迁出时/clone前或S在entry/每次clone前`Threads!=1`，NPROC基线漂移，
  以及S clone返回后L未在等待READY/放行前完成四组limit收紧/readback、失败后未kill准确S，或首个case
  早于该门；
- L入口signal race、W-bound PDEATHSIG、SIGUSR1/HUP/TERM/INT/QUIT/XCPU signalfd、SIGCHLD wait、
  SIGPIPE/EPIPE、outer最早deadline前10s只关闭stdin写端且保留双读端、原deadline只kill本地client
  process group；本地kill不能证明远端停止，远端最终backstop只由W held pidfd/BOOTTIME deadline证明；
- process CPU在18/19/20s边界、pre-action或final段内跨19s、SIGXCPU已观察/pending/未耗尽却继续、
  guardian或carrier成功CPU>9s、process成功CPU>18s以及19→20s区间写success；同一process-clock
  membership样本归属、migration歧义+rounding双计、guardian cpu.stat不得反推、cleanup首样本只能
  追加一次、每段/边界未按segment/physical-stop/success-remaining-tail最早候选rearm、迁移未取两域、
  envelope≤fatal overshoot、arm/readback错及stop reserve不足均须fail closed；
- initial路径须覆盖L从出生继承CPU hard9/SIGXCPU ignore/`W_BLOCKED_SET`、W在loader/首码窗口转发
  SIGUSR1只形成pending、首码验证W parent/PDEATH/profile/mask、fatal arm/readback+紧邻复测→G0→
  block SIGXCPU/改DFL→create/readback signalfd(`W_BLOCKED_SET+SIGXCPU`)→首次drain/pending→raise
  `(20,100)`→再次drain/pending的准确顺序，以及任一pending stop/XCPU继续success、8/9/10s界、
  CAP_SYS_RESOURCE raise失败或raise前放松guard；cleanup路径须
  覆盖旧ITIMER非零/SIGPROF pending、ITIMER_PROF resolution/timeval向下量化/最小值/readback误差、
  临时RLIMIT整数候选不足或set/readback失败、exec改变/丢失任一guard、P0 remaining为零或SIGPROF状态错、
  旧四个POSIX timer未随exec删除/其reservation未释放、把ITIMER误计入SigQ、full-ledger guard前提前
  restore/disarm、restore/disarm/pending验证失败；
- initial/cleanup exec gap在sample、Threads、Q0/limit、fatal arm、deadline pending drain、三个wall
  timer重建或相邻复测任一点超CPU/wall界；cleanup P0/CP_MAX/preparse expiry非法、H parse/hash stall或
  错误、P1不早于preparse expiry、未在CP_MAX内按full ledger首次rearm、P2增量重复/遗漏均fail closed；
  两代timer_create第1–8固定call site分别覆盖quota exhaustion、SigQ不等Q0+n、旧wall event跨exec
  pending及非协议占用漂移；initial generation故障不得进入首mutation，cleanup generation故障锁
  UNKNOWN且不得进入后续success-producing步骤，只可有限收尾。失败后越过固定序列前缀、第五个同时
  live或第九/额外create的源码路径须在F2/首mutation前拒绝；初始DECLARE前只准
  BOOTTIME/MONOTONIC保护G0+48s，REALTIME不得以未知UTC武装；两个exec wall gap只作admission/success
  界，zero-CPU stall最终由W deadline收口，测试不得把owner local kill冒充远端stop；
- outer与internal FD类型或`O_NONBLOCK`错、pipe满/停读、partial/EAGAIN/EINTR、signal、suspend、
  realtime前后step、wall timer到期；owner须在stdin partial同时并行drain stdout/stderr并观察client
  pidfd/三个timerfd，覆盖client启动前timerfd create/absolute arm/readback失败、一流反压而另一流有数据、client先/迟退出、REALTIME timerfd cancel及未在
  durable append+fsync后才ACK；任一路都不得刷新deadline或从frame头重发；
- bounding drop/setgroups/setresgid/setresuid/capset/NNP/PDEATHSIG/dumpable顺序和任一失败；
- piped core_pattern、setuid/file-cap runtime、额外FD/thread/exec、wrong membership或cgroup attach；
- status缺失/重复/多级/非整数、错误proc mount/magiclink/nsfs/type、child提前exit/reap；
- wrong SCM credential/FD数、TRUNC/CTRUNC、role交换、relay不同对象、nonce replay/乱序；
- L基础13/持S后steady18/current-case20/installed峰22/含queue24，S clone峰18/steady14/临时16，
  G22/R13/O13（fd0在IPC前已关闭）及15帧每个edge的installed/queued FD峰值与close；N09两pidfd须单帧、与临时open互斥
  并在resume后关闭，不得隐式增加ACK或第16帧；
- Start类历史故障不会出现：源码不得调用systemd-run/StartTransientUnit或复用产品property map；
- N09中S崩溃、stopped G/R/O、L emergency cgroup.kill、subreaper wait缺失和guardian失效UNKNOWN；
- empty前counter、leaf提前消失、peak缺失/reset、case/S/guardian/B任一完整final字段缺失、remove后
  last held FD或parent dying未归零、CPU rate正确但usage超5s、memory charge外部化；每轮
  `memory.current`/reclaim请求/errno/复读、EAGAIN后归零、四轮后仍非零都须覆盖；
- stage/runtime预热后refault到B、S/旧L mapping未释放、cleanup exec失败/重复、H/source摘要或原期限/
  FD0–11/parent/PDEATHSIG/signalfd/leaf/RLIMIT错；carrier memfd copy的charge/AS/physical/CPU/wall未计、
  setup/arm注册摘要错、tail mapping或fixed buffer提前释放，以及guardian/B current或dying不归零；H最大37项/
  22 stage entry并含CPU样本/账、两个exec gap、Q0/四timer/deadline/O_NONBLOCK和cleanup-final schema的
  canonical encoding必须≤16KiB且不得内联slot/capture；
- guardian membership期间任一正常/stop/异常/traceback/diagnostic路径对fd1/fd2的write syscall或byte、
  允许outer frame缺carrier membership、result 752KiB布局/offset/EMPTY错、case metadata>8KiB、slot
  partial/overflow/扩展、final slot自含result digest/H/ACK，或freeze后再写；这些路径只能UNKNOWN；
- final carrier资格/0或1次迁移分流、`FINAL_CARRIER_READY`、result全文件digest、752KiB双流导出、
  large chunk未在deadline内按remainder补齐、两marker/ACK的atomic partial、owner capture fsync/ACK的
  缺失/乱序、EPIPE/错counter/digest/head、marker后5s超时，
  以及fd1/fd2仍开时guardian current不归零；不得重发export/marker/ACK，也不得依赖pipe drain；
- `CLEANUP_FINAL`最大H与完整raw final/control输入编码超过32KiB、counter/previous digest错、chunk
  partial/duplicate、owner未durable fsync却ACK、ACK错或5s超时；H不得预填未来值，frame不得自含其
  digest/ACK/head，任一失败不得写success；
- final gate前模板未预分配、native setup/arm未完成、TC/TW未资格化、CPU+TC或双钟+TW越界、REALTIME
  step、stop/deadline pending非空、fd1非nonblocking、cleanup ACK未证明stdout已读尽；tail返回Python、
  post-gate出现allocation/import/loop/cleanup、SIGPIPE在write返回前被恢复默认、receipt短写/EAGAIN/
  EPIPE/close错、第二frame、remote非零/signal wait、local client wait非零、双EOF或capture
  seal缺失都必须拒绝success；
- case开始或任一pre-action时没有`CASE_T0+40s-current+110s`；首例四个近2s excursion连
  intent/leaf/clone/bootstrap/N09/observe未在共享+20s内，+20→25/+25→30/+30→40越权或最后10s
  reclaim/final/remove不可行；final reserve任一步越过work或借用10s containment补成功；
- G/S/L任一EOF缺失、raw/unframed诊断、overflow、partial stage/capture、stage extra name、任一固定
  basename ENOENT、EMPTY/final slot digest错、rotation和concurrent writer；
- old actual/future/new peak重复计费或错误退款、fixture状态污染P4/normal-chain字段。

纯单元测试不访问guest、不改系统配置、不运行field case。本机native test只能在明确isolated fixture
中创建临时对象；条件不具备则记录`NOT_RUN`和原因，不能写PASS。

## F2：冻结D、artifact和可发行合同

完成定向测试、全源suite、installed/source一致性、Linux CI和至少一次独立源码审阅。保留第一次
失败、全部skip/NOT_RUN和环境限制。只有准确D干净树、测试和审阅齐全才生成bundle。

bundle必须：

- 全部逻辑bytes≤1MiB、最多8个regular file；G artifact+context≤256KiB、context≤16KiB；
- RAM bootstrap source≤32KiB、完整remote command≤48KiB且各自单独SHA；bundle最多8个regular file，
  只含fixed collector/S、native bridge `.so`、schema/manifest/必要启动描述，无wheel、interpreter、
  credential、guest默认路径、compiler/headers或历史raw evidence；
- W不是bundle member；sealed plan/manifest另行固定W absolute identity、ELF/loader/dependencies、
  source→binary relation、完整native ABI/profile、W0/830s及wake→kill/kill→reap/reap→status+EOF三项
  margin、FD/task/CPU/RAM/kernel object/audit资源表、child-stop/prlimit/release、signal/grace/kill/reap/
  status mapping以及`W_PREFIX_CPU_MAX_NS≤1s`/`W_PREFIX_WALL_MAX_NS≤2s`/单task/64MiB/入口8FD的
  pre-arm TCB prefix envelope；signal合同固定`W_BLOCKED_SET`、child跨loader继承、initial
  fatal/G0→SIGXCPU block+DFL→signalfd create/readback+drain→raise→再次drain的顺序；资源表还须
  固定既有carrier持久分配/保留≤64MiB/1024 inode、W独立≤64MiB默认相加，以及无准确共享证明时
  carrier/W聚合≤128MiB/1024 inode另加fixed kernel objects；
- 列出每个member basename/size/SHA、D/tree、bridge source/compiler/flags/CPython ABI/artifact relation、
  clone/setup/arm/non-returning tail exports、fixed receipt/digest/signal/write/close/exit合同、carrier memfd
  flags/size/copy/page-touch/digest/seals/load、payload逻辑/RAM/AS≤1MiB及物理≤2MiB/1 shmem inode上界、
  runtime/import closure、clone/prctl/cgroup ABI、
  15帧表、FD/task/read/output/cost表和所有ceiling；
- 另列完整stage manifest：固定`action.journal`=64KiB、`result.journal`=752KiB、N01–N12十二个
  预分配intent/context各=16KiB；result准确offset为header 0、cases 8192、excursions 598016、terminal
  753664、EOF 770048；列出各EMPTY/动态slot的offset/length/digest、case raw/metadata上界、owner capture
  commit/ACK schema和37项上界。这些状态文件不是bundle member，任一basename ENOENT均为UNKNOWN；
- 列出guardian零outer write门、37个action carrier往返、final 0|1次迁移、`FINAL_CARRIER_READY`、
  result freeze/digest/固定双流导出、两marker、owner append+fsync/唯一ACK和H绑定schema；
- 列出guest/owner全部protocol FD真实类型与nonblocking flags、owner三pipe/client pidfd/三个absolute
  timerfd并行状态机、每流offset/counter/digest，及≤4KiB chunk表；列出`CASE_T0+20/25/30/40s`、
  首例最长路径、CPU样本/rounding/双计、segment/stop/overshoot catalog、两个exec gap、CP_MAX preparse
  公式、Q0/SIGPENDING pair、两代各四call-site且全程create≤8的顺序、ITIMER_PROF向下量化和临时
  RLIMIT_CPU guard、TC/TW、W remaining以及所有absolute expiry；
- 列出canonical H完整最大schema、≤32KiB `CLEANUP_FINAL` schema/chunk/ACK和≤512-byte预分配
  success receipt固定宽度/atomic-write/tail schema；H只绑定cleanup-final schema、对象及ceiling，
  并绑定W identity/PID/starttime/W0/expiry/arm/status-map摘要、W parent/PDEATH、ITIMER/临时RLIMIT
  pre-exec actual；cleanup-final保存P0 remaining、restore/disarm及其后产生的raw final值；
- 由私有plan填准确target/runtime/identity/carrier/anchor/capacity source后再次seal；
- 入口明确这是fixture batch，不是P4、consumer或正常任务。

F2硬门包括：所有strict parser/state/cost/fault测试、固定source→artifact byte relation、W准确原字节/
source→binary relation及静态资源/ABI/status资格、无systemd
Start路径、静态FD/process/clock/cleanup表、late-start/duplicate拒绝、独立source review及可执行的
F3 live preflight。硬门还须证明最大H≤16KiB、最大`CLEANUP_FINAL`≤32KiB、首例四次近2s excursion
仍能在共享20s完成且最后10s收尾可行、≤1MiB bridge carrier-copy/seal/load/setup纳入固定15s stage段、
  initial hard-9s+overshoot界、cleanup ITIMER_PROF+临时RLIMIT双guard、CP_MAX preparse最坏界、
  TC/TW native tail界，以及两代第1–8 timer/quota、固定序列前缀及第九/额外
timer拒绝和
owner双流反压状态机。支持环境还应以准确内核和同类tmpfs/runtime workload运行真实本地
  pidfd/SEQPACKET/nsfd/close_range/clone3/cgroup/reclaim/current=0/zero-guardian-output/final-export/cleanup-exec/nonblocking-I/O/EOF
测试；没有适用root/cgroup fixture时可准确NOT_RUN，但不能省掉实现和live拒绝路径，也不能冒充
目标guest能力。目标特有anchor、controller、core、clone3权限和真实counter只在F3核对；任一不符
在首个mutation或首个case准确BLOCKED/FAILED。这样不要求先运行尚未授权的目标fixture。

独立review逐项核查：

- pre-`BATCH_RELEASE`除W在完整guard后唯一clone L外没有额外fork/clone；L只做自限、DECLARE/HELLO/
  RAM bundle读取和只读gate，没有外部/持久write/create/cgroup迁移。owner原三钟、UTC/guest双钟不能刷新；
- 每个native batch/clone/EXEC_GO/G_GO动作都晚于对应journal fixed-slot pwrite+fdatasync、完整carrier
  往返、owner capture append+fsync及匹配ACK、guardian re-entry和excursion slot seal；tmpfs state不能
  单独证明issued durability；
- exact wrapper/shell/W/runtime command round-trip、W静态身份/ABI、pre-arm prefix、fd0–6表、RLIMIT/
  signal/`W_BLOCKED_SET`跨loader、timer/pidfd/prlimit/kill/reap/status与W资源账成立；anchor初始dying=0、live基线D0、depth≥2且计D0后slots≥4，B空domain、
  B cpuset/limits先readback再唯一启用四controller、guardian/S/case sibling domain leaf各自subtree-control
  空且effective cpuset/mems准确、原carrier leaf完整回迁重验和clone3原子出生满足cgroup v2边界；
- native bridge hooks、88-byte args、parent/child分支、S固定FD表及child不返回Python，以及setup/arm/
  non-returning tail的无Python/分配/import/loop路径由source/test证明；
- cleanup continuation唯一exec、canonical H最大编码≤16KiB且绑定CPU ledger/两个gap/CP_MAX/Q0/
  两代timer/deadline/O_NONBLOCK、bridge/memfd预期与cleanup-final schema；原期限/状态跨exec、准确
  0–11表、startup≤14 FD、stage artifact+memfd瞬时FD≤2、carrier copy/seal/load/setup→stage→guardian→B
  顺序由source/synthetic硬门证明；最大cleanup-final≤32KiB、durable ACK和TC/TW
  post-gate tail同样由source/fault硬门证明；H另绑定W和pre-exec ITIMER/临时RLIMIT actual，P0 remaining/
  restore/disarm只进cleanup-final；已有适用native fixture才补同类workload，缺失保留
  NOT_RUN，目标上的真实逐层证明仍是F3成功硬门；
- guardian全部正常/stop/exception/traceback路径fd1/fd2零write、每个允许action frame准确carrier
  membership、final carrier result export、owner并行drain两流/durable capture/单一ACK及client wait/
  timerfd deadline由state/fault测试证明；
- L/S各检查点`Threads=1`，guardian/S pids.max=1与B的五task峰值由真实status/counter闭合；
- W始终位于原carrier且不计入B `pids.max=5`；原carrier现场容量须同时容纳既有parent/W/L。W新增task、
  entry FD≤8/guard后峰值≤7、从进程出生完整CPU风险≤10s且status0 absolute CPU≤1s、≤64MiB物理
  风险、fixed kernel objects及`W_PREFIX_CPU_MAX_NS≤1s`/`W_PREFIX_WALL_MAX_NS≤2s`；既有carrier
  持久分配/保留≤64MiB/1024 inode，W独立≤64MiB默认相加，无准确共享证明时carrier/W聚合
  ≤128MiB/1024 inode另加fixed kernel objects。L carrier CPU/共享池的独立或可证明去重账由
  plan/source/test闭合；
- S只提高继承soft并readback；S clone返回且child仍held时，L在等待READY或SIGCONT放行前先将自身
  CPU/AS/DATA/NOFILE准确收紧为(19,20)s/(64,64)MiB/(64,64)MiB/(32,32)并readback，然后才放行S/
  等READY；SIGXCPU stop及20s hard kill均由测试覆盖；
- 每个pre-action和final-success分段前后读取process CPU、耗尽signalfd/核pending，按verified
  membership全序与rounding/迁移双计累计；每段先满足segment+stop absolute 10/20s门，success还须
  预留剩余段与TC后guardian/carrier/process≤9/9/18s；19→20s只走stop；
- root时drop bounding、再exact groups/GID/UID/fsuid/fsgid、清residual cap、NNP、PDEATHSIG和dumpable
  的顺序正确；exec前env/cwd/umask/signal/rlimit/personality/scheduler/affinity和CLOEXEC表准确；
- S/L独立；L以blocked catchable signal+signalfd观察stop set，W异常死亡则由PDEATHSIG SIGKILL
  fail closed；L在N09/S失败时持原leaf和pidfd并可kill准确child；
- G首次身份/proc观察晚于context原deadline检查；core pipe已被拒绝；
- 15帧SOURCE方向、许可顺序、L 13→18→20→22（含queue≤24）、S clone18/steady14/temp16、
  G22/R13/O13、三进程installed≤48/含queue≤50均由source/test复现，N09两pidfd在resume确认后关闭；
- case和supervisor在task/关联FD/mapping关闭后、guardian在L经0|1分支已位于carrier并exec释放旧mm后、B在子层清完后，
  都以最多4轮current-sized reclaim取得`memory.current=0`再读完整final；每层remove后关闭最后held
  FD并等parent dying=0，且fd1/fd2保持打开时guardian current仍为0；leaf peak不被写成全部physical RAM；
- pre-carrier、W、≤37 action往返、final tail、shared runtime、tmpfs、transport pipe/socket、audit/capture
  费用未混入case leaf或逐窗口重置/重复去重；L guardian外absolute累计CPU≤10s、成功≤9s，W与L
  CPU独立，carrier/audit admitted attributable CPU≤30s；
- 每例在任何intent/leaf/action前固定同一`CASE_T0`，case/pre-action保留
  `CASE_T0+40s-current+110s`；首例四项/后续三项excursion及全部业务只用前20s，之后三个阶段严格
  5/5/10s；160+480+110=750s，containment只用于stop/receipt。

review缺口在D内修复并重跑；若修复改变A的source/premise/property/cap/budget/use contract，停止并
按R形成新A，不以“实现细节”绕过。

## F3：唯一live delivery与native batch

全部离线门通过后，owner一次读取REALTIME、BOOTTIME和紧邻MONOTONIC，为三者各固定≤840s
outer deadline。在启动local client前只使用授权固定来源确认`core_pattern`非pipe、W static identity/
source relation、pre-arm TCB prefix和完整资源预算，按固定顺序create/absolute arm/readback owner三timerfd，
然后create-only写intent和`fixture_delivery_issued=true`，只发一次准确W carrier请求。W缺失或静态合同不能
预先证明时`NOT_ISSUED`；任何reply loss不重发。

### HELLO、`BATCH_RELEASE`和live admission

W入口先取absolute process CPU累计，依次完成parent-before→PDEATH set/readback→parent-after同一非1
identity、空signal mask/固定catchable dispositions/SIGCHLD flags、stdio/close_range、SIGXCPU ignore和W
RLIMIT readback；随后block/readback准确`W_BLOCKED_SET`并建只接收该set的signalfd=3，取W0并按三项
margin公式absolute arm/readback
BOOTTIME timerfd=4。W以88-byte全零args、唯一`CLONE_PIDFD`、`exit_signal=SIGCHLD`创建唯一L。W用
pidfd=5和SIGCHLD signalfd消费child唯一`CLD_STOPPED/SIGSTOP`，在同次numeric PID/live pidfd/已消费
stopped event window完成完整L profile readback，关闭自己的0–2并保持outer零read/zero write，再唯一
SIGCONT；L native stub关闭继承3/4、建立/readback准确`W_BLOCKED_SET` mask、SIGXCPU ignore/其余
catchable default并核恰0–2
后才exec runtime。W此后只poll signalfd/timerfd/pidfd，终态只用`WEXITED|WNOHANG`，并保留准确pidfd
直至wait/reap。

RAM bootstrap只能执行架构中的自限和只读HELLO。L从出生已受继承CPU hard9约束并保持/readback
`W_BLOCKED_SET`，因此W在loader/首码窗口转发的SIGUSR1只形成pending。首个user-code按process sample→
W parent/PDEATH/profile/SIGXCPU ignore/继承mask→同一held procfs `Threads=1`→Q0/limit→fatal timer
arm/readback→紧邻CPU复测的顺序完成initial CPU guard并立即固定不可刷新的G0；随后block SIGXCPU、
恢复其`SIG_DFL`，创建/readback接收`W_BLOCKED_SET+SIGXCPU`的signalfd并先drain/核pending。只有无
stop/XCPU且当前候选有余量才把CPU提高/readback为`(20,100)s`，raise后立即再次drain/核pending；任一
已pending stop只进入同一stop状态机。W唯一SIGCONT至
该门的`initial_exec_gap_wall_ns`只作正常/admission界；zero-CPU stall由W deadline物理收口。

owner在启动local client前固定HELLO发送原点；完整HELLO收齐≤10s。HELLO必须带并由L验证W absolute
identity、PID/starttime、W0、timer expiry/arm-readback摘要及W parent snapshot；W通过child固定argv把
这些字段交给L。实测
`W0→G0≤10s`，DECLARE/HELLO/等待完整release须在`G0+48s`内；所有guest期限都取W界和既有界的
较早者。owner用发送/receive区间证明HELLO时guest realtime offset全落在±2s，双方分别证明三钟delta
无step，并固定`adjtimex`/clocksource相对频率误差上界；owner三个outer deadline及guest报告的UTC
not-after剩余均≥792s。只有HELLO后才能证明W cap早于owner最早outer cutoff；任一postlaunch HELLO/
RTT/三钟/actual-W/limit/slack/CAP/raise门失败都不得发送`BATCH_RELEASE`，delivery保持consumed；只有
L已发出有界`CLEAN_REJECTED` frame、sealed W映射加W remote status 0证明L `CLD_EXITED/0`、local client
wait 0、stdout/stderr双EOF且账目完整时才可BLOCKED，否则UNKNOWN；W是唯一remote status来源。不能把pre-arm prefix称作远端
hard wall。
只有这些条件及prefix费用同时通过时，owner才紧邻issued动作前取得第二组REALTIME/BOOTTIME/
紧邻MONOTONIC和同步状态，连同原点封入固定`BATCH_RELEASE` frame；随后在写出任何frame字节前
持久写`fixture_batch_release_issued=true`，然后尝试唯一发送。短写、断线或回执丢失仍保持consumed=true。
过去的RTT不约束release单程。L收到完整frame时按HELLO guest采样后的实际双钟elapsed和固定相对
频率误差上界扩大offset区间；当前整个区间仍须落在±2s。L先用owner原点→frame第二组的三钟delta/
同步状态复核owner无step，再以区间最坏端独立要求guest UTC原始余量≥782s、证明owner当前剩余
下界≥780s。guest三钟delta仍无step且双方未unsynchronized，另由固定
adjtimex/clocksource输入证明随后760s最坏相对漂移≤2s；否则在mutation前`CLEAN_REJECTED`。L随后
从guest BOOTTIME和紧邻MONOTONIC各派生不可刷新的work `+750s`和
containment `+760s` deadline；成功受两个work clock及原UTC约束，stop/receipt受两个containment
clock及原UTC约束。780→760的20s中最多2s给漂移、至少8s位于远端收口与owner EOF stop之间，
再有10s至local hard cutoff。L只有收齐并验证frame后才在RAM置accepted并先输出`BATCH_ACCEPTED`；owner取得该frame
或后续同一状态链证据、append+fsync固定private capture后，须在任何native-batch动作前持久登记
`fixture_batch_release_accepted=true`及`batch_release_outcome=ACCEPTED`。`fixture_batch_release_issued=true`
却既无accepted证据、又无上述完整clean rejection/status/exit/EOF证据时结果为UNKNOWN。owner在原三个outer deadline最早值前10s
关闭carrier stdin写端并保留stdout/stderr读端，以EOF触发L停止；到原deadline只kill本地client
process group，不把它冒充远端kill。远端正常收口仍由L原work/containment deadline、EOF和cgroup.kill
完成，最后物理backstop是W的不可刷新BOOTTIME timer和held pidfd。必须同时证明
`W0→G0≤10s`、`G0→BATCH_RELEASE≤48s`、release→containment≤760s，总计≤818s，并给W wake→
pidfd kill、kill→typed reap、reap→W status/EOF三段保留至少12s且不重复扣费。W收到
SIGUSR1/HUP/TERM/INT/QUIT/`DEADLINE_SIGNAL`只转发一次SIGUSR1，
grace到界或W deadline只kill准确pidfd；W status0仅在原L准确`CLD_EXITED/0`且未触发deadline时成立。
双EOF可先于W status，owner须继续wait W；W/local client异常、D-state或未reap只能UNKNOWN。任何情形均
不重发。

`BATCH_RELEASE`后L在首个mutation前完成固定live admission：W absolute identity/PID/starttime/W0/
expiry/arm摘要、准确PPID/PDEATH/profile和W remaining、W/parent/L原carrier task/FD/CPU/RAM/audit容量；
其中既有carrier持久分配/保留须≤64MiB/1024 inode，W独立≤64MiB默认相加；没有准确共享证明时，
现场readback须证明各项在界内且可用容量足以承受carrier/W聚合风险≤128MiB/1024 inode另加fixed
kernel objects，
以及ordinary身份和allowlisted manager、旧对象状态、runtime/core、anchor/controllers/cpuset/mems/depth、
初始dying=0/live基线D0/计D0后slots≥4、
目标层可写`memory.reclaim`、原carrier leaf完整返回
资格、held `/run` parent、capacity、audit/journal/capture和三个deadlines；并实证guest/owner各
protocol FD类型与nonblocking flags、owner三timerfd/client pidfd并行状态机、guest Q0/有限
SIGPENDING pair、四个timer的create/arm/readback顺序、三wall clock/API/blocked signal、CPU clock/
resolution/rounding、segment/stop/overshoot catalog、initial hard9/overshoot、cleanup ITIMER_PROF/
临时RLIMIT backstop、两个exec gap及TC/TW。任一缺项输出有限
BLOCKED receipt，不创建B。初始carrier/audit费用从pre-reserved
prefix扣除并核对，不临时新增预算。

### B、stage、S和case

admission通过后：

1. L仍在原carrier leaf，经全程held的`/run` parent dirfd create-only建立完整stage；写入/复读sealed
   bundle，建立并逐页实写固定64KiB action journal、752KiB result journal与十二个固定16KiB
   intent/context EMPTY slots，核对root owner、ordinary read-only、准确offset、size/blocks/schema及
   2032KiB/23-inode逻辑总账和≤3MiB/48-inode物理资格。L逐页触达runtime/import closure，并在该处加载、触达
   bridge全部允许mapping；预热不冒充file-backed folio永久归属；
2. create-only建立空procs的B并读回`cgroup.controllers`恰含四项；先写/readback固定`cpuset.cpus/mems`及effective值、B cpu/memory/pids
   limits和可写`memory.reclaim`，再只向新B唯一写`+cpu +cpuset +memory +pids`并严格读回恰四项，
   取得B严格零initial schema后才建立children，anchor全程只读。guardian/supervisor及每个later case
   都须为domain、空subtree-control，按架构合同配置/readback CPU/cpuset/pids和memory
   max/swap/min=0/low=0/high=max并核effective值，在首个task前分别取得严格零initial schema；L证明`Threads=1`后才
   首次自迁移到guardian；该次加最多37次action往返和按实际0或1次final进入的全批self-write≤76；
3. L以供S继承的CPU `(20,100)s`、AS/DATA `(64,192)MiB`、NOFILE `(32,64)`执行S clone；child在
   native gate保持未放行。parent clone返回后、等待READY或放行S前，L立即把自身CPU/AS/DATA/NOFILE
   收紧为(19,20)s/(64,64)MiB/(64,64)MiB/(32,32)并readback，失败即kill准确S并stop。通过后才放行；
   native child只把S的CPU/AS/DATA/NOFILE soft提高到继承hard、逐项复读完整RLIMIT，净化固定FD/env/
   process state并exec S；L持pidfd/streams取得S `BOOTSTRAP_READY`。该门完成前不建case；
4. 固定顺序N01→N12。每case在任何intent、leaf或pre-action前一次取得不可刷新的`CASE_T0`并派生
   `CASE_T0+20/25/30/40s`；开始case及每个pre-action门都须证明
   `remaining_work≥CASE_T0+40s-current+110s`，并通过同一process-clock ledger、当前segment最早
   fatal rearm/readback及stop pending门。每case只在对应预分配文件固定slot按准确offset/length pwrite并fdatasync，
   size/blocks不变，由L复核完整slot/final digest；
   首个case clone3前通过journal→carrier membership→owner capture fsync/ACK→guardian re-entry→
   excursion slot seal提交`fixture_native_batch_issued=true`，每case的`clone_issued=true`也须用同一链
   绑定intent digest后才唯一clone；
5. 每case由S建fresh leaf并配置，经native bridge clone child；L ARMED后，S先通过同一carrier往返链
   提交`exec_go_issued=true`再尝试一次`EXEC_GO`，native child完成drop/净化并exec G；G
   `BOOTSTRAP_READY`后，S再通过该链提交`g_go_issued=true`才尝试一次`G_GO`。每个完整往返前后都
   检查CPU ledger/timer/SIGXCPU且≤2s；首例native-batch/clone/EXEC_GO/G_GO四次、后续三次往返，
   连同intent/leaf/clone/drop/exec/bootstrap/N09/observe全部共享`CASE_T0→+20s`，不得另起G时钟。
   任一owner ACK丢失时
   动作不发生但已commit位保持consumed；任一调用/写入短失败也视为该动作已消费，均不重发；
6. 执行准确case；到`CASE_T0+20s`无条件停止业务/observe，`+20→+25s`只执行original pidfd TERM/
   cgroup.kill stop，`+25→+30s`只完成typed wait、empty、三层EOF/report/`CASE_DRAINED`，
   `+30→+40s`只执行reclaim/final/remove。S关闭
   gate、G三条stream、全部SCM/proc/ns临时FD、child pidfd和自己的case leaf FD，只发不声称final的
   无FD `CASE_DRAINED`；L清空control rights queue并关闭自己的pidfd/重复leaf/临时FD，只留最后held
   leaf。L最多4轮先读C=`memory.current`、非零则写十进制C到`memory.reclaim`并复读；EAGAIN后复读
   为0仍成功，四轮后非零即UNKNOWN。只有current=0才由L读取并形成唯一完整`CASE_FINAL`，把G两路
   raw、S `CASE_DRAINED`/wait/EOF及reclaim/final写入对应48KiB result固定区、fdatasync并关闭临时FD，
   再经held B dirfd唯一unlink，关闭最后case leaf FD并等B `nr_dying_descendants=0`。S无remove fallback；
   完整封闭后才允许下一个case；任一阶段越界或最后10s不足以完成最多四轮reclaim/final/remove即
   UNKNOWN并停止后续case；
7. unexpected BLOCKED/FAILED/UNKNOWN立即停止后续case，不换ID、不重试、不补一个探测case。

`BATCH_RELEASE`后work阶段上界：live admission+stage+S≤160s；最多12case及case间收尾≤480s；
固定final-success reserve=110s，其中S/supervisor闭合≤15s、final carrier/journal/export/ACK≤15s、
FD/H/BEGIN/cleanup exec≤10s、carrier bridge copy/digest/page-touch/seal/load/setup加完整stage验证/删除≤15s、
guardian/B/anchor≤35s；最后20s中唯一`CLEANUP_FINAL`/
durable ACK≤5s，post-gate receipt tail/remote exit/双EOF/owner final capture seal≤15s；
总计≤750s。work到期或catchable stop后只进入
≤10s containment，最迟760s：最多5s TERM，随后cgroup.kill、wait/empty/EOF/receipt；不再开始case或写成功。
final marker后的5s ACK包含在上述15s export分段内，不增加或刷新任何deadline。
每例严格使用同一`CASE_T0`的20/25/30/40s边界；阶段提前完成只缩短以后deadline。D-state、kernel或carrier失效时只做已授权
有限stop并保留UNKNOWN，不承诺必然释放。

### 无重试和有限收尾

L/S只可操作本batch held anchor下的准确B/stage/child。不得清理旧Q2对象、reset失败旧unit、停止
allowlisted user manager或补连第二个管理会话。stage/leaf只有身份完整、进程/FD已停且账目先保留
时可删；删除失败或身份不明则保留到reboot并计全额。任一case leaf删除失败因B只有三个descendant
名额而立即停止后续case，至少为`UNKNOWN_RETAINED`。

最后收尾顺序固定；下列每个可返回final-success分段进入及verified membership边界都须更新同一CPU
ledger，按segment/physical-stop/success-remaining-tail最早候选rearm/readback fatal timer，并证
process CPU<19s且无observed/pending `SIGXCPU`；否则立刻转stop且永久失去success资格：

1. S停止后，L完成S wait/三条EOF，关闭S control/stdin/stdout/stderr/pidfd，只留最后held supervisor
   FD；按case同一最多4轮current-sized reclaim规则取得`memory.current=0`，再读完整final，经held B
   unlink supervisor、关闭最后FD并等B dying=0；把supervisor final和batch terminal状态写入固定
   terminal/global slot并fdatasync/关闭临时FD，guardian内仍对fd1/fd2零write；
2. 若L仍在guardian，先证明`Threads=1`并用同一held对象重跑原carrier资格表，只写`0`做唯一final
   self-migration，再从held视图证明实际membership；若此前action terminal failure已把L留在carrier，
   只重验当前carrier并记录`final_migration_write_count=0`，不得再写`cgroup.procs`或把它当重试。
   这类历史失败保持UNKNOWN。两分支都在第38个4KiB slot冻结`FINAL_CARRIER_READY`、0|1迁移数、
   action journal摘要、result slot bitmap/counters和固定占位，不写result全文件digest、H或导出后ACK；
3. L fdatasync第38 slot后冻结result，使用一个CLOEXEC临时FD和预触达buffer流式计算全文件digest并按
   固定slot/stream顺序导出752KiB内容；每帧带offset/length/digest。随后向stdout/stderr分别写唯一
   ≤256-byte `FINAL_CAPTURE` marker。owner把两路全部frame/marker append+fsync private capture后才回
   唯一≤256-byte ACK；L在marker后≤5s、整个final carrier/export段≤15s及原期限内验证并耗尽。
   large chunk未在deadline前按remainder补齐、atomic marker/ACK partial、EPIPE、EOF、错counter/
   digest/head或freeze后写均UNKNOWN且不重发。ACK/capture head
   只进入H；完成后关闭result临时FD；
4. L把仅存对象规范化为固定0–11：carrier stdio、signalfd、procfs root、cgroup2 root、原carrier leaf、
   anchor、B、guardian、stage、`/run` parent。cycle remap scratch≤1且立即关闭；随后close_range 12以上、
   只清0–11 CLOEXEC并复核准确表。L构造≤16KiB canonical H前缀，绑定准确batch/session/boot、D/tree/plan/
   bundle/source摘要、bridge setup/arm/tail API及carrier-memfd flags/size/digest预期、D0、FD0–11身份/flags
   （FD3另绑定signalfd mask=`W_BLOCKED_SET+SIGXCPU`）、
   W absolute identity/PID/starttime/W0/BOOTTIME expiry/arm摘要/status-map、W PPID和L
   `PDEATHSIG(SIGKILL)`、原期限、latches、case位图、action链/owner ACK heads、37个excursion status/摘要向量、
   `FINAL_CARRIER_READY`、result全文件digest/slot状态、final markers/ACK/capture head、全部stage final/EMPTY
   digest、process/guardian/carrier CPU ledger和handoff process+相邻BOOTTIME/MONOTONIC/REALTIME样本、
   rounding/迁移双计、segment/stop/overshoot catalog、两个exec gap的CPU硬界/wall admission界、
   ITIMER_PROF resolution/timeval向下量化/最小非零值/readback误差/expiry/requested/actual与临时
   RLIMIT pair/readback、sealed
   CP_MAX/preparse公式、Q0/
   SIGPENDING/SigQ转换、两代各四timer call-site/expiry、全部protocol `O_NONBLOCK`预期、cleanup-final
   schema/对象/ceiling及TC/TW。H只内联固定status/bitmap/摘要，不内联4KiB slot或capture records，也不
   预填P0 remaining、restore/disarm或其它exec后值。F2须对37项+22 stage entry最大编码实测≤16KiB；
   H不得写回result。exec前重验W identity/PPID/starttime/expiry余量和PDEATH，用可信账本证明
   `carrier_accum+cleanup_gap+STOP_C≤10s`、
   `process_handoff+cleanup_gap+STOP_P≤20s`，success还须在全部剩余段与TC后闭合guardian/carrier/
   process 9/9/18s，并证明wall gap早于work/containment/UTC及W deadline。随后耗尽signalfd并确认全部
   blocked stop/deadline pending为空，确认旧`ITIMER_PROF`为零/SIGPROF无pending并设置SIGPROF
   unblocked/`SIG_DFL`；取得handoff process/相邻三钟样本，按最早physical/success候选扣完整
   `EXEC_GUARD_DELIVERY_OVERSHOOT_NS`，将ITIMER timeval向下量化后唯一arm/readback。再按absolute
   process CPU保守向下取`CLEANUP_RLIMIT_HARD_S`，使`HARD_S*1s+RLIMIT_CPU_KILL_OVERSHOOT_NS`
   不晚于最早physical候选，soft=`min(19,HARD_S)`，原子set/readback；无正余量、无整数候选或任一步
   失败均不得exec。把handoff、ITIMER requested/actual、临时RLIMIT pair/readback、absolute candidates和
   W remaining填入H，完成最终canonical encode/SHA；从guard arm到H/hash/BEGIN/exec/P0/full-ledger
   rearm的全部费用仍计cleanup gap。预构造`CLEANUP_EXEC_BEGIN{H_digest}`≤atomic-write bound，零字节
   EAGAIN只在原期限/W expiry内回ppoll继续同一未发送logical frame，完整raw write时H不变，partial/
   EPIPE/其它错误/超时把success latch锁UNKNOWN；若guard余量仍足，只可重算带该latch的H/SHA后继续
   同一次cleanup exec，不得从头重发或发第二帧。结束后不再做FD mutation，以准确runtime、≤16KiB
   封存source、最终H及其SHA只尝试一次`-I -B -c` exec；ITIMER_PROF和临时RLIMIT跨exec保留，不新增
   issued/ACK，exec失败不重试；
5. continuation首个user-code在任何解析/写前取得process sample P0，立即读取`ITIMER_PROF`并只接受
   armed/nonzero remaining、SIGPROF `SIG_DFL`且unblocked，再从继承FD4核`Threads=1`，readback临时
   RLIMIT_CPU、W-bound `PDEATHSIG(SIGKILL)`和准确W PPID；任一步失败不得创建timer或继续。该读取属于
   preparse gap。由继承有限SIGPENDING pair派生Q0，按sealed常量计算
   `preparse_expiry=min(P0+CP_MAX_NS,20s-STOP_CPU_MAX_NS[PROCESS])-overshoot`；候选不晚于P0或静态
   最坏pre-arm/parse/full-rearm CPU不能严格早于expiry即停止。设置SIGALRM default/unblocked，按cleanup
   generation第一call site重建/absolute arm/readback fatal timer，立即耗尽继承signalfd，确认全部
   blocked stop/deadline pending为空及`SigQ=Q0+1`，旧event只可stop。guard生效后才strict parse/verify
   source/H；紧邻取P1，要求P0/P1≥handoff且P1早于preparse fatal和ITIMER expiry，把
   P1-handoff+rounding仅一次计carrier并更新last，以H的ITIMER actual和P0/P1 delta核remaining/candidate，
   随即按完整ledger/catalog通用最早候选full rearm/readback，且P0→readback≤CP_MAX_NS。只有full-ledger
   fatal已生效且严格早于ITIMER expiry，才凭CAP_SYS_RESOURCE恢复/readbackRLIMIT_CPU `(19,20)s`，再
   disarm/readback ITIMER为零并确认SIGPROF无pending；任一步失败保留更早guard并只可UNKNOWN。再按
   handoff顺序读三wall clocks并核elapsed/step，按BOOTTIME/MONOTONIC/REALTIME顺序重建/arm/readback
   原absolute wall timer、逐项核SigQ至Q0+4；紧邻取P2/三钟，只追加P2-P1+rounding并再次full rearm。
   handoff→P2 CPU不超cleanup CPU gap，三钟elapsed不超cleanup wall admission界；zero-CPU stall由W
   expiry收口。随后复核boot/W identity/parent/starttime/expiry、原双钟/UTC期限、root/RLIMIT/affinity/
   signal mask/signalfd/SIGPIPE/PDEATHSIG、BEGIN latch、自己位于FD6 carrier leaf及准确FD0–11；startup
   临时FD≤2且复核时恰12项。失败不写success，只在原containment/W deadline内有限收尾；
6. continuation预分配32KiB cleanup-final和≤512-byte receipt buffer。在verified carrier从FD10打开固定
   bridge并复核fstat/size/digest；以固定flags新建executable/sealable memfd，保持artifact FD+memfd
   瞬时仅2项，按固定chunk复制、逐页触达、复读全字节/digest，施加并readback四个seal，关原artifact。
   关原artifact后，load阶段memfd+loader/procfd临时对象峰值仍≤2；再从memfd复核ELF/SOABI/loader/
   dependencies/setup/arm/tail exports，经资格化procfd load并关memfd及loader临时FD；
   mapping留至`_exit`，payload逻辑/RAM/AS≤1MiB、含folio/THP/metadata/allocator的瞬时物理风险≤2MiB/1 shmem inode，CPU/wall和shared charge全计carrier。调用setup注册
   receipt buffer/layout/fd0–fd2及一字节stdin probe scratch并核摘要。之后才按完整manifest复核并unlink全部stage文件：bundle核原SHA、
   两个journal和十二个intent核H/owner capture最终或EMPTY digest；任一basename ENOENT、extra name、
   digest错或ENOTEMPTY均UNKNOWN。关闭stage FD，经held parent删除stage并关闭parent FD；copy/seal/
   load/setup加完整stage验证/删除共同受固定15s分段约束；
7. continuation在carrier fd1/fd2两端仍打开时，以同一reclaim规则把empty guardian current降至0；
   成功不依赖pipe drain、关闭或缓存页释放。随后读完整final，经held B unlink并关闭guardian FD、等B
   dying=0；再把empty B current降至0，读完整final/hierarchical ceilings，经held anchor unlink并关闭B
   FD，最终证明anchor live=D0/dying=0；
8. 用预分配32KiB buffer形成唯一canonical `CLEANUP_FINAL`，包含canonical H bytes/digest、continuation
   P0/P1/P2与FD验证、carrier bridge copy/memfd size/digest/seals/load/setup实际记录、完整stage verify/
   delete、stage parent remove、guardian/B完整final/control raw bytes、reclaim/remove/last-FD/dying、anchor
   复原、CPU ledger/catalog、P0 ITIMER remaining/H核对、RLIMIT restore、ITIMER disarm/SIGPROF pending
   actual与两代timer状态。frame含counter/previous digest，不自含其digest/ACK/capture
   head。L从已验证carrier按固定≤4KiB chunks发送一个logical frame；owner并行drain并完整append+fsync后
   回唯一≤256-byte `CLEANUP_FINAL_ACK(counter,frame_digest,capture_head)`。exchange≤5s且不重发；
   任一错误锁UNKNOWN；
9. 全部可失败cleanup/验证及ACK完成后，fd1 `O_NONBLOCK`已readback且ACK已证明此前stdout读尽。
   continuation以arm入口一次性注册counter/digest/ACK head、last sample、CPU账、stop latch、原deadline
   和TC/TW等最终immutable inputs，随后只调用一次不返回的`fixture_cleanup_tail`。native入口首动作按
   固定顺序取得process/BOOTTIME/MONOTONIC/REALTIME sample，把last→sample+rounding计carrier并执行
   final gate：`process+TC≤18s`、`carrier+TC≤9s`、guardian≤9s，双钟+TW早于work/UTC且REALTIME无step，
   W未触发且W expiry仍有固定退出余量，ITIMER_PROF已disarm/SIGPROF无pending，耗尽signalfd并核stop
   latch/pending为空，再以一字节scratch对nonblocking fd0 raw read且只接受`-1/EAGAIN`；EOF、额外byte
   或其它结果失败。通过后只按固定offset原位填充receipt并以无分配无loop路径
   封digest，恢复/unblock catchable stop/deadline signal；SIGPIPE保持ignore直到唯一≤512-byte、≤
   `_PC_PIPE_BUF` raw nonblocking write返回，随后恢复SIGPIPE默认、关闭fd1/fd2并`_exit`。最终sample后
   不得Python/allocation/import/loop/cleanup/第二frame。仅全写且两close成功才exit 0；partial/EAGAIN/
   EPIPE/其它write/close错在恢复SIGPIPE并尽力close后非零退出，late stop signal可产生signal wait。
   owner只有取得完整唯一cleanup-final/ACK与success receipt、sealed W映射加W remote status 0证明原L
   `CLD_EXITED/0`、local client wait 0、双EOF和capture final fsync/seal才接受success；双EOF可先于W
   status但不能替代它。其中receipt、W remote status/exit和双EOF须早于guest gate+TW
   及原成功期限；该W status 0依据sealed mapping同时证明原L `CLD_EXITED/0`。local client wait与
   capture final fsync/seal使用最后15s分段剩余并须早于work/UTC/outer原成功期限，不纳入≤1s TW。

任一exec/reclaim/final/remove/close/dying失败不得写成功。删除不返还本轮budget；不得把
css_offline、charge reparent或目录消失当作`memory.current=0`证据。

## F4：independent receipt、账目和发布

S经内部pipe给L每case intent digest、batch及每case action commit counter/digest、clone/pidfd/leaf、
G报告、typed waits、kill/empty、`CASE_DRAINED`、G EOF和费用；S不声称reclaim后的final，L在guardian
内不把这些内容写outer。L独立形成每case唯一`CASE_FINAL`并写固定result区；final carrier export后，
cleanup continuation核对supervisor/guardian/B各自`memory.current=0`/完整final、每层close/dying、
guardian零outer byte、action excursions、result/owner durable ACK、stage和audit/capture账目，先输出
唯一`CLEANUP_FINAL`并取得owner durable ACK，再经TC/TW final gate输出唯一success receipt。
delivery owner以同一nonblocking状态机逐项保留此前pre-action append+fsync及ACK，最后取得L原client/
进程stdout/stderr真实EOF、随后sealed W的remote status 0、local wait 0、carrier结束及private capture
最终fsync/seal；只有W固定status mapping可由0证明原L `CLD_EXITED/0`，不得把W粗粒度非零映射冒充
原raw wait status。L自报SEALED不能替代这一层。

| 条件 | `fixture_qualification` |
| --- | --- |
| delivery未发 | `NOT_RUN` |
| delivery已发、`fixture_batch_release_issued=false`，且L已发有界`CLEAN_REJECTED` frame、sealed W映射加W remote status 0证明L `CLD_EXITED/0`、local client wait 0、双EOF和账目完整；W为唯一remote status来源 | `BLOCKED_RETAINED` |
| `fixture_batch_release_issued=true`，但L已发有界`CLEAN_REJECTED` frame、sealed W映射加W remote status 0证明L `CLD_EXITED/0`、local client wait 0、双EOF和账目完整；W为唯一remote status来源，`fixture_batch_release_issued`保持true且不重发 | `BLOCKED_RETAINED` |
| `fixture_batch_release_issued=true`，但accepted与clean rejection均无法证明 | `UNKNOWN_RETAINED` |
| `BATCH_RELEASE`后在首个case前admission拒绝，且全部已建对象/exit/EOF/账目完整 | `BLOCKED_RETAINED` |
| guardian任一额外outer byte、action excursion、final result export/owner两路durable capture、`CLEANUP_FINAL`/ACK或success receipt不完整/不匹配 | `UNKNOWN_RETAINED` |
| 已发动作的身份、wait、stop、EOF、final peak/counter、账目或seal缺失 | `UNKNOWN_RETAINED` |
| 证据完整但一个准确关系或negative expectation不成立 | `FAILED_RETAINED` |
| N01–N12、三层stop、guardian零outer byte、action往返、final carrier export/ACK、完整唯一`CLEANUP_FINAL`/ACK和native success receipt、TC/TW门、sealed W mapping+W remote status 0证明原L `CLD_EXITED/0`、local wait 0、双EOF、capture final fsync/seal、全部caps/账目和outer seal完整 | `FIXTURE_LIVE_REFERENCE_MATCHED` |

raw plan/bundle/streams/system facts只进私有版本化证据。Public记录实际D/tree、bundle摘要、脱敏
fixture关系、case矩阵、准确PASS/FAIL/NOT_RUN/BLOCKED、资源上界和未证项，不含账户、路径、
boot、机器标识、raw日志或私有SOP历史。旧field/P4/normal-chain字段保持原值。

## B必须准确覆盖的决定内容

请求Owner决定时必须给出准确R、A commit、scope和F0–F4，并明示：

- 旧`dfdd653…`被新A替代为未批准提案，历史字节/审计保留；
- 接受限定的fixture endpoint execution integrity premise，不接受原terminal provenance；
- 批准C后的source/test、RAM bootstrap、direct cgroup fixture、bundle和验证；
- 接受只使用既有、预先封存和资格化的native W作为SSH顶层程序/L准确parent；不安装、上传、编译或
  替换W。接受W pre-arm TCB prefix只受固定`≤1s CPU/≤2s wall/单task/64MiB/入口8FD/zero-I/O`
  endpoint-premise envelope约束、不冒充kernel hard wall，
  以及W在完整guard后唯一clone L、pidfd stopped-child prlimit/release、`W_BLOCKED_SET`由child跨loader
  继承、initial signalfd建立前SIGUSR1只pending、全生命周期deadline/grace/kill/reap/status mapping；
- 批准对唯一Q1 guest/历史Q2普通身份的一次conditional carrier request：outer UTC envelope≤840s，
  三钟/48s/RTT/792s门、HELLO→release按相对频率界扩张后仍在±2s的current offset门和release到达时
  owner剩余下界≥780s后最多一次`BATCH_RELEASE`，
  其后的guest work≤750s、containment≤760s，包含root-only
  B/guardian/S/fresh leaves、stage、最多12个
  唯一case、stop/EOF/final accounting/seal和允许对象的有限收尾；
- 接受postlaunch只读拒绝只有在L有界`CLEAN_REJECTED` frame、sealed W mapping加W remote status 0证明
  L `CLD_EXITED/0`、local client wait 0、stdout/stderr双EOF和准确账目完整时才为
  `BLOCKED_RETAINED`；W是唯一remote status来源，缺任一项即UNKNOWN，已写issued位保持true且不重发；
- 接受W0起不可刷新BOOTTIME remote-exit cap≤830s：W0→G0≤10s、G0→release≤48s、release→
  containment≤760s合计≤818s，另留至少12s给wake→pidfd kill、kill→typed reap、reap→W status/EOF
  三项固定margin且费用不重复扣；owner local kill
  不能替代W远端backstop，W/L不可中断或W未reap只保留UNKNOWN；
- 接受固定stage EMPTY slots、64KiB action journal、752KiB result journal准确布局，以及每个action
  journal→carrier→owner durable ACK→guardian→slot seal链；接受旧carrier/new guardian各最多38次、
  全批最多76次self-write、每项≤2s、无数字PID、无重试；
- 接受只在新建且空procs的B先配置/readback cpuset与limits，再唯一写
  `+cpu +cpuset +memory +pids`并读回恰四项；anchor保持只读，三个child均为subtree-control空的domain leaf；
- 接受guardian membership期间所有正常/stop/exception/traceback/diagnostic路径fd1/fd2零write，
  非action结果延迟写固定result slot；接受final carrier 0|1次迁移分支、result freeze/digest/752KiB
  双流导出、两marker、owner append+fsync及单一ACK，marker后ACK≤5s、整段≤15s；
- 接受case/S关尽关联对象后最多四轮current-sized reclaim至`memory.current=0`；接受L在carrier用
  ≤16KiB封存H/0–11表进行一次cleanup exec；continuation把stage bridge复制/逐页触达/复读digest到
  carrier-owned sealed executable memfd，从memfd加载setup/arm/non-returning tail、关闭临时FD并保留
  mapping至exit，随后按stage→guardian→B完成收尾，并在fd1/fd2仍开时证明guardian current=0；
  H绑定预期、cleanup-final记录copy/seal/load实际；该exec不新增发行或重试；
- 接受guest/owner全部协议端nonblocking；owner同时poll stdin/stdout/stderr、client pidfd和三个absolute
  timerfd，且在启动client前已create/absolute arm/readback三timerfd；持续并行drain双流并在capture
  append+fsync后才ACK；接受≤4KiB chunked result/cleanup-final；
- 接受同一process-clock ledger、rounding/迁移双计、segment/stop/overshoot catalog、每段与membership
  边界按segment/physical-stop/success-remaining-tail最早候选absolute rearm的fatal timer、两个exec gap、
  L从出生继承CPU `(8,9)s`/SIGXCPU ignore且initial fatal active后才raise；cleanup exec前以
  `ITIMER_PROF`向下量化加临时整数RLIMIT_CPU形成双guard，sealed CP_MAX preparse按
  P0→ITIMER/SIGPROF→Threads/临时RLIMIT/PDEATH/W parent→fatal guard→H→P1/full-ledger rearm→
  RLIMIT restore/ITIMER disarm→P2顺序；同一real UID `Q0+8`
  有限SIGPENDING及两generation各四固定call site（完整success八次、失败固定前缀、全程≤8）顺序；
- 接受固定110s final-success reserve、160+480+110=750s，以及每例同一`CASE_T0+20/25/30/40s`和
  case/pre-action必须保留`CASE_T0+40s-current+110s`；首例四次、后续三次excursion都在共享前20s，
  containment不补成功；110s中的固定15s stage段已包含最大1MiB carrier bridge copy/digest/
  page-touch/seal/load/setup与完整stage验证/删除，不新增时长；
- 接受唯一≤32KiB canonical `CLEANUP_FINAL`/owner durable ACK≤5s及setup/arm后不返回Python的固定
  native TC/TW post-gate tail；最终四钟sample/gate和receipt fill/digest/write/close/exit均在该入口；success
  还必须绑定≤512-byte单次receipt、sealed W mapping+W remote status 0证明原L `CLD_EXITED/0`、local
  client wait 0、双EOF和capture final seal；
- 接受需求中的G/session、root、shared runtime、carrier/audit/capture/storage全部上界和失败保留；另接受
  W在原carrier新增1 task、entry installed FD≤8/guard后峰值≤7、从出生完整CPU风险≤10s、status0最终
  absolute CPU≤1s、保守物理
  风险≤64MiB及fixed kernel objects，W/L CPU独立；既有carrier持久分配/保留≤64MiB/1024 inode，W
  独立≤64MiB默认相加，无准确共享证明时carrier/W聚合≤128MiB/1024 inode另加fixed kernel objects，
  carrier/audit admitted attributable CPU总界≤30s；
- 接受L guardian/carrier成功CPU各≤9s、process≤18s、每个pre-action/final分段的<19s且无SIGXCPU门，
  final gate另以`+TC_MAX_NS`闭合9/9/18并以`+TW_MAX_NS`闭合退出时限；19→20s仅用于stop；
- 完整batch一次授权、无需逐项询问；同批12个case各一次clone不构成第二个batch；没有第二次
  delivery、`BATCH_RELEASE`、native batch或material expansion；每case的一次`EXEC_GO`和一次
  `G_GO`只是同一已发行case的两道门，均不可重发；
- NS3、NS4、P4、产品/生产、旧window/normal chain和全部排除项保持未授权。

缺少这些绑定的“继续”“批准旧A”或一般修复授权不能作为本范围B。不得代Owner合成决定。
