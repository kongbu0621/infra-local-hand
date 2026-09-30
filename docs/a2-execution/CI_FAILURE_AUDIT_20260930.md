# 2026-09-30 全仓失败检查核查

## 核查结论

Owner 要求核查仓库内所有红叉，修复仍存在的问题。本次只读枚举 GitHub Actions
全部 **80 次运行**（两页 50 + 30），其中 **53 成功、27 失败**，没有取消、超时
或未完成的运行。起始 `main` 为 `21a2646b70bf2069ccb6ffd734f0f6e19fe5d348`。
这份计数是修复发布前的快照，后续运行不回写历史计数。

- 普通 CI 失败 25 次：15 次为 2/3，10 次为 1/3，没有普通 CI 的 0/3 记录。
  全部逐项读取失败 job 日志，并检查对应补丁及其在当前源码中的保留情况。
  这些旧问题已有后继修复，没有发现仍需重复修改的相同缺陷。
- 独立实验失败 2 次，各为 0/1；实验已按 Owner 指令退休，保留未通过的事实。
- 当前 8 个分支头没有失败或运行中的检查；5 个分支有成功检查，另 3 个候选／
  发布分支没有检查。开放 PR 为 0。空 statuses 集合的 `pending` 不算正在运行。
- 现行 CI 另有可复现的 PR 分类漏检，本次作针对性修复，见下文。

完整运行身份、逐失败 job 与修复映射、分支头快照见
[脱敏核查清单](evidence/ci-failure-audit-20260930.json)。原始完整 job 日志没有复制
进公开仓库。旧提交的红叉属于原提交，不会因后继提交修复而自动变绿；本次不删除
失败记录、不重写历史、不把旧提交按新源码重跑。

## 25 次普通 CI 失败与现有修复

表中修复提交均为上述起始 `main` 的祖先，相关改动仍存在。每个链接对应实际
失败 run；“已修复”指当前源码的相应问题已修复，不改变该 run 的失败结论。

