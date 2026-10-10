# PP1 原核心接续实现与返回

授权为 [persistent-path baseline](../governance/Q2_CORE_PERSISTENT_PATH_CONTINUATION_BASELINE.md)，
Owner 事件 `LH-Q2-CORE-PERSISTENT-PATH-CONTINUATION-CLOSURE-20261010-01`。
准确 A 三文档原字节保持，独立 C 为 `d77315e5792c54c406b000b2179ef179ec900c94`。
本实现系列下降自 C；本节是实现记录，不是现场成功或核心验收。

## 最小实现

PR #4 的准确修复 `47183cc310cbab15cf78bdb8f3f26cc935c1fb66` 已经正常 merge commit
合入 main，合入提交 `48a5ba15bc61ad930fbea60bfda740aa2db4e4dc`。
A/C 通过 PR #5 正常合入，合入提交 `1bc2122055f0f860cc1350984b92678f3986a106`。
未直接推送 main，未使用管理员 override，未 squash C 与实现。

固定外层归档采用旧 activation 完整字节、旧10c五个实际原件及冻结/终态/完成记录，
共 12 成员、522240 B，在原 524288 B 上限内。只替换原 activation 输入 FD；
旧55原件的 custodian、连续持有协议与 128 FD 上限保持。归档只在内存按固定
USTAR 顺序消费，不解包到文件系统。原 coordinator 3/custodian 0、UNKNOWN、
缺失 post 原件及 H01/Q4/H11 NOT_RUN 均保留，不能解释为新维护成功。

新 manifest v18 通过归档内固定前代 marker 的 `manifest.resume` 及准确摘要引用
完整旧历史；仅一层引用，重建后的 canonical 内容与完整逻辑历史逐字比较。
receipt v18、preflight v17、transition v17、capacity v20、reconciliation v21
及独立 dispatcher 同步更新。旧10a消费者明确使用旧历史格式，避免新字段污染旧证据。
为保留 host 源码原 98304 B 上限，仅将纯 preflight 编解码移入既有 prior 模块。

十六份完整维护义务、两次路径读取及全部准备费用、原核心合计 20809 MiB/6224 inodes；
无退款。两次路径读取原件在原处保持，不进入外层归档或55-FD custody。
NAS discovery/new-job admission 继续关闭，未增加外围功能或现场观察。

## 发布前验证

实际留存输入的离线生命周期验证通过：19 个输入、55 个旧维护原件、20 个旧核心
原件、4 个诊断原件及4个容量原件；无 VM/SSH 查询。工作区版本的静态上界为
marker 52179 B、receipt 44848 B、pre/post argv 47676/52204 B、guest FD 98、
维护交接峰值128、核心准备126。准确 D 冻结后仍须复核，不以此替代最终发行门槛。

归档篡改、错误来源/完成/历史、缺失/循环引用、两个完成消费者及完整费用有离线
回归覆盖。两个新私有调用器的实际结果写入与门控经18项合成测试通过，包括已有
diagnostic 的完整保留、create-only 拒绝重复、一次 preflight/PASS 同窗 execute、
独立完成消费者后才生成 PP3 可执行门控。旧调用器保持不变。

首轮完整 Q2 检查为5123通过、88跳过、8个旧测试输入/断言失败：它们仍将新压缩引用
直接作为完整 resume。已修正测试为从固定前代还原或使用已验证逻辑输入，不改变
生产校验。全库回归、准确 D 首次 CI、独立安装、最终来源准备和双调用器冻结尚待完成。
归档准备脚本初次加载因错误的 Inputs 模块定位停止，尚未访问原件或创建准备池；
修正后一次实际准备完成，原错误记录私有保留。没有因此创建新现场窗口。

首个本地实现提交 `eb8384174253d21b8731d3b01fb0aa8148b3676e` 的真实准确来源核对
在 `GROWTH_DEPENDENCY_CHANGED` 停止：维护入口仍将 `q2_core_obligation_inputs.py`
与旧版本比较，无法采用已批准的 PR #4 分类修复。该单个依赖现在准确绑定到
`47183cc310cbab15cf78bdb8f3f26cc935c1fb66`；其他固定依赖和完整 A/C/D 校验不变。
此发现来自保留来源与 Git 字节，无新现场观察。原本地提交/失败日志保留，尚未推送
实现 CI 或消耗 PP2。独立 wheel 构建改在准确提交的隔离 checkout 完成，保留用户
工作区的既有未跟踪条目，不改动构建器的 clean-source 要求。

此记录版本：PP1 IN_PROGRESS，PP2 NOT_ISSUED，PP3/H01/Q4/H11 NOT_RUN。
只有完整 PP1 后执行本批唯一10d；其完整成功原件及实际 coordinator/custodian
完成通过独立校验，才发行原未发行07a。失败/未知立即停止并保留，无重试或补采。

## 最终 PP1 冻结

