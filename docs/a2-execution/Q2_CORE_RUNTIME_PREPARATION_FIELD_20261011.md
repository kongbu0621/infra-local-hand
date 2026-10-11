# RP1 冻结与 RP2 实际预检返回

范围 `LH-Q2-CORE-RUNTIME-PREPARATION-CONTINUATION-v1`，Owner批准及准确A/C见
[闭合记录](../governance/Q2_CORE_RUNTIME_PREPARATION_CONTINUATION_OWNER_DECISION.md)。
本记录只登记实际返回；原A三文档、旧IR1冻结/IR2失败和所有旧caller保持。

## RP1 已完成

准确D `934122fab56f1a78f43dbc773e0de9598ea63078` 下降自独立C
`4ae2b8f83f65b3262015e46f43d64ea035e89c91`，由正常
[PR #16](https://github.com/kongbu0621/infra-local-hand/pull/16) merge
`b3c828face975c9b28a6bbfc06ea78f51cde8113` 发布，没有squash。
自己的首次CI [38133163908](https://github.com/kongbu0621/infra-local-hand/actions/runs/38133163908)，
attempt 1，三项job全部成功：Linux 7810通过/89跳过，独立root文件检查16通过/0跳过，
独立安装94检查/292命令；Windows 2025通过/1390跳过，独立安装10检查/10命令。
本地准确D干净检出构建的独立wheel安装也为94检查/292命令PASS。

本地完整来源/维护载荷/core静态验证在实际AS512 MiB、FD256、CPU240秒限制下完成，
CPU 7542536000 ns，聚合RSS峰值上界361807872 B，elapsed 7491866187 ns；无现场观察。
维护handoff峰值129 FD、独立core preparation上界127、guest上界98。最大静态维护
marker 54907 B、receipt 45908 B；post descriptor 49094 B，压缩载荷39822 B，
展开175988 B，remote argv 55399 B。合成维护成功形状的独立core验证通过，approved
input 443609 B、transition 57684 B、原包保守上界21585736 B；未构造真实核心包。

原798720 B identity archive保持；新409600 B/18成员失败归档实际分配421888 B/
3 inodes。准确D的13份受保护源码704010 B，含index/preparation实际分配745472 B/
16 inodes；各在获批2 MiB/64 inode准备池内。两归档及旧11a五原件、原冻结/终态、
十二旧caller摘要和完整历史均再次离线核对。原55份持续持有原件不变，当前父输入20。

实际256-FD双归档测试6通过；新私有caller及真实本地父管道/EOF/一次性控制共28通过。
[实现记录](Q2_CORE_RUNTIME_PREPARATION_IMPLEMENTATION_20261011.md)中各次中间失败保留，
不以此次CI覆盖或取消。两个新caller与全部15份依赖、准确R/A/B/C/D、首次CI、安装、
固定目的地/私有payload、两归档、来源和全部费用完成最终冻结，freeze 83452 B。
冻结完成时RP2 NOT_ISSUED，RP3/H01/Q4/H11 NOT_RUN。

## RP2 唯一预检失败，未消费

冻结的新 `lhqjgrow-20261011b` caller实际调用一次，只运行一次本地preflight。
preflight返回exit 3、`BLOCKED / GROWTH_ACTIVATION_HOST_BOOT`，error_type
`ObservationError`；顶层caller实际exit 3，父捕获确认stdout和stderr均EOF。
没有执行same-window execute，SSH请求数0，consumed marker未创建。

准确D的失败位置在`q2_journal_growth.main`将保留activation的host boot与本次
window binding比较处。实际preflight保存了window binding，和原冻结中的activation
host boot逐值比较确认不同；两值及其来源摘要保持私有，核对复用已有返回、无新观察。
不据此推断当前VM存在、运行状态、guest boot、当前安装或发生了何种宿主变更。
该失败在VM进程/镜像冻结和维护传输之前；没有guest命令、poweroff token、备份、
journal增长、维护重启或核心包。返回management_usage的CPU/RSS为0/0；源码确认该点
尚未执行第一次Usage.sample，这两个初始化值不是实际零用量证据，不能用于退款。

十个实际本地返回（parent launch/双流、caller started/双流/实际完成、preflight双流、
summary）及其私有索引保留。固定九个维护输出均不存在，维护原件集合为空；execute
双流及RP3 parent/caller started也不存在。没有guest或维护execute的完成结果，不把
本地caller完成解释为维护成功，也不把“未消费”解释为可重放。

独立终态为`RP2_INVOKED_FAILED_UNCONSUMED_RP3_NOT_RUN`；RP1 immutable freeze与
全部15个新caller/dependency摘要不变，旧11a冻结/终态和十二旧摘要也不变。
RP2为`INVOKED_FAILED_UNCONSUMED / STOP_AND_RETAIN`，RP3/H01/Q4/H11保持NOT_RUN。
没有自动审批拦截，本次停止来自实际预检身份校验；未尝试替换身份或绕过门禁。

## 保留边界

十五代旧维护仍已消费；旧09c/10b与本次11b均是实际调用过但未消费的preflight。
十八份完整维护义务及全部旧读取/准备、新准备池与core捕获保持25283 MiB/7364 inodes，
维护准入25155 MiB/7332 inodes，无退款。每份档位2余量仍各计一次。

本批唯一preflight已经失败，不再调用11b或原07a，不修改旧冻结，不补采host/guest
现场证据、探测SSH、替换host boot/VM身份、放宽校验、启动、清理、回滚或另开窗口。
后续仅使用保留返回及源码进行离线工作。NAS发现与新作业准入继续关闭，外围保持暂停。
所有原始返回、索引、归档、caller、路径和机器资料私有；本记录不构成新的现场授权。
