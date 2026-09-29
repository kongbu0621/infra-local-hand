# H07 首轮历史异常的限定续验：架构

- Authority：Owner；状态：**PROPOSED / Gate OPEN**。
- Scope：`LH-Q2-H07-R1-CONTINUATION-v1`，U1–U4；R/旧 A/C 见[需求](REQUIREMENTS.md)。
- 这是旧 A 的增量，T/G/S/W、原子 clone3 入组、原 pidfd/双流和六例机制保持。

## 职责与信任边界

| 责任方 | 职责 | 不具备的权限或证明能力 |
| --- | --- | --- |
| Owner | 对准确新 A 接受指定首轮历史未知，关闭有限变更范围 | 决定不能生成清理事实或测试通过 |
| executor | 读取全部实验运行历史、登记额度/原因、发布准确 D，手动派发并取证 | 不能凭剩余额度略过后续停止条件 |
| fixture T | 验证来源/环境，固定账户观察、创建与精确清理，保存 schema 2 报告 | 不能处置首轮 runner，不能删除身份未登记或已替换对象 |
| G/S/W 与 native 收件器 | 沿用旧控制与六例事实合同 | 不接收本次历史处置为 fence/EOF/期限证据 |
| 独立报告收件器 | 按版本验证来源、continuation、账户事实及原 native 结果 | 不把总布尔值或新 boot 当完整事实 |

执行环境仍信任 GitHub 托管 OS、固定 T/helper 和账户工具。本实验不对恶意宿主
或并行敌对 root 账户管理提供不可伪造的对象世代；该假设不成立就拒绝清理。

## 历史处置与本轮运行分离

原 run 的 report/manifest/diagnostics 不修改；新的 continuation 记录只引用原
run=36577764454、attempt=1、round=1、准确源码、artifact 及原报告/ZIP SHA-256。
处置语义为“Owner 接受该历史未知，仅不阻断限定续验”，不是 resolved 或 cleaned。
第 2/3 轮仍各自产生独立 run、原时钟、账户、cgroup、报告和完整清理责任。

来源准入同时绑定旧 A/C、新 A/C、准确 expected_commit=github.sha=HEAD；D 必须
从新独立 C 下降，两个 A 的文档摘要均核对。新三文档、决定、额度事实及全部实验
源码进入冻结源码闭包；旧源码闭包不得被伪装为包含新授权。新 A/C 不从输入字符串
临时采信，而由新 C 后发布的准确实现固定。旧 schema 1 仍按旧 A/C 校验。

## 托管隔离依据及其限度

