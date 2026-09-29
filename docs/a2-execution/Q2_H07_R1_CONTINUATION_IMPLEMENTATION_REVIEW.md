# H07 首轮限定续验实现

本记录对应 `LH-Q2-H07-R1-CONTINUATION-v1` 的 U1–U4。准确新 A 为
`a08a5055c35009a896ad6c6059d709758cc78436`，Owner 决定及原文见
[独立决定记录](../governance/Q2_H07_R1_CONTINUATION_OWNER_DECISION.md)。
独立 CLOSED C 为 `7d33c698ff6c1bf34733ee2429d0404ace2abd55`，tree
`c66e43ca0a28d88fa50d92bef8fbe1ec19406387`；实现提交以 C 为直接父提交。
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

本实现记录提交时，新的准确 D 普通 CI 尚待远端结果；第二轮尚未派发，
总额度仍已用 **1/3**。后续必须先核对准确 D 的普通 CI、全部实验历史、托管环境
依据，再通过 GitHub 页面手动派发 round=2。取得 run ID 即计 **2/3**，失败也计入。
页面或账号不可用则保留未派发，不改用 push/rerun/其他执行通道。

第二轮任何新增 UNKNOWN、清理未知、根本环境不支持或其他原停止条件都继续生效。
若第二轮已获资格即结束；不能为 C5 竞态或剩余额度而重跑。第三轮还需要明确另一
源码缺陷、准确修复、离线及普通 CI、第二轮完整证据和无新增阻断。
本实验不签发原 Q2 startup，不代表原机器、真实远程链、文件系统或完整计费已合格。
