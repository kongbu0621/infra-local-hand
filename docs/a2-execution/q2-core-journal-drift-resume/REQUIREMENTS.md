# Journal 一致性诊断修复后的单次维护接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-JOURNAL-DRIFT-RESUME-v1`，仅 DR1–DR2。
沿用 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、Owner mandate/authority、无例外及
准确 A→Owner B→独立 C→D 顺序。本文、[架构](ARCHITECTURE.md)和
[计划](IMPLEMENTATION_PLAN.md)是本次待决三文档。

## 已完成与未完成

目标仍是 journal 256→512 MiB 扩容，解除 Local Hand 核心验收的前置容量阻塞。
[W2 返回](../Q2_CORE_JOURNAL_SCAN_WORK_FIELD_20261007.md)记录 checkpoint 1 的
`PID_RECHECK` / `GROWTH_PROC_DRIFT`；窗口已消费，marker false、SSH0、维护未开始。
初列 594、已完成 419 个 PID，task 开始/完成均 1549，114545 FD stat、137564054 B maps
是失败前缀，不是全量需求。
具体重复枚举、task 集合或 PID starttime 分支仍 UNKNOWN；不得猜测某个进程或正常线程活动。

诊断修复 `711932aae3370c7f2ed5c1a51ac82d3b0f67a6e5` 已发布，准确 CI `37569620992`
attempt 1 为 3/3 success；云端相关回归 773 passed/3 skipped、本地不同命令回归
663 passed/0 skipped，十二源成员及八份原静态输入已核对。两组计数不合并。
详见 [修复与本地复核](../Q2_CORE_JOURNAL_DRIFT_DIAGNOSTICS_REVIEW_20261007.md)，
登记提交 `d8c079302717452711251a83d642e5b9ed9fb21e`。
修复只区分原拒绝条件，不改变接受集合；诊断和离线核验不再重复开发。

## 唯一新增权限

DR1 将本范围准确批准绑定到最终候选并验证、发布、通过准确候选 CI、冻结之后，DR2
允许沿用 `lhqjgrow-20261006a`、原对象、原八输入与原终端，**再一次替代预检窗口**。
预检全部通过即在同一窗口完成尚未消费的原维护，不另拆诊断试跑或另开执行窗口。
旧窗口全部保持消耗；无 marker、代码修复或 CI 成功不返还次数。

继承 scan-work A `42a66be98c45e817e866d3fb86a1c184c2ce55f9` 的全部现行边界，以及它
继承的 maps、终端认证、宿主读取和原扩容要求。本提案只新增上述一次机会及其来源绑定；
不替代旧批准字节，不改变扫描一致性策略、覆盖、预算、协议、认证或维护动作。

- 固定 root writer 继续使用 Owner 已有真实前台终端的 sudo；coordinator 保持普通身份，
  密码只交控制终端，不新增 helper、权限、sudo 预热、服务配置或安装。
- 保留每个 PID/task、FD 身份/fdinfo/snapshot、maps 与最终集合复核；任一漂移仍拒绝。
  不关闭宿主应用凑稳定，不跳过 task、不缓存、不去重、不增加检查重试。
- 原双时钟 900s 总窗、780s 后不启新修改、每 writer 15s（含认证）、八个串行检查点
  各一次保持。窗口开始即消耗，失败不退款、不重连、不补采、不自动另开窗口。
- 原全部历史用量、承诺及 UNKNOWN 保留；累计维护最多一个 marker、两条固定 SSH，
  正常关机、完整备份、镜像增长、VM 启动和 ext4 增长各一次。不强杀、清理、回滚或恢复。

成功仍须完整备份、原身份/内容保留、两层增长与普通可用至少 400 MiB/32768 inode，
获得原合格 receipt 才记 `JOURNAL_GROWTH_VERIFIED`。失败保留本次首因、已取得前缀、
真实退出与动作次数；不追补历史 UNKNOWN，不把 scan_complete 当父层 writer 准入。

本次可能仍因一致性、期限或其它原门失败，**不保证通过**。本范围不执行新 boot 核心
采用或 H01/Q4/H11；其真实接线缺口仍在原 scan-work 计划中，不能用旧包直接续跑。
namespace/watchdog、部署及其它支线暂停，生产 E3 仍未验收。
