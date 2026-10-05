# 核心 host 容量边界实现与单次验收

2026-10-05 +08:00。本记录对应已批准的 `LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1` B1–B3。
**当前终态：B1/B2 已交付，B3 单次请求已消费并 STOP_AND_RETAIN，不能重试。**
真实 HELLO、BIND 和包发送完成；guest 准入返回 `CORE_ADMIT_SUDO_OUTPUT`，没有业务结果包。
下文前期只读检查的未消费状态是历史检查点，最终现场结果见后两节。
容量条件只证明采样时普通 writer 可用量满足两项 core 承诺；更早 host 承诺仍 UNKNOWN，
完整 host 历史准入与排他空间预留均为 false。生产 E3 限制和暂停支线不变。

## 准确授权与实现

R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 已直接读取，完整性沿用根声明。
A `f491b15514ed0e05f7e1924785a3f7d162dae90f` 的三个文档原字节保持。
[Owner 原文](../governance/Q2_CORE_HOST_CAPACITY_BOUNDARY_OWNER_DECISION.md)与 Gate 登记构成独立 C
`434c6a07f7a84f26d7bd01de138125debc467dd4`；其中没有代码或测试。
实现 D `61e232e1a4b57c9b7fbd523cbd7d4f8f747d756e`（tree
`a7982bf0f410d91c5e3368340a0d3a54b215aff8`）直接以 C 为父提交。

D 在原 pre-marker 点核对旧五原件后，仅调用一次受原 deadline 包裹的 `fstatvfs`。
调用前后检查完整 held fd/name 目录身份、权限、UID/GID/nlink 及实际 writer；双钟顺序不变。
当前可用量要求固定 `134217728 B / 32 inodes`；不扣除旧五文件的小额实际分配，不退款。
条件记录绑定实际 D、management digest、prior canonical digest、原窗口与本次观察。
记录沿原调用栈进入 finalizer 和 live 返回，再次严格校验；不重采样、不用成功说明覆盖后续失败。

包准备现在只读原件，不提前或重复采集容量。新 A/B/C 的 tree、祖先关系、三文档与 B 字节
加入原发行检查；不存在 caller 可选预算行。原 capture_accounting 五键、六个文件名、盘上格式、
wire、guest 计费和三个 field 文件保持；条件说明仅为 live 返回 sibling。

## 验证

核心定向回归 `1159 passed / 35 skipped`。新增覆盖阈值、坏容量值、身份/双钟漂移、
旧原件改变、pre-marker 零请求、返回记录篡改和 ENOSPC/EDQUOT/EIO 保留失败。
真实 package builder/parser 的合成接线测试不等于现场业务测试。

保留验证准备失败：默认 umask 0002 下，沙箱运行 `24 failed / 1135 passed / 35 skipped`，
普通环境运行 `23 failed / 1136 passed / 35 skipped`；主要是 fixture 文件组可写，另有沙箱 home 只读。
umask 077 下 `1 failed / 1158 passed / 35 skipped`，因为原 mkdir fixture 断言期望 0755。
使用标准 CI 的进程 umask 022 后上述定向回归通过；未修改系统配置、生产权限规则或旧断言。

准确 D 在独立 clone 构建测试 wheel、新 venv 安装验证通过：`94 checks / 292 commands`，fixture-only。
报告 `lhqcore-capacity-verify.zERhxt2g/installed-acceptance/report.json` SHA-256
`d09b0b4add98ee5940e38e72c2c743f3d72a504a513906486097bb9f05c232d0`；测试 wheel SHA-256
`7cdb7be20b3abae466ad468f2dd1d01badc202acfc86898cb61f16baf03f1e7a`。
测试 wheel 不替代原现场 wheel `ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`。

准确 D 的独立 clone 完整源码：`5070 passed / 126 skipped / 475.31s`，进程 umask 022。
JUnit `lhqcore-capacity-verify.zERhxt2g/source-tests.xml` SHA-256
`1c4cac853a30dd76ed8842008a77523bc6711ffd35c90f720cff6b5a5e1118ce`。
所有 skip 保留，不当成现场能力通过。
[准确 D CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37262540014)
已 3/3 success，Linux 源码及独立安装、Windows 和 classify-change 均已核对终态。
上述条件及下述真实私有双构包通过后，后续独立发行登记仅加入已审查 dispatcher SHA-256
`30d8e9fe9a9bbf39dc5261d0eb0d47c7349fe7e8229132f394a31aa934216eb4`，并保留未知摘要拒绝回归。
发行登记提交仍须自身准确 SHA 的 source/installed/CI 通过，才能在新的 live caller 中执行。
登记不消费 marker，也不放宽原 pre-marker 的来源、身份、当前容量和六名 absence 检查。

