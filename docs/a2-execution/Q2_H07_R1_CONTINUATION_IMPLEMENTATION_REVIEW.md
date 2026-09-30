# H07 首轮限定续验实现

本记录对应已 CLOSED 的 `LH-Q2-H07-R1-CONTINUATION-v1` U1–U4。准确新 A 为
`a08a5055c35009a896ad6c6059d709758cc78436`，Owner 决定及原文见
[独立决定记录](../governance/Q2_H07_R1_CONTINUATION_OWNER_DECISION.md)。
独立 CLOSED C 为 `7d33c698ff6c1bf34733ee2429d0404ace2abd55`，tree
`c66e43ca0a28d88fa50d92bef8fbe1ec19406387`；首次实现提交以 C 为直接父提交，
随后测试名称修复 D `d4dd8c6ea4284d0d9e8802073df6ea1cc9c52029` 沿该链下降。
原 R、旧 A/C、新 A 三文档及首轮原件均不改写。

## 实现与证据边界

- `run_fixture.py` 将账户观察/命令纳入原准备或清理双钟窗口；观察子窗口最多
  2 秒，包含启动、原退出、双流 EOF 及回收观察。两流都计入原 256 KiB diagnostics。
  输出截断、迟到或退出/EOF 未证会阻断后续账户动作；后来回收原进程不会改写其原回执。
- 同目录内 `account_evidence.py` 分离固定观察、候选身份和准入身份。
  固定三个本地文件先准入、后有限 NSS 点查、最终整体复核；只输出目标及冲突摘要。
  创建成功的全部后条件成立后才登记删除权限。失败后观察到部分对象不授权自动删除。
  清理核对原 name/UID/GID/home/shell/groups 及共享身份，userdel 后继续绑定原 UID/GID。
- `continuation.py` 固定旧/新 A/C、首轮原件索引及原状态、额度与 boot 比较。
  首轮 `UNKNOWN_RETAINED` / cleanup=false 仍保留，仅该历史事件获限定接受。
  当前没有第二轮完整索引，第三轮会拒绝；以后也须独立检查前轮原件和另一明确修复。
- `verify_receipt.py` 显式分支校验 schema 1/2。新报告必须有账户及续验事实，
  严格核对字段、原双钟、身份、捕获摘要、来源闭包和原预算；账户总布尔不授予资格。
  原 native/helper 与 C1–C6 判据不变。
- workflow 仍仅 `workflow_dispatch`、attempt 1、标准 ubuntu-24.04 x64，
  没有 job container、自动重试或自动实验。固定新 C 的祖先关系，绑定准确 D；
  round 输入不能证明全局额度，executor 仍须读取所有相关运行和 attempts。

观察依赖受信 GitHub 托管 OS 和无并行账户管理；相同身份元组不是不可复用世代。
允许的 nss-systemd 后端是受信 OS 服务，观察输入/时间上限不证明其内部所有工作有界。
完整清理只指已登记实验对象，不声称整个 OS 回滚。不同 boot 不证明首轮机器已销毁。

## 验证与运行状态

最终离线结果及准确文件摘要见同目录 evidence 中的
`q2-h07-cgroup-fence-spike/continuation-offline.json`。这些检查只用合成数据和模拟
账户/进程，没有在 cloud 创建账户/cgroup、执行 helper 或 probe。
集成期间旧测试夹具补齐新闭包和新的账户监督接口；交叉审查还修复了前查退出但
缺 EOF 被误当清理成功，以及长 wait 未持续复核 BOOTTIME 两处边界。