2026-09-29 核对的 GitHub 官方资料：[runner 选择](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)
说明 hosted job 使用新的 runner image 实例；[runner 参考](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
将标准 ubuntu-24.04 x64 列为 VM，单 CPU ubuntu-slim 容器是不同类别。
这是设施约定，不能当作原 run 的销毁回执。

每次派发前复核该约定仍适用、workflow 仍固定标准 ubuntu-24.04 x64，实际准入
读取 github-hosted/Linux/X64、Ubuntu 24.04、image/kernel/工具事实；拒绝 self-hosted、
job container、不同类别或无法核对的来源。不靠重写环境变量伪造托管身份。
本轮 boot 必须可读且与所有先前已用轮次不同；首轮 boot 的脱敏比较值是
`SHA256(小写 UUID，无换行)` = `8c0a15a1229a2c1b468cacda35de76f8e9b9fb0f96b82695207da8090a562810`。
第 3 轮还必须绑定已核验第 2 轮原件及 boot。不同 boot 是必要拒绝复用检查，
不是新 VM 或首轮已清理的充分证明。缺少任何前序记录或无法排除重复 dispatch 就停止。
额度全局事实由 executor 核对 GitHub 全部相关运行（包括非 main 和失败准入），
不声称单个 job 的 round 输入或 concurrency 锁能证明全局额度未消费。

## 账户观察与清理状态

观察只针对确定的本轮名称和它的 UID/GID 关联。固定本地 `/etc/passwd`、`/etc/group`
只在内存中有界读取，派生同名、UID/GID 别名、组成员和其他主组引用冲突；不读取 shadow。
同次有限 NSS 点查核对解析出的目标与本地记录一致。先有界读取固定
`/etc/nsswitch.conf`（≤16 KiB）：passwd/group 各须恰好一条，去除注释及分隔空白后，
provider 序列只接受 `files` 或 `files systemd`，不接受 action override、重复条目、
compat 或任何其它 provider。`initgroups` 若显式存在也只能恰好一条且 provider 序列与 group 相同；
缺省时沿用已准入 group 来源。配置和两个数据库须为 root 所有、不可由组/其他人写入
的普通文件，以不跟随符号链接的方式读取；不满足就在 NSS 调用前拒绝。
systemd 仅作为本地身份点查来源；所有接受目标仍必须
与本地 files 记录一致。远程/未知来源不支持，不发起其查询，不改配置。
每次观察只允许各一次 getpwnam(目标名)、getgrnam(目标名)；若准确目标账户存在，
再各至多一次 getpwuid(目标UID)、getgrgid(目标GID)、getgrouplist(目标名,主GID)。
不进行 NSS 全库枚举。别名和其他主组引用依据本地 files 的完整有界解析；不宣称
排除了任意外部目录中的别名。固定可信本地来源和无并行管理仍是限制条件。
`files systemd` 不是“只读取这三个文件”的闭包：
[systemd 的 nss-systemd 说明](https://github.com/systemd/systemd/blob/main/man/nss-systemd.xml)
描述了本地 userdb/Varlink 及动态身份来源。这里将该解析服务视为受信托管 OS 设施，
输入/时间限制只约束观察者直接读取和收件，不宣称界定服务内部所有读取或异步工作。
不控制、重启或改造这些服务，不主动提交网络探测；配置不符、目标不一致或发现
异常下游活动即拒绝，不能用观察者退出证明所有 OS 服务工作已结束。
只返回目标非秘密字段、冲突计数/布尔及读取完整性、前后身份/双钟，不输出其他用户。
本地来源变化、重复记录、NSS 与本地不一致、超时或截断均为歧义，不当作不存在。
每次观察先固定全部三个文件的身份/元数据，完成解析和 NSS 后整体复核 held FD
与路径映射，比较 dev/ino/size/mtime_ns/ctime_ns；任一变化拒绝。它仍是有限区间
稳定观察，不声称跨文件原子快照；可信 OS/无并行管理的假设不能被这些字段替代。

固定观察在单独有界子进程中执行；只在 Python pwd/grp 调用前后看时钟不足以
约束阻塞查询。每次观察在启动前固定 MONOTONIC/BOOTTIME 原点和最早截止，
窗口≤2秒且不晚于原阶段截止，覆盖启动、读取、原退出、双流EOF及回收观察。
超时/kill请求不证明进程已消失；退出或双EOF未证即留UNKNOWN，不启动下一观察、
账户创建或删除。原有清理阶段只可继续处置这个已登记原进程，不重置其原截止或
补记按期完成；未决持续阻断账户操作。每个本地数据库输入≤256 KiB，
每次结构化观察输出≤8 KiB，输出仍计入原 diagnostics/report 上限。无网络探测、
重试环或无限枚举；最多创建前、创建后、清理前、userdel 后和必要 groupdel 后五次。

| 状态/事实 | 可执行动作 |
| --- | --- |
| 创建前准确账户、组均不存在且来源完整 | 只调用一次固定 useradd profile |
| 前查存在、失败、漂移或不完整 | 不创建，保存事实 |
| useradd 非零、超时、原退出/捕获未确认 | 停止 setup；只在原命令无未决后做一次有界后查；不重试，不据后查授予删除权 |
| 观察到候选身份 observed_identity | 仅留证；不等于本轮可清理所有权 |
| rc=0、原退出/双流完整、后查及全部身份/组限制通过 | 才登记 admitted_identity 并允许后续 cgroup/probe |
| 清理前 admitted_identity 完整匹配且无未决命令/共享身份 | 原有一次 userdel；必要时对已登记且不共享的组调用一次 groupdel |
| 身份未登记、漂移、共享或后查不明 | 不猜测删除；cleanup 未证，停止 |

原实现在完整后条件检查前赋 account_id 的行为必须调整：候选身份先记录，只有
全部条件通过才登记可清理身份。失败后出现部分账户或组也不得自动晋升。
清理复查 name/UID/GID/home/shell/附加组及别名；组必须无成员、无其他账户主组引用。
账户工具不使用 --remove/-r、强制删除或递归清理；userdel 已删除组时按后查留证。
userdel 后的第4次观察继续使用原 admitted UID/GID 检查别名及主组引用，不因目标名
消失丢掉原关联；第5次只在确实发出 groupdel 后执行，不追加第6次补查或重试。
仅相同元组不能排除敌对 ABA 替换，可信临时 runner 且无并行账户管理是明示假设。

后查分类固定为 ABSENT_BOTH、EXACT_PAIR、PARTIAL、AMBIGUOUS、UNOBSERVABLE。
ABSENT_BOTH 只说明观察时目标未发现，不能排除账户数据库备份、日志、锁等其他
副作用，不能据此将失败创建的 cleanup 改 true。cleanup 的成功范围仅为已登记
实验对象，绝不表示整个 OS 字节恢复原状；原阶段失败与诊断始终保留。

## 收件与版本

未来顶层报告显式使用 schema_version=2，在原 native/case/预算字段之外强制增加
account_setup 和 continuation。source 明确保留旧 approved_A/closure_C 并增加
approved_continuation_A/closure_continuation_C；字段集、类型、身份、前序绑定和
状态关系严格校验，不忽略未知字段、重复键或未知版本。

account_setup 含目标/run/command 身份、前查、命令 attempted/started/exit_observed/
rc/timeout/termination、双流 EOF/完整性/bytes/SHA、后查、observed_identity、
admitted_identity 和清理观察。没有取得的值为显式未知，不能以 null rc 当 0。
continuation 含准确处置身份、新 A/C、前序 run/原件摘要/状态、已用额度及 boot 比较；
原首轮清理字段必须保留 false。整份 report 仍≤2 MiB，不另增旁路证据预算。

schema 1 继续走旧合同并保留原结果；不通过填默认字段把旧原件“升级”成 schema 2。
新轮次必须 schema 2，schema 1 即使显示 QUALIFIED 也不能满足本次续验准入。
所有 native 回执和 C1–C6 判据不变；历史接受决定不参与生成本轮 fence/cleanup。
新账户记录不完整时，不允许总体资格通过。原件逐文件摘要与 manifest 继续核对。