## 真实私有来源校包

复用已经定位的固定来源，未再要求搜索 44 份文件或重采 K4/R3。旧五原件全匹配，共 9318 B。
实际 cloud-init 与规范 grant、历史 guest 来源链及完整 source-aware approved-input 校验通过。
approved-input 为 325117 B，SHA-256 `ea650c23e2894d820aa591121fc93d141a0d37b2f3f76928234e9f90391bf7b1`。
实际新 held writer/anchor 的同窗两次独立 build/parse 相同：860 members、18149835 B，包 SHA-256
`9a90956b6ca728295a7ca6c1b87f6543f4d4f53e924a07315b742e43a908c7d6`；manifest SHA-256
`cbaf9efe7e7ac9c88963b17f2b772566a055e696d4cddb15ca1ce8d6a1d0b645`。

这是只读校包，不是可复用的现场包或窗口；未观察本次容量、未创建 marker、未发 carrier。
正式 B3 必须在新的原 900 秒 caller 中再次双构包及检查全部来源/身份/absence/容量条件。
原未消费机会、固定 session、预算、900/800/750 秒、失败不重试/重连/清理保持。
该记录目前不证明 H01/Q4/H11 执行，也不证明真实业务结果或证据回收。

## 最终准确发行版本与 B2 复核

实际发行 D 为 `59d7c32bbe10d580603b8e5e62dd49ad6a538e56`，tree
`15bfe2192ced5aad0acf5c74a58b6e865afe34d1`，直接以实现 D `61e232e1` 为父提交。
该提交仅登记准确发行摘要、相关回归和本报告；三个 field 文件未改。
现场 runtime candidate 保持 `4b6e4a7c403362358192086b88679e1326dcb2e1`，wheel 保持原
`ce31fa11caf5995a3c62611660a3908b78d68b88ee80196900bf69a7702856c9`。