最终 D `a3f9dbeca268de80124f524ccee4f1437bd61784` 下降自独立 C，保留初始实现
`eb8384174253d21b8731d3b01fb0aa8148b3676e` 及真实来源核对失败。PR #6 通过正常
merge commit `e8868806dfc9ef413177420eb1157bcd4131da07` 合入 main。
其自身首次 CI [38052327972](https://github.com/kongbu0621/infra-local-hand/actions/runs/38052327972)，
attempt 1，head 为准确 D，三项全部成功；没有用 rerun 替换首次记录。

- Linux：源码7612通过/89跳过，独立 cgroup fixture 另有16项通过；独立安装94项
  检查/292条命令通过。Windows：1940通过/1384跳过，独立安装10项检查/10条命令通过。
- 本地完整回归7561通过/140跳过；这是依赖 pin 修正前的实现，最后唯一源码差异
  另经54项针对性检查、准确 D 真实来源验证以及上述准确 D CI 覆盖。
  本地准确 D 独立安装94项检查/292条命令通过；最终私有调用器18项合成检查通过。
- 准确 D 的实际留存输入、归档/历史、两个完成消费者、完整 FD 生命周期和大小/费用
  上界核对通过。维护交接峰值128、核心准备126；synthetic transition 53861 B、
  approved input 438037 B、核心包上界19480174 B，原限额不变。未提前创建核心现场包。
- 最终13个受保护来源副本准备占704512 B/16 inodes；固定归档准备占532480 B/3 inodes。
  两个池均在各自原1 MiB/32-inode及 CPU/RSS/时间预算内。原件和旧准备费用不退款。
- 42437 B 的私有 `pp1-freeze.json` 绑定12个调用器/依赖、批准记录、准确提交/CI/安装、
  固定出站槽、全部来源、两次路径读取原件核对及预算。旧文件不改，两个新调用器冻结。

PP1 完成；以下是冻结后的唯一 PP2 实际返回，不将准备成功解释为维护成功。

## 唯一 PP2 返回与终态

新 `lhqjgrow-20261010d` 调用器只调用一次。一次 local preflight 返回
`LOCAL_PREFLIGHT_PASSED`，随后同窗 execute 一次；新 marker 已创建，pre SSH 请求为1。
execute 返回 `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`，调用器实际 exit 3。
实际 coordinator completion 为 returncode 3，custodian returncode 0；receipt 摘要绑定一致。
聚合完成用量为 CPU 2280254000 ns / RSS upper 157270016 B，在原上限内。

已捕获 guest stderr 与本次 nonce/source/session 绑定，其 failure 为
`PRE_RUNTIME_PREPARATION / GROWTH_PATH_PROTECTION`；已有诊断完整穿过
receipt、调用结果和 summary。persistent_inventory 的 path_index 73、component_index 3
均为零基，operation 为 `qualify_component`，对应最后一级对象。该对象已打开并进入
既有 fstat 后的所有者/写权限谓词；errno 为 null，实际 UID/GID/mode 未记录，不能
判定是所有者集合不符、group/other write 位，或二者。它不是 ENOENT 返回。

guest `actions_started` 为 runtime_preparation；已完成的 guard_units 命令有 exit 0/
双 EOF。其余配置/目录/父域/池/manager 记录为空，不能据此声称准备完成。失败时
stderr EOF 为 false，remote_exit 为 UNKNOWN；不以 guest 自述或 custodian 0 冒充远端成功。
未发送 poweroff token，未备份/增长 journal，未维护重启，未发行原核心包。

实际五原件：marker、events、空 pre stdout、pre stderr、receipt。post stdout/stderr、
maintenance pidfile 和 journal backup 均不存在；没有伪造补件。五原件、大小/摘要索引、
caller stdout/stderr、实际退出及终态均私有保留。原 immutable freeze 与12个哈希保持；
另写 `PP2_MAINTENANCE_CONSUMED_FAILED_PP3_NOT_RUN` 终态 gate，阻止两调用器重放。

当前 PP2 **CONSUMED_FAILED / STOP_AND_RETAIN**；PP3/H01/Q4/H11 **NOT_RUN**。
维护已消费代数为14；old09c/old10b仍为调用过但未消费的预检。16份完整维护义务、
原核心、读取与准备费用全部保持20809 MiB/6224 inodes，不退款。本次没有平台审批拒绝。

## 仅保留来源的后续定位

只用本次已保存 marker/guest 返回，将索引、长度、摘要定位到原配额边界证据对象的
最后一级；未读取当前 guest 元数据。随后校验原六个固定 archive/26个准确文档和两个
原计划/准备文档，得到九个准确引用：七个 plan 的 `retained` 项及原 before/after 根身份。
这证明它属于原来明确保留的证据，不是 PR #4 修正的两个未发行位置；不能将该修复扩大为
删除此必备对象。上述旧根身份只有原路径/device/inode，不能填补当前 UID/mode 的缺失。

该离线来源核对已完成，私有映射保留。没有额外 SSH、探测、chmod/chown、权限放宽、
服务停止、清理、回滚、恢复或新窗口。已获批实现修复和准备均已交付，但核心仍未跑通。
本批失败即停止的边界不允许另读当前权限或再次执行；下一现场动作需要另一个准确、
有界的 Owner 决定，不能从本次测试、CI、普通修复或旧“批准”中推导新窗口。
