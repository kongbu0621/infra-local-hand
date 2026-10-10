# IR1 冻结、IR2 返回与运行准备修复

## 批次与准确发行

Owner 已一次批准 `LH-Q2-CORE-IDENTITY-RESOURCE-CONTINUATION-v1` 的 IR1–IR3，
准确 A `e16b9038eb825f06306a6fe94bc2be30cc418238`，
R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，
独立 C `f74725156ed0fa5bfc1c9760ca9efd1afd110870`。
A 三文档原字节、历史 OPEN 标签及 Owner 原始决定均保留。

最终 D `29df25577aa848b4fa6264bd539692d0a2fa6386` 沿 C 后继发布，
[PR #13](https://github.com/kongbu0621/infra-local-hand/pull/13) 正常 merge 为
`e24aa744767c62214c54db621001f7105a04fe5c`，没有 squash 或主分支直接推送。
准确 D 的首次 CI `38073250220`、attempt 1 三项成功：

- Linux 7710 passed / 89 skipped；另行强制 root collector 16 PASS / 0 SKIP；
  独立安装 94 checks / 292 commands PASS。
- Windows 1979 passed / 1389 skipped；对应平台独立安装 10 checks / 10 commands PASS。
- 本地准确 D 的独立安装为 94 checks / 292 commands PASS。

此前候选 `e389448c2b13d9a31087047b6d228cce40812ae2` 的首次 CI `38072347999`
实际失败：Linux 1 failed / 7709 passed / 89 skipped，Windows 成功。
失败为测试仍断言已明确复核的 dispatcher 未发行；后继只修正测试和说明，生产字节
未变。保留旧失败；它不是并发取消，也没有用重跑替换首次结果。

私有归档固定 19 成员、798720 B，实际分配 806912 B / 3 inodes；保护源码 13 文件，
686641 B，实际分配 724992 B / 16 inodes。准确源码、两次维护载荷上界、独立核心包、
全部历史来源/费用、FD 生命周期及私有调用返回路径均已验证。FD 交接上界 128、
核心准备 126、guest 98，保留当前 256 上限。原始核心任务与 Q1 参数不变。
IR1 最终冻结 79635 B，绑定十二个 caller/依赖摘要；IR1 COMPLETE。

## 唯一维护返回

唯一 `lhqjgrow-20261011a` 通过一次本地 preflight，并在同窗调用 execute 一次。
消费 marker 已创建，发起一条 pre SSH；execute 退出 3，
`STOP_AND_RETAIN / GROWTH_REPORT_MISSING`。
已保存的 guest 失败记录为 `PRE_RUNTIME_PREPARATION / GROWTH_RUNTIME_LIMITS`。

runtime preparation 已进入；固定 `guard_units` 和 `system_before` 两个命令均返回 0，
各自 stdout/stderr 均 EOF。五份已核对配置全部 `created=false`；未创建目标配置，
未调用启动步骤。没有发出关机令牌、创建备份、扩展 journal、重启 VM 或发行核心包。
host 累计 CPU 2471402002 ns、RSS 157347840 B；该返回没有触及当前管理资源上限。

保留五个实际原件：marker、events、空 pre stdout、8137 B 的 pre stderr、receipt。
post 两流、维护 pidfile、备份不存在。原件、原件索引、完整私有诊断、机器元数据、
调用输出与源码归档均不发布。

实际 caller/coordinator 退出 3，custodian 退出 0；caller 双 EOF 只证明本地返回收齐。
host 的传输诊断未确认 stderr EOF，远端退出仍为 UNKNOWN，不能从已捕获的完整 guest
失败 JSON 推断远端完成。无完整维护成功证明，IR3 条件未成立。

IR2 为 CONSUMED_FAILED / STOP_AND_RETAIN；IR3/H01/Q4/H11 全部 NOT_RUN。
原冻结与十二个摘要保持不变，另存终态
`IR2_MAINTENANCE_CONSUMED_FAILED_IR3_NOT_RUN` 阻止两个 caller 重放。
现有十五次维护消费，旧09c/旧10b仍为调用过但未消费的 preflight；全部十七份完整
维护义务保留。总计 23079 MiB / 6834 inodes，维护前置 22951 MiB / 6802 inodes，
不退款。本次批准不允许失败后的重试、补采、恢复、清理或另开窗口。

## 已保存返回定位出的普通修复

故障不是资源使用超限。固定 ordinary slice 的配置文件已由保护读取确认缺失；
`system_before` 却返回 loaded/inactive/dead、空 FragmentPath/DropInPaths/ControlGroup/
InvocationID、无 PID/Job/User、Delegate=no，四项资源属性全部 infinity。
旧 `_runtime_properties` 只把 not-found 识别为待配置状态，因而在原本已批准的
配置创建之前错误地要求配置后的有限值。

systemd 上游实现支持这一形状：[slice_load](https://github.com/systemd/systemd/blob/v255/src/core/slice.c#L155)
允许缺少 fragment；[公共加载函数](https://github.com/systemd/systemd/blob/v255/src/core/unit.c#L1330)
在 fragment 非必需时将未定义单元标为 loaded。这里的现场判断来自本次保留返回，
未借此推断其它单元或进行新查询。

普通修复只在两个固定准备目标已确认配置缺失时接受上述空、inactive/dead、默认值
形状，继续原有配置创建、daemon-reload 和启动。存在配置、活动状态、外来 fragment/
drop-in、cgroup/invocation、Job/PID、用户、委派或混合资源值均不能使用此路径。
管理器检查、启动后的四项有效限制、内核 cgroup 限制和身份复核保持严格。
不增加命令、读取、目标、上限或功能；dispatcher 发行摘要未变。

直接读取已保存且 SHA-256 核对的 system_before 片段，使用冻结 D 的真实函数重现
旧 GROWTH_RUNTIME_LIMITS；修复后仅“配置缺失的准备前状态”通过，相同值仍被正常
有效限制检查拒绝。此复现没有现场查询。运行准备完整生命周期及拒绝路径共 81 项
通过；含维护报告、核心身份消费者、资源上限和诊断的相关离线回归 248 项通过。
这些验证只证明普通源码修复，不恢复已消费的 IR2，也不构成核心 PASS。
