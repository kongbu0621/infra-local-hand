# PP1 原核心接续实现与返回

授权为 [persistent-path baseline](../governance/Q2_CORE_PERSISTENT_PATH_CONTINUATION_BASELINE.md)，
Owner 事件 `LH-Q2-CORE-PERSISTENT-PATH-CONTINUATION-CLOSURE-20261010-01`。
准确 A 三文档原字节保持，独立 C 为 `d77315e5792c54c406b000b2179ef179ec900c94`。
本实现直接下降自 C；本节是实现记录，不是现场成功或核心验收。

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