发行前定向 `166 passed / 4.04s`。准确 D 的独立 clone 完整源码为
`5070 passed / 126 skipped / 472.75s`；JUnit
`lhqcore-capacity-release.FyX1ENAZ/source-tests.xml` SHA-256
`32bd1f1be8a8da50f141fd7ffc52d75fa63f9c297e0d4122d5031108c484fdab`。
同一 clone 新 venv 独立安装为 PASS、94 checks / 292 commands、fixture-only；报告
`lhqcore-capacity-release.FyX1ENAZ/installed-acceptance/report.json` SHA-256
`9a32950074c983749fa10d39e3f243d667bc23543d8ce26576c62cd7e4a5342a`，测试 wheel SHA-256
`f13d7d9e9318fd90db70ca48fe8314f88b7f1979462266718afff4d192a9e82e`。
[准确发行 D 的 CI](https://github.com/kongbu0621/infra-local-hand/actions/runs/37263529942)
在现场请求之前已确认 3/3 success；未把 skip、安装验证或 CI 当成业务验收。

该 D 的独立私有只读双构包也通过，包 SHA-256
`fa8c26b6a867e3417ac546dee6111ba6d873c352048f03590c6aa110a314dcca`，manifest SHA-256
`e9edf5c92b60d441f0cb560bbaeaa486ca82e49187747f12262ef27ea82f001e`。
其窗口结束后没有复用。正式 caller 重新取得原 900 秒 origin、held writer/anchor 和全部来源，
再次双构包、解析、重验当前身份和六名 absence，再执行本次唯一容量采样。
实际发送包为 18149835 B / 860 members，SHA-256
`da72c862bbcbe4ae43df681f91576d38586eec1eeb550b46e378d3398e07008b`；manifest SHA-256
`09e7b8ef0df3b3103f0ba87113dfcf2d3470b861ad14f84c83c144a0f6b3c6fb`；approved-input
325117 B，SHA-256 `5bcbf535f6c8d0d2c974756af6815ba95a03da7fadc31c97a0622cdeeaf4846e`。

## B3 实际停止结果与证据

`lhqcore-20261005a` 的 O_EXCL marker 一次创建、carrier 一次 execve 成功；真实 HELLO 有效，
BIND/package 完整写入，stdin EOF，发送 18150763 B。没有第二 request、重连、重试或清理。
唯一采样的可用量满足固定 134217728 B / 32 inodes；返回条件与实际 D、原双钟窗口、writer、
prior 原件摘要绑定。旧/新两项仍各保留 67108864 B / 16 inodes，更早历史字段保持 UNKNOWN/null，
`complete_host_admission_proven=false`、`exclusive_reservation_proven=false`，释放量均为零。
该条件的通过没有覆盖后续 guest 准入失败。

实际 stderr 23 B：`CORE_ADMIT_SUDO_OUTPUT\n`。carrier/SSH wait status 3；stdout/stderr EOF
均为 true，host deadline met 为 true。这些是本地等待和传输事实，不能替代 guest 监督退出证明。
finalizer 返回 `STOP_AND_RETAIN`；缺项 `CORE_OUTPUT_MISSING`，没有 output-package、remote-result
或 case verdict。原 receipt 的 `real_task_execution` 与 `result_evidence_collection` 均为 UNKNOWN，
原样保留；无 H01 PASS，未继续 Q4/H11，不合成正常任务执行或业务结果证据。

准确 D 的静态调用顺序为 `dispatch → admit → _admit_collect_policies → _admit_sudo_output`。
该解析器消费固定 `/usr/bin/sudo -n -ll -U q1admin` 的输出；同一错误码覆盖头部、section、字段、
缩进和取值的多条严格断言。现存回传没有 helper 原始 stdout，所以只能定位到此解析器，
不能认定具体断言、缩进差异或 sudo 配置错误。准入成功之后才会核对旧 scope、完成 guest 容量检查、
安装和 H01；本次在这些步骤前停止。旧 scope 当前静默、本次 guest 资源使用和监督退出均未得到
完整结果证明，保持 UNKNOWN，不退款。未因工具环境 PID 1 推断真实宿主能力。

保留原六名中的五文件。实际 logical bytes 为 9072、created inodes 为 5、最大观察分配为 20480 B；
`full_filesystem_peak_proven=false`。marker/原始 streams 的 capture manifest 确认 fsync 和回读一致。
私有原件仍在原管理 anchor；以下仅公开文件名和摘要，不公开机器原文、路径、凭据或身份。

| 原固定文件 | SHA-256 |
| --- | --- |
| `.lhqcore-20261005a.carrier-consumed.json` | `126a3fc0c40085c360e6392d06ec286e42f05edc93823fd01f36c0869103d2a6` |
| `.lhqcore-20261005a.stdout` | `3cf4a279a36daeb3348d52544c92bdfeba3f295e0650f2bf49bd204d3e0bd3b9` |
| `.lhqcore-20261005a.stderr` | `ef5aad9b8e8b977441ad9ab1e58cd1dc8ad994798f5802d2f6768c241afb8ece` |
| `.lhqcore-20261005a.capture-manifest.json` | `081019f289a561839ddf13da0c5bf55150879e998a6b52241864f3813b132d1b` |
| `.lhqcore-20261005a.acceptance-receipt.json` | `541198e61811e4b6f2df3d17eb4ade8f91ef567ae4c00e89e7023f5709040f35` |

本次没有新增第七个现场文件。原 20261003a 的失败、原五文件及全部承诺仍保留；本次失败不释放
任何旧/新承诺，不刷新任何 deadline，不创建替代 batch 或新执行窗口。

## 失败后收口与直接阻塞

两个固定 core 批次现在均已消费，host release allowlist 重新置空；保留已消费 marker。
回归要求当前准确 dispatcher 和未知 dispatcher 都在 anchor、marker 和 request 之前被默认入口拒绝。
仅测试 fixture 显式注入摘要来验证 gate，不构成重新发行资格。三个 field 文件和生产 E3 均未修改。

直接阻塞是 guest sudo 有效授权输出解析失败，以及未回传其具体失败原文；不能通过放宽身份/授权
检查或再次探测来猜测修复。下一次现场动作需先完成有来源的诊断/修复与准确候选验证，再建立新的
固定一次性批次批准，明确保留本次失败/未知退出与资源义务。当前批准不覆盖第三次请求或补采连接。
真实验收仍须按 H01 正常链 → Q4 取消 → H11 原账本/原单元恢复顺序完成，结果证据完整回收后，
生产启用仍需单独明确授权。B1/B2 的通过不等于 B3 业务验收成功。

收口版本本地定向检查（entry/freezer/host capacity/capture/admission）为
`217 passed / 2 skipped / 4.42s`；两项 skip 明确要求 root 才能对 root-owned 对象使用 O_NOATIME，
未提权或改弱 reader。首次测试命令写错 capture 测试文件名，pytest exit 4、未收集测试；修正路径
后得到上述结果。这是关闭发行入口的定向验证，不冒充该收口版本的完整源码或 installed 结果。
三个 field 文件摘要、A 的三文档与 B 原文均再次核对未变；本次收口没有发出新的现场请求。
