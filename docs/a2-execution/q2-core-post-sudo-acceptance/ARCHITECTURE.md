# sudo 修复后核心单次验收：架构

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-POST-SUDO-ACCEPTANCE-v1`，S1–S3；R和固定来源/身份/资源见[需求](REQUIREMENTS.md)。
- 本文与需求、[实施方案](IMPLEMENTATION_PLAN.md)构成新准确A；批准和独立C之前不实施。

## 1. 最小增量与边界

复用host builder、独立parser、entry、三field文件、现有installer/harness和六文件finalizer。
仅将固定旧attempt单例扩为**恰两个已固定attempt**，接入一个新固定批次；不实现任意历史数组、通用重试平台或新runner。
原 wire scope/manifest.amendment 仍指原合同，包v3、approved-input顶层v1、HELLO/BIND、remote-result v2不换义。
新scope仅作为新增授权链和UUID seed；新旧对象只能采用需求表整套固定映射，不能混搭。

| 组件 | 这次必须接齐的增量 |
| --- | --- |
| contract/freezer、独立host builder/parser | 固定双旧profile、新A/B/C→D来源、十原件和新身份；各自独立严格消费 |
| prior reader/approved-inputs | 同一受保护anchor下读十件原bytes、核验两个缺失remote-result，不重跑旧finalizer |
| entry/capture | 原live窗口、192MiB/48当前条件、唯一新marker/request、六文件集合 |
| dispatcher admission | 两旧scope各A/B观察、分别保留承诺；全部通过才create-only安装和业务 |
| host consumer/finalizer | 复核双旧观察和所有摘要/容量，区分历史UNKNOWN与本次真实结果 |

原件只进入既有 `private/approved-inputs.json` 和guest RAM，仍≤1048576 B；包输入仍≤33554432 B。
三field source cap 8192/49152/524288 B不扩大；本次bootstrap仅余121 B，实施必须先做静态尺寸预算，超限不能删校验或提高cap。

## 2. 双旧来源的显式格式演进

`reconciliation` 变为 `local-hand-q2-core-reconciliation/v3`，exact keys：
`schema,state,applied,released_bytes,released_inodes,record_basenames,prior_core_attempts`。
原state、空applied、两项零release、原五seal basename保持；仅把单例替换为固定顺序 `[20261003a,20261005a]` 两元素。
两元素schema为 `local-hand-q2-core-prior-attempt/v2`，exact keys仍是
`schema,scope,session_id,implementation,package_sha256,manifest_sha256,files`；scope保持各原wire scope，implementation为原准确D/tree。
每个files仍为恰五项ASCII basename排序，各项 `basename,bytes,sha256,raw_base64`；strict base64解码/回编码、原字节摘要、总长度和需求固定profile逐项一致。
第二批各项bytes等于散列已核验raw长度并受原role cap限制，合9072 B；第一批既有逐项长度及9318 B总和保持。
不把第一profile中的零输入/255 wait/EOF false用于第二profile；第二profile使用需求中已固定非零输入、3 wait、双EOF及failure状态。
第二profile必须保留原 `STOP_AND_RETAIN` 和 `CORE_OUTPUT_MISSING`；marker/receipt/capture的consumption关联、原streams长度/摘要/EOF、文件身份、fsync和same-inode回读事实仍按原冻结schema交叉校验，不只验顶层hash。
任何profile混用、缺件、重复/额外字段、重序列化替代raw、额外stdout frame、伪造COMPLETE或业务truth变更均拒绝。

十件读取沿用held parent/fd、O_NOFOLLOW/O_NOATIME、single-link regular、0600、owner/device、fd/name前后完整身份与摘要。
同一live anchor必须包含两旧原件；不搬移原件来凑条件、不读取新现场。两旧remote-result有任何存在/不明即拒绝。
各旧HELLO用其**原发行D**中冻结的loader/bootstrap契约核验，boot/InvocationID/cgroup只从原bytes取得；禁止当前D身份替代旧D。
第一旧observer已实施不等于第二旧observer可复用结果。旧writer无需仍存活；旧PID无starttime仍不得当作进程身份。

第二旧profile还须离线对需求固定dispatcher hash和原D调用顺序作独立审查：原错误只来自sudo parser，错误前尚未进入旧scope核对、安装、quota或独立业务unit启动。
与十原件结构/摘要、marker包/manifest/approved-input摘要和单HELLO一致后，这一固定代码路径才支持本A的pre-business限定。
它不恢复历史执行/退出证明；无法建立此限定时不发行、不扫描额外unit、不把局部日志当作任意过程完整证明。

`historical_capacity_obligations` 变为 `local-hand-q2-core-historical-capacity-obligations/v3`：原全部keys和值保持，
仅 `prior_commitment` 替换为 `prior_commitments`，与两prior一一对应、固定顺序。
每项exact keys沿用 `scope,session_id,source_attempt_sha256,logical_bytes,logical_inodes,cpu_seconds,host_capture_bytes,host_capture_inodes,released_or_refunded`；
各旧固定289406976/16512、2090、67108864/16、false；各source摘要为对应v2对象canonical/no-LF SHA-256。
每旧32池按既有parent-role和每实际 `(dev,fs_uuid)` 单独计完整池：同池同设备去重、跨设备重复，三个32MiB/1024 headroom各计state设备。
两旧增量不能写回伪造原24+12行或覆盖更早totals；逐设备先算全部历史，再加本新批。所有release/refund仍0/false。

## 3. 一个carrier内的四次固定观察

原policy/program/guest校验后，固定顺序：旧03a观察A → 旧05a观察A → 原filesystem/quota/absence/capacity/managers → 旧03a观察B → 旧05a观察B。
任何失败立即终止，不继续剩余观察取成功样本。原同一双钟窗口、held parents和各旧boot一致性必须覆盖所有观察；无需也不允许独立SSH probe。
每次SHOW沿用旧架构§4的精确十属性、`show --all`、exit0、空stderr与完整ASCII record；最多5s wall、2CPU-s、32768B合计输出，合4次且限需求预算。
每个observer先消费自身观察槽，失败不可重入；不存在轮询、等待自然退出、stop/kill/reset-failed或清理动作。

两旧分别复用原 `LOADED_TERMINAL` / `COLLECTED_ABSENT` 判据：同原Invocation终止且MainPID0、旧精确cgroup不存在/同身份空；
或两次not-found/inactive/dead、空Invocation/cgroup且原cgroup两次不存在。完整字段、父链、nofollow及boot一致，A/B不能换分支/换inode。
两个observer同时held直至全部B和最终身份复核完成，不能检查完第一个就允许新安装。两旧CURRENT_SCOPE_QUIESCENT后才进入原case链。
最终复核覆盖两个held parent和各旧精确cgroup basename：ABSENT仍确实缺失，EMPTY仍为同一fd/name身份；漂移即停，不增加第五次SHOW或连接。观察不是对未来持续静止的互斥保证。
需求的pre-business前提使前置跨批只涉及三个carrier；各内helper计入自身cgroup，最多3GiB/384pids。
新批预算中的2624MiB/1160仍只描述新批；不把它宣称为核验前全三批峰值，旧usage UNKNOWN从不填0。
四次SHOW helper的CPU、memory、pids计入原carrier；`native_children_started`仍只统计原quota native children，上限16不改，不把管理helper混入该字段。
普通非core整机负载不在这一上界内；不能核验各carrier原限额、helper均在其cgroup内或pre-business前提时停止。
3GiB/384只是固定三carrier的理论上界，不是当前整机可用内存、排他预留或完成保证；不增加meminfo/整机探针，资源失败沿原停止路径。

session.admission 中将单 `prior_core_attempt` 显式替换为 `prior_core_attempts`，其余八字段保持。
新列表固定两项原 `local-hand-q2-core-prior-quiescence/v1` 记录，保持该record exact keys和全部A/B事实；每项摘要绑定对应新的prior/v2对象。
每项历史remote_exit/usage仍UNKNOWN、release0、current_scope_quiescent=true；缺一不可。
session/admission摘要链、独立host消费者都重算两个记录和原件，旧shape不发行新批；读取历史原件仍按其旧冻结profile，不能就地升级旧事实。

## 4. host条件和原结果流

仅原pre-marker点采样一次 `fstatvfs`，紧邻原双钟、同held anchor/writer身份检查。
成功记录升 `local-hand-q2-core-host-capacity-condition/v2`，沿用原v1 exact keys，
只将 `prior_attempt_sha256` 替换为 `prior_attempts_sha256`（有序双prior数组canonical/no-LF摘要）；scope/session绑定本新scope/05b，implementation仍绑定准确新D/tree。
known_commitments恰三行03a、05a、05b，每行67108864 B/16；required固定201326592/48。
origins/observation/management摘要、dev、有效非负整数/正frsize、双钟晚返回拒绝和最终live重验保持。
earlier_host_obligations仍为 `{coverage:UNKNOWN,bytes:null,inodes:null,shared_pool:UNKNOWN}`；完整准入/排他预留false、释放0。
新增可靠host来源若推翻此前固定UNKNOWN前提，按R停止受影响范围；不能隐去矛盾或静默替换新口径。

本条件仍为原live返回sibling，不增加第七个持久文件、不改变原capture_accounting/receipt格式；任一后续失败不被容量通过掩盖。
保留sudo详细错误码沿原stderr有界回传，禁止回显原始配置、密钥或私有路径。
H01 PASS才进入Q4，Q4完整PASS才H11；H11只恢复自身origin，不借读取业务原result补统计。
最终报告区分三批消费、传输、历史truth、当前静止、业务结果及资源；只有原live finalizer能确认COMPLETE，不能重启接受旧receipt。
失败回退只有保留现场和准确失败状态，不回退旧合同再发请求，也不产生第四批。