2026-09-30 当前登记：修复 D `d4dd8c6e` 的普通 CI 已通过，准确结果见下节；
**第二轮尚未派发**，总额度仍已用 **1/3**。首轮 `36577764454` 的原
UNKNOWN_RETAINED、cleanup.verified=false、probe/C1–C6 NOT_RUN 均保留。
后续必须冻结本次纯文档及证据登记发布后的准确 HEAD，作为新的 `expected_commit`，
核对实验实现/workflow 与已验证 D 的字节关系、新 C 祖先关系，完成该 HEAD 的普通 CI，再核对全部实验历史及 attempts、
剩余额度与托管环境依据，再通过 GitHub 页面手动派发 round=2。
不能在 main 前进后仍填写旧 D，或把普通 CI 通过当成真实实验通过。
纯文档变更不会自动触发当前普通 CI 的 push 路径；须使用该普通 workflow 的手动入口。
它不消费 H07 实验额度。普通 CI 成功后保持准确 HEAD 不变再派发实验，结果随后合并登记，避免登记提交再次改变派发身份。
取得 run ID 即计 **2/3**，失败也计入。
页面或账号不可用则保留未派发，不改用 push/rerun/其他执行通道。

第二轮任何新增 UNKNOWN、清理未知、根本环境不支持或其他原停止条件都继续生效。
若第二轮已获资格即结束；不能为 C5 竞态或剩余额度而重跑。第三轮还需要明确另一
源码缺陷、准确修复、离线及普通 CI、第二轮完整证据和无新增阻断。
本实验不签发原 Q2 startup，不代表原机器、真实远程链、文件系统或完整计费已合格。

## 首次实现与普通 CI 的保留结果

首次实现 D 是 `78fc0a3ca0cbc54e4c6def38338d04afe4d7449d`，tree
`1d8d6a9fb6db1e4b51edb7ca6ca33ac74b118808`。离线 317 PASS / 0 SKIP。
普通 CI `36586633992` attempt 1 在该准确 D 上完成，但总体为 FAILURE：
Linux 源码 3063 PASS / 51 SKIP、真实 root collector 16 PASS / 0 SKIP、
installed 94 checks / 292 commands PASS；Windows 995 PASS / 996 SKIP / 2 ERROR。
Windows 错误发生在同一个超大输入用例的 setup/teardown，原因是 pytest 将
262145 字节参数自动编码进 `PYTEST_CURRENT_TEST`，超过平台环境变量长度上限。
该结果及日志摘要保存在 `continuation-initial-ci.json`，不改写为成功。

后续修复仅为五个账户输入负例设置固定短 ID，测试输入、断言和所有 runtime 文件不变。
再次整套离线 317 PASS / 0 SKIP；317 个收集节点最长 215 字符，见
`continuation-ci-repair-offline.json`。该离线检查时，修复后的准确提交普通 CI 尚待结果；
后续已取得的准确结果单列如下，不改写首次 CI 失败。
此次 CI 与测试名称修复均未派发实验，额度仍为 1/3。

## 修复后的准确普通 CI

准确 D 为 `d4dd8c6ea4284d0d9e8802073df6ea1cc9c52029`。
[run 36592634218](https://github.com/kongbu0621/infra-local-hand/actions/runs/36592634218)
attempt 1 已完成，三个 job 全部 SUCCESS；[准确证据](evidence/q2-h07-cgroup-fence-spike/continuation-final-ci.json)
与首次失败、短测试名称修复离线记录分别保留。

| 检查 | 结果 |
| --- | --- |
| Linux 源码测试 | 3063 PASS / 51 SKIP |
| Linux 独立真实 root collector | 16 PASS / 0 SKIP |
| Windows 源码测试 | 996 PASS / 996 SKIP |

这些结果只归属于上述准确 D。普通 CI 和本次纯文档登记均未派发实验，不消费实验轮次，
不补首轮 cleanup，不证明当前 runner 的原语能力或原 Q2 准入。

## 可选第三轮的可达性缺口

当前 `continuation.py` 的第三轮检查要求第二轮原报告经真实收件器验证为无错误的
REJECTED 且 cleanup 已证；但 `run_fixture.py` 尚无可达的该类完整报告生产路径，
`test_continuation.py` 的相应正例替换了收件器，只证明该层输入检查，未证明整链可达。
该缺口不阻断已批准的第二轮。第三轮若确有需要，须先依据第二轮原件和明确源码缺陷
完成准确修复及验证，并继续满足全部原停止条件；不得改写第二轮原件状态、放宽收件判据
或把剩余额度作为派发理由。第二轮已获资格即结束，新增 UNKNOWN、清理未知或
UNSUPPORTED 等停止条件不能用这项缺口豁免。