| 失败 run / 提交 | 当时问题 | 对应修复 |
| --- | --- | --- |
| [35578834478](https://github.com/kongbu0621/infra-local-hand/actions/runs/35578834478) / `3a8591c` | Windows 错用 Linux bootstrap | `c8176b0` |
| [35594194058](https://github.com/kongbu0621/infra-local-hand/actions/runs/35594194058) / `a1bc0eb` | bootstrap 与 `.gitignore` LF/CRLF 夹具不一致 | `c8176b0` |
| [35600713655](https://github.com/kongbu0621/infra-local-hand/actions/runs/35600713655) / `03a78e2` | bootstrap 与换行转换造成构建夹具非干净 | `c8176b0` |
| [35711147672](https://github.com/kongbu0621/infra-local-hand/actions/runs/35711147672) / `b12e9c0` | bootstrap、构建与冲突断言的 LF/CRLF 差异 | `c8176b0` |
| [35746249867](https://github.com/kongbu0621/infra-local-hand/actions/runs/35746249867) / `d500384` | 同前一组，5 项失败 | `c8176b0` |
| [35757160205](https://github.com/kongbu0621/infra-local-hand/actions/runs/35757160205) / `f109a4d` | 临时裸仓清理 `ENOTEMPTY` | `b0b37cd` |
| [35769636440](https://github.com/kongbu0621/infra-local-hand/actions/runs/35769636440) / `11225c1` | Windows wheel 校验混用 stat/fstat 的 ctime 语义 | `1921ea1` |
| [35900165257](https://github.com/kongbu0621/infra-local-hand/actions/runs/35900165257) / `3b309c2` | Windows 收集时 `NOW` 未定义 | `d117cbe` |
| [35936686250](https://github.com/kongbu0621/infra-local-hand/actions/runs/35936686250) / `6e1a25b` | 合成 Linux FD 数据错误使用 Windows 常量 | `273eb0a` |
| [36222011920](https://github.com/kongbu0621/infra-local-hand/actions/runs/36222011920) / `303f9ca` | 负例未接纳真实 `O_NOATIME` 的 EPERM | `2ea59b8` |
| [36285458941](https://github.com/kongbu0621/infra-local-hand/actions/runs/36285458941) / `1b7d178` | Windows 错收 Linux 恢复测试，入口提前调用 Linux 时钟 | `eb8a54a` |
| [36288350559](https://github.com/kongbu0621/infra-local-hand/actions/runs/36288350559) / `9a55632` | Windows 收集 CPUQuota 测试时导入 `fcntl` | `15af5f1` |
| [36291609770](https://github.com/kongbu0621/infra-local-hand/actions/runs/36291609770) / `15af5f1` | Windows 恢复边界；Linux 对只查元数据的祖先要求 `O_NOATIME` | `eb8a54a` |
| [36313382679](https://github.com/kongbu0621/infra-local-hand/actions/runs/36313382679) / `8fd8452` | 可执行文件／collector 属主夹具；Windows `fcntl` | `3d9b9ff` |
| [36317652508](https://github.com/kongbu0621/infra-local-hand/actions/runs/36317652508) / `f1814b2` | 上述夹具；Windows 导入时读 `/proc` | `3d9b9ff` |
| [36324126279](https://github.com/kongbu0621/infra-local-hand/actions/runs/36324126279) / `0a456a9` | 上述夹具加 home ACL；Windows Linux 依赖 | `3d9b9ff` |
| [36331451304](https://github.com/kongbu0621/infra-local-hand/actions/runs/36331451304) / `ad40550` | Linux 21 项失败、Windows 6 项收集错误 | `3d9b9ff` |
| [36385294117](https://github.com/kongbu0621/infra-local-hand/actions/runs/36385294117) / `14d19f1` | 同组 ACL／属主夹具与平台收集错误 | `3d9b9ff` |
| [36391489578](https://github.com/kongbu0621/infra-local-hand/actions/runs/36391489578) / `4c1285a` | Linux 固定来源等 55 项夹具失败；Windows 6 项收集错误 | `317b09f`、`411a9f0`、`3d9b9ff` |
| [36392913200](https://github.com/kongbu0621/infra-local-hand/actions/runs/36392913200) / `317b09f` | `/opt` 下新夹具继承 ACL；Windows 收集错误 | `411a9f0`、`3d9b9ff` |
| [36393186487](https://github.com/kongbu0621/infra-local-hand/actions/runs/36393186487) / `411a9f0` | 剩余 Linux 21 项夹具失败、Windows 6 项收集错误 | `3d9b9ff` |
| [36409235607](https://github.com/kongbu0621/infra-local-hand/actions/runs/36409235607) / `7779266` | 同前一组 | `3d9b9ff` |
| [36546965469](https://github.com/kongbu0621/infra-local-hand/actions/runs/36546965469) / `7e80268` | pytest 参数 ID 使 Windows 环境变量超过 32767 字符 | `24b5536` |
| [36586633992](https://github.com/kongbu0621/infra-local-hand/actions/runs/36586633992) / `78fc0a3` | 另一组 pytest 大参数 ID 超出相同限制 | `d4dd8c6` |
| [36684496707](https://github.com/kongbu0621/infra-local-hand/actions/runs/36684496707) / `6ec995e` | Windows 路径分隔符导致夹具字典 `KeyError` | `21a2646` |

`35757160205` 的直接事实是 `ENOTEMPTY`。历史 Trace2 及回归验证了 Git 自动维护
后台写入入口并修复，但该次 CI 的具体 writer 未被采样，不能把候选归因写成已直接证明。
平台边界修复保持可移植合同用例；Linux 专属用例由 Linux 执行，root collector
仍在独立强制步骤要求至少 16 PASS、零 SKIP／error／failure。没有以跳过代替通过。

## 2 次已退休实验的失败

| Run / 提交 | 保留事实 | 当前处置 |
| --- | --- | --- |
| [36577764454](https://github.com/kongbu0621/infra-local-hand/actions/runs/36577764454) / `6b085d9` | 账户参数错误，probe 与六案未运行，原清理 UNKNOWN | 参数在 `9596c78` 修复；历史清理未知保留 |
| [36662298613](https://github.com/kongbu0621/infra-local-hand/actions/runs/36662298613) / `9d8328c` | C1 身份证据缺失、原报告 UNKNOWN，收件 REJECTED | 未取得实验资格；不是普通 CI 测试失败 |

两者所属路线在 `8b72306` 已退休，工作流 job 禁用，第三轮未派发。
本核查不恢复实验、不新增轮次，也不把本次普通 CI 通过当作实验通过。
原件摘要、历史修复与归因限度仍见原实验复核文档。

## 本次新修复：PR 分类漏检

直接执行原 workflow 的分类 Python，构造实际临时 Git 历史：PR 先增加
`tools/local_hand/` 代码，再提交文档。旧分类器只比较 synchronize 的
`before..after`，输出 `runtime_changed=false`，使累计仍含代码变更的 PR
跳过 Linux／Windows 检查。起始 `main` 的 push 始终执行完整检查，未受此问题影响。

修复保持既有工作流与测试范围：按事件中的准确 PR base/head 计算 merge-base，
每次检查整个 PR 累计差异；不使用会前移的远端分支代替事件基线。文件名使用
NUL 分隔原始路径，并关闭重命名折叠，覆盖中文路径与移出受测目录的旧路径。
无法确定比较范围时继续完整验证。main push／手动普通验证仍必须指向准确 main。

回归直接从 workflow 提取实际分类脚本，在隔离 Git 仓库中运行；覆盖累计代码后
补文档、纯文档、基线前移、无法解析基线、中文路径、移出受测目录，以及 main
push／手动触发。修复同时保持 PR whitespace 比较与事件基线一致。
本次只调整验证装配，不更改产品运行代码、平台保护合同或已批准 A 文档。

最终相关测试 **76 PASS**；独立分类复核 **7 PASS** 是其中子集的重新执行，不累加。
累计代码后补文档、中文路径、移出目录这三个新增真实 Git 回归在旧 workflow 上
均实际失败，在修复后通过。另在工作树外验证不可解码路径进入完整检查。
Python 语法、diff whitespace、27 个报告链接与清单覆盖一致性检查通过。
本地结果不替代真实 Windows CI。

本文件及相邻清单绑定发布前快照；本次新修复的原生 CI 结果以包含修复的准确
提交关联运行记录为准，不把起始 `21a2646` 的成功沿用为新提交结果。

真实 systemd 隔离验收、完整 Q2／E3 与生产启用状态不由 CI 绿灯关闭。
