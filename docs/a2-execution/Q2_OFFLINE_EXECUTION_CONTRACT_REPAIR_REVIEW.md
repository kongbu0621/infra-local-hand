# Q2 离线执行合同与证据读取修复复核

2026-10-02 +08:00。按本次“按照你的建议，开始搞”继续本地修复和离线合同验证。
这是工作区修复及证据记录，不是新 Gate、现场授权或现场验收。

## 范围与源码身份

Q2 使用既有 CLOSED `LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-v1` 的 P1–P3
离线实现、非执行模型及 P4 合同复核范围：R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，A
`68424df2ddbf812b9479ffa7a64dcaa59a2a9f76`，B
`LH-Q2-OLD-PRODUCER-ADMISSION-RETRY-CLOSURE-20261002-01`，独立 C
`179652cb9487163d83c004d358e4d4b49409694c`。执行者本轮已直接读取固定 R；
没有采用公开 excerpt 替代该来源。ResultReader 和 evidence-client 的字节完整性
修复属于已经 CLOSED 的 E1–E3 本地源码开发范围。

验证快照创建时 Git HEAD 为 `50c5590995fc75ca68e2970730b9384a5b816302`，Git 核验 C 是
其祖先。当时修改仍在工作区，未形成新的已提交 D，不能把该 HEAD 当作包含本轮修改的
候选。最终变更源码的大小与 SHA-256 见
[验证索引](evidence/q2-offline-contract-repair-20261002/validation.json)。
A 的三份文档、Owner 决定、历史失败和既有 partial prototype 保持原字节及原语义。
固定现场产品 `1a900e4a38e9567655f21cbf3c3f17941de1a8d5` 及其 artifact pins 不变。

## 修复行为

