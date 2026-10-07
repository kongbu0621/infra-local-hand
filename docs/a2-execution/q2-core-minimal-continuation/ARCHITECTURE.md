# 核心接续架构：目标维护与任务执行

Authority：Owner；**PROPOSED / Gate OPEN / NOT APPROVED**。
范围及取舍仅来自[需求](REQUIREMENTS.md)，scope `LH-Q2-CORE-MINIMAL-CONTINUATION-v1`。
现有维护和核心组件继续使用；不增加服务、权限代理、通用远程接口或新的扫描组件。

## 维护删减

`q2_journal_growth.py` 的 CLI 中 writer-auth/writer-preflight 参数及校验、`WriterObserver`、
`ImageSet.verify_writers` 和八个扫描调用点一起退出当前维护路径；保留普通维护 CLI。
不能传 `writer=None` 后继续落入本地 `collect_image_writers` 回退。
guest 文件中 root payload/WriterProtocol 的只为此路径服务部分随之移除。
保留 `ProcessIdentity`、host boot/window 读取和 guest 本身必要的静止/持久证据检查。
这里关闭的是 host 全进程扫描；不能误删目标 VM/guest 检查，也不能扩张 guest 扫描范围。

原 `writer-preflight` 改为最小普通维护预检交接：准确 D、manifest 摘要、原 host boot/
双钟起点/期限、nonce、普通预检实际累计计量。execute 验证同一绑定并重做目标准入，
不创建新时钟、不退还已用 CPU、不借新进程降低 RSS 记录，不接受旧 writer handoff。
删除 host root observer 的 sudo/TTY认证依赖；guest 原固定 sudo 入口及 SSH 配置不变。
没有新增后台任务、日志平台或密码收集。

manifest/marker/receipt 显式绑定本准确 A/C/D 和 `TRUSTED_SINGLE_ADMIN` 访问模式，
记录 `host_writer_observation=NOT_PERFORMED`、`continuous_exclusion_proven=false`。
采用严格 `lhq-journal-growth-manifest/v2`、`lhq-journal-growth-receipt/v2` 和普通预检
`lhq-journal-growth-preflight/v1`，不让旧消费者把新记录读成八次观察已通过；
旧格式只用于历史识别，不能作为本次成功证明。没有 writer rows/空报告的成功替身。
source admission 保留准确旧批准来源，并显式记录本次覆盖替代，不能宣称旧全部谓词仍适用。

修改前后的实际数据链仍为：目标核验、guest 静止、正常关机、原 QEMU 退出、离线结构检查、
完整备份、一次镜像增长与逻辑比较、一次启动、一次 ext4 增长、内容/容量和结果回收。
O_EXCL marker 是一次性消费标记；QEMU 的正常锁是协作锁，二者都不描述为全程强制排他。
不使用 `-U`、`-r`、ignore-locks、强制共享或强杀 mutator；失败保持原 STOP_AND_RETAIN。

## 维护结果接入核心

维护成功后，本地受保护读取固定 consumed/events/pre/post/receipt/vm.pid 原件，交叉验证
准确来源 D、session/nonce/原输入、动作顺序和次数、备份/镜像/内容校验、真实退出/EOF、
旧 VM pidfd 退出、新 VM 身份及五个原镜像。旧 start.sh/vm.pid/serial 原件不改。
只允许已批准的新 pidfile 与 serial=null 参数差异，其余 QEMU 参数与原配置等价。
不只接受 receipt 中的 VERIFIED 字符串，也不重新执行维护命令以产生证据。

结果以固定 `journal_transition` 数据对象（`local-hand-q2-core-journal-transition/v1`，
canonical JSON 最多65536 B）接入原 approved-input：绑定上述原件的长度/
摘要、准确维护来源/访问模式、前后 boot/镜像/内容/容量和完整验证结论。
原件在 host 完整验证后保留本地；guest 独立检查投影结构、来源、关系及其与当前 HELLO 的
一致性，不把 host 投影误称为 guest 重新验证全部原件。字段和大小严格限定在原 1 MiB 输入内；
任一必需事实不能表达、原件不全或超界就不能发行，不能截断或依赖未经检验的 PASS 标记。
这延续现有可信本地输入构造者边界，不引入新信任方。

host 在发送 BIND/package 之前核对新 HELLO，dispatcher 及独立返回消费者再次核对。
新 boot 必须由合格维护 post 推导，等于新核心 HELLO，并区别于原 boot；四份旧 HELLO
仍绑定各自原 boot。不得将旧 boot 全局替换成新 boot，也不得删除当前 boot 校验。
旧 boot 与维护 pre 不一致、当前 HELLO 与维护 post 不一致或维护失败均拒绝接续。
在新 boot 上，四个旧 scope 各保留 A/B 两次观察，只接受 unit not-found/inactive/dead、
InvocationID/ControlGroup 为空且原 cgroup ABSENT；旧 invocation 不在新 boot 上重新采用。
当前缺席不等于历史正常退出，所有历史 UNKNOWN/承诺继续保留。

## 核心与资源

`q2_core_prior_attempt.py` 增加精确 05c profile；前三 profile 和旧原件不变。
05c 的 D/tree、正式包/manifest、五 capture 的长度和摘要取自基线 Git 中的
[05c 现场记录](../Q2_CORE_POST_LOCALE_ACCEPTANCE_REVIEW_20261005.md)。
四核心原件共20件/36534 B；两诊断原件仍只按现有受保护读取与保留语义采用，原文不入包。
独立 host/guest 消费者同步四旧集合与维护代次：reconciliation/historical-obligations 升至v5，
prior-quiescence升至v2；prior-attempt单项仍v2。固定新字段和集合，拒绝旧三项输入冒充新批。

contract/freezer/package/entry/dispatcher/bootstrap 同步07a固定身份及本 A/C；loader 原样。
dispatcher 仅增加第四旧 profile、受维护证明约束的新 boot 分支和资源保留接线；
原 sudo/sshd 文法、任务权限、quota、安装和 H01/Q4/H11 执行逻辑不扩大。
四旧观察顺序 A03a/A05a/A05b/A05c→原容量/manager→B03a/B05a/B05b/B05c→最终复核。
八槽各一次，共用原 carrier；任一失败停止，不用重取样制造通过。
旧四与新 carrier 配置量合计5 GiB/640 pids仅作保守合同总数，不称新 boot 同时存活量；
旧域全部缺席后的新批2624 MiB/1160 pids限额不变，诊断/管理祖先和整机负载仍不在该总数内。

历史账本不因 guest 重启清零。四旧、新批、更早义务及维护完整保留分别入账；容量条件
按需求执行，不将已使用量和未用承诺擅自互相抵销。journal 达400 MiB也不能代替实际五池准入。
本范围没有生产部署/自动恢复；部分维护失败后的恢复仍需另行决定，不能在K3中隐式修复。