- mountinfo consumer 在 `nsfs` 的 root 字段识别合法 namespace inode 表示，例如
  `mnt:[4026531840]`；mountpoint 和其它文件系统 root 仍须满足原绝对路径约束。
  所有行仍参与包含挂载选择，覆盖 parent 的 nsfs 挂载不能被跳过或当作 ext4 资格。
  该 root 表示可从固定的 [Linux v6.8 nsfs 源码](https://github.com/torvalds/linux/blob/v6.8/fs/nsfs.c#L235)核对。
- ResultReader 在第一次有界读取和身份核验后，用原 fd 复读并逐段比较字节，随后再次
  核验 file/name/root 身份。复读沿用原 deadline 与原长度上限；不因时间戳相同而接受
  同 inode、同大小的改写。额外 IO 消耗原预算，不刷新期限。双次观察不提供原子快照。
- ProtectedFiles 的既有内容漂移测试接受两种准确拒绝原因：metadata 变化或字节变化；
  chmod 子例仍要求 metadata 错误。新增只模拟目标文件 mtime/ctime 精度相同的负例，
  真实 inode、大小和字节保留，明确要求 `RECONCILIATION_CONTENT_CHANGED`。
  临时夹具支持已有 `LOCAL_HAND_Q2_TEST_PARENT`，祖先保护检查不放宽。
- evidence-client 在首次完整校验和所有持久化屏障之后，重新定位并通过同一 held final
  fd 有界复核完整摘要，再核验目录绑定，防止同步期间同 inode、同大小改写通过元数据
  比较。新建与恢复 final、file/download/root 三处 fsync 的确定性反例均拒绝成功并保留
  损坏文件。保留既有 validator、create-only 发布、上限及错误清理语义。

## 纯离线模型

新增 `protocol`、`accounting`、`offline` 三个辅助模块及反例测试，均以显式提供的
合成数据计算，不采样真实时钟、不访问文件/进程/网络、不创建 marker 或发行权限。

HELLO→BIND→READY 验证原双钟、固定顺序、guest boot/nonce、外部 intent/package
摘要、1 ms 向下取整与 2 秒 margin；owner 截止保留 120 秒上限和独立的
stop/EOF/fsync/seal 余量。不同机器的时钟原点不作数值比较。

intent fixture 绑定批准链、固定产品、独立包、helper/bootstrap/SSH argv 摘要、
locator/context、普通身份及完整 groups、原始 window、预算和证据上限；本体不包含自身
摘要。P4 引用只允许显式未发行的 `SYNTHETIC_` fixture，不能替代真实 stable event。
严格事件顺序分别保留 `LOCAL_BLOCKED_UNCONSUMED`、`CONSUMED_PARTIAL`、
`BLOCKED_RETAINED`、`REMOTE_UNKNOWN_CONSUMED`，禁止第二通道、重放或失败补连。

账本保留旧完整未释放承诺；按物理身份去重并按设备计费，既有 actual 不成为 free 的
第三个加数。12 个旧计划目录、7 个 root、ordinary slice 和 `12051..12057` 的缺项或
未知都阻断。新 record/archive/metadata 不得别名到任一已有 observed allocation。
父基数、覆盖和峰值未知保持未知，不能填零。partial/final 是同一 archive 的状态峰值。

集成模型将 parent 与外部 locator/context 绑定，逐阶段核验 archive allocation 上限，
将最终 inode/allocation 与写回执绑定。写前分别预留完整 64 KiB / 4 inode record
子额度，以及 manifest 最大 archive 分配加合成 parent 增长与同步开销；较小的观测文件
不能缩减预留。两者仍属于唯一 capture 20 MiB / 384 inode ceiling，各设备还要通过
available 检查；补加和总量保留 `2**63-1` 整数边界。

最后 evidence 帧分别验证完整 header+payload、逻辑长度和 SHA-256；写模型要求
排他打开、0600、file/parent fsync、同 fd pread 长度/摘要、名称重绑定、准确身份、
nlink/ACL/分配量。失败保留固定名称和原消费状态，不能因 archive 未新建而退回未消费。
这些是合成回执，模型不验证真实 ZIP 内容或真实文件系统持久性。

独立复核发现并修正了 inode 别名、复读摘要缺失、错误未消费状态、完整未来预留遗漏及
整数溢出问题。集成 API 重新计算外部绑定，而不是信任调用者自报的验证结果。

## 验证与环境

项目要求 Python ≥3.12。本机系统仅有 3.10/3.11，因此在私有临时目录编译官方
[Python 3.12.14](https://www.python.org/downloads/release/python-31214/)，原 xz SHA-256
`5c8462af5790baf43a321a1559dbe0db06d1be4300fb85fb53c40060668e548a`。
隔离 venv 安装原 `requirements-build.txt` 的锁定版本，pytest 8.4.2；
SQLite 3.37.2 使用原系统共享库及官方同版本 headers。没有系统包安装、全局 pip、
Snap/sysctl/AppArmor/bubblewrap 配置修改或仓库依赖修改。

| 验证轮次 | 准确结果 |
| --- | --- |
| Python 3.10 初步 smoke | 原 root offline 测试 62 PASS / 1 FAIL；仅测试错误标签断言不符，已改为严格整数错误；不算支持环境验收 |
| Python 3.10 代理 smoke | consumer/protocol 157 PASS；accounting 初版 75 PASS、别名修补后 77 PASS；均不算支持环境验收 |
| Python 3.12，首次沙箱定向 | 324 PASS / 1 SKIP / 31 FAIL |
| 原宿主普通身份，临时 umask 0077，六组定向 | 355 PASS / 1 SKIP |
| 最新源码，临时 umask 0022，含 ResultReader broker/runner 的八组定向 | 386 PASS / 1 SKIP |
| 独立代理，普通沙箱，三组最终纯离线模型 | 266 PASS / 0 SKIP / 0 FAIL |
| 首次全库，umask 0022、TMPDIR=/tmp | 3709 PASS / 89 SKIP / 1 FAIL，434.40 秒 |
| 证据发布原源码定向复现 | 新 final 1 FAIL / 恢复 final 1 PASS；新增强制时间戳碰撞反例在修复前也 FAIL |
| 证据发布修复后定向 | 3 PASS |
| 最终 evidence-client 与 evidence store | 96 PASS / 0 SKIP / 0 FAIL |
| 最终全部源码，umask 0022、TMPDIR=/tmp | **3713 PASS / 89 SKIP / 0 FAIL，436.84 秒** |

首次沙箱 31 项失败发生在保护检查：沙箱根祖先 UID 映射为 65534，且继承 umask 0002
使旧夹具文件组可写，拒绝与生产合同相符。随后在原宿主普通身份和仅该进程的适用 umask
下验证临时文件；没有修改保护规则或宿主设置。chown 专项仍因缺 root 而 SKIP。

全库唯一失败为
`ClientTests.test_new_final_keeps_verified_identity_through_all_durability_barriers`：
同步回调改写同大小文件后未得到期望的 `EvidenceError`。保留这个失败，不记为全库通过。
该次全库收集先于离线模型最后两项整数边界反例；最新模型由独立 266 项及最终定向验证
另行覆盖。初期相邻三项诊断均通过，它们不替代失败用例的复现。

最后全库复验覆盖最终 13 个变更源码的固定摘要。运行期间与结束后摘要一致；
`git diff --check` 通过。89 项 SKIP 分别保留原因，包括实际 root/manager 夹具、
systemd 255 共享库、真实监督环境及未安装的可选 MCP extra；不把它们转换为 PASS。
Windows 未在本轮执行，本轮不增加 Windows 验收结论。

日志与 JUnit 原件留在本次私有本地验证目录；公开索引只存摘要、统计、失败节点和源码
关联，不包含机器原始证据、连接资料或绝对机器路径。本轮本地修复与离线验证完成。
索引中的工作区状态描述该验证时点；随后提交的准确身份与资格复核另行记录，不覆盖历史快照。

## 保留的现场结论

所有模型返回 `field_ready=false`、`allow_run=false`、`guest_executed=false`、
`normal_chain_executions=0`；完整未来包合同和 P4 qualification 也保持 false。
合成正常链只记 modeled count，不增加真实正常链计数。

H07 全运行期 rate/pause 与独立远端 stop、双 parent 文件系统/峰值/持久资格，以及原
host terminal 与 proc/PID namespace 对齐仍未证明；`E3_SUPERVISION_UNVERIFIED`
不能由源码或合成 PASS 清除。退休的 native cgroup spike 未恢复。
本轮没有 `TASK.txt`、可执行现场 ZIP、host 消费对象、guest 连接或现场运行。
后续现场工作仍须按既有批准文档闭合实际资格并取得准确独立 P4 event；本复核不代替它。
