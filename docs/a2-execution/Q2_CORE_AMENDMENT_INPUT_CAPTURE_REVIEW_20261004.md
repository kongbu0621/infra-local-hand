# 核心最小修订：固定输入、六文件采集与保留材料复核

2026-10-04 +08:00。**本件记录部分 D1/D3，不是 D1–D4 完成、package freeze 或 F1。**
本轮建立独立 C，新增输入处理与六文件采集代码并接入本地终结器；没有发出现场 request，
没有受理/执行真实任务或收回任务结果。

## 准确批准链与代码

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`，本轮直接读取且摘要与采用记录一致。
- A：`0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`；三个文档的 bytes/摘要保持
  [baseline 登记](../governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_BASELINE.md)所列值。
- B：[Owner 准确回复](../governance/Q2_CORE_BINDING_FINALIZATION_AMENDMENT_OWNER_DECISION.md)，event
  `LH-Q2-CORE-BINDING-FINALIZATION-AMENDMENT-CLOSURE-20261004-01`。
- 独立 bookkeeping-only C：`7598886e15ed6911fe0e09e2f8d66203455f9057`，tree
  `7f2178942c126f883829a139b842cfc2c2e12159`；只含 AGENTS CLOSED 登记与 B 记录。
- 首个 D：`a7e2a6ffb97b7515ec3f8ceab00ff5e0789f65c9`，direct parent 恰为上述 C。
  后续 D：`aec85bd41c31d0f7a33fbe3a56dfe3a444204b98`、
  `1caf26facbccfc9e8783d94504e599914bde7365`；输入组件基线为后者，tree
  `507bf0706c04c7727a091af98da8e73d1bb8260a`。
- 六文件采集/传输/终结 D：`5e129f76a4a716053a769a3fbfd15bd19da737b4`，tree
  `536f39063f171f6b3b053392386c262238baaed7`，直接继承 `1caf26f`。
  这是实际源码冻结，不是完整 field package 或可执行批次冻结。

| 新增实际组件 | 实现范围 | SHA-256 |
| --- | --- | --- |
| `tests/e3_host/q2_core_obligation_inputs.py` | 六个固定 archive、26 个 exact member；24+12 rows、46 quota rows、固定 placement 及总计复算。只解析 RAM 数据，不解包到磁盘、不分配 current device、不发放执行权。 | `8591d620c8476b006a30a2686b4ea8322a21f815b99327eafaad0298e282ab1e` |
| `tests/e3_host/q2_core_legacy_inputs.py` | 从准确后续保留帧恢复原 34010-byte manifest；验证全文件摘要、42 个历史工具输入关系与 48 个 blob。返回原验证器输入，不继承旧 run permission。 | `c9bab031ce62ad4b9f074b13cb315db9e080c26a681a61bc63fc7abd2b171f59` |
| `tests/e3_host/q2_core_policy_basis.py` | 固定四项 policy basis、源摘要、参数/执行/输出限额和 digest preimage；拒绝 source 或 predicate 漂移。不做 current observation，不调用 helper。 | `54c1e016a26eee1ed82e892df70f6097f389c322a42a8c9328a6d04be62eb601` |

policy builder 的 token 输入仍须由集成 freeze 与准确 D 的 loader/bootstrap 交叉绑定；
本组件不是 standalone authorization boundary。它不能代替 current guest collector/predicate parser。
上述输入组件尚未接通完整 package/admission；原空 allowlist 和失败关闭行为保持。

## 真实保留材料验证（非现场执行）

本机既有六个 normal/system-manager archive 及原 20260927 整体 archive 的长度/摘要全部匹配 A。
新 horizon 组件读取六个 archive 的 26 个固定 member，拒绝同名替代、alternate prefix 和重复 member。
复算结果如下；raw、私有路径/账号/机器身份均未进入公开仓库。

| 项目 | 数量 / 合计 | canonical no-LF SHA-256 |
| --- | --- | --- |
| snapshot | 24 rows；626790400 B / 32113 inodes | `82bdb7a94c85a7450a45d9ee7dff2baa4e5fef7b8a7a7d8f7787a0cb7bea358e` |
| amendment delta | 12 rows；138412032 B / 8064 inodes | `b8af1d3264b77b9142a48288482c26d2eafa894523f85baa0fc71d595da90352` |
| effective | 36 rows；765202432 B / 40177 inodes | `7c2786f240144e7a2de90bc9a70561089a7334559bd8e962371132cf1db806e9` |
| normalized placement | 24 rows；不冒充 current pool | `b6153d8c45e5b009bcc1f878406565e08bcf7c7d07c17f18361b562bf1096703` |
| configured quota liability | 46 rows；249561088 B / 17792 inodes，单独计费 | `95b59d878d643bfbce2eef6ce88145bf1086058694dee127b3de49d13319bde0` |

原 manifest 的恢复来源为本地已保留的 kernel-preflight 输入帧：7494251 B / SHA-256
`807f774bfe6716ae404d360698adb5f6d5190c18d8f8b6be4e74d7691b8eefe3`。
这里只解码保存的数据，**没有重跑旧 preflight、内核观察或其中的 payload**。
其 `inputs.json` 带有后续 34978-byte manifest（SHA-256
`5900f95acd4fd67ebdad759334d2a403aa83d978e2b691770798e7964ca798f0`）及 48 个 blob。
仅按准确历史 D `8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1` / tree
`5fb64e578d06e2954c1eedbc1b15e00069dc32a4` 恢复 implementation/source commit/tree 和 42-tool digest map，
结果恰为 A 固定的 **34010 B / `f705d3c77885887c7b6f799f4721dfefd0e9c588dbd11085cc8456fe623c6d40`**。
这是已固定原字节的可核验复原，不把后续 manifest 或“等价近似”冒充原件。

另在隔离临时目录加载准确历史 Git tree 的原纯 `q2_reconciliation_sources.verify`，验证恢复输入：
48 unique blobs / 5686734 B、12 historical trees、47 typed sources、610 forward entries、5 disclosed
atime changes；得到的 7 行与新 snapshot 前七行**逐字段同序相等**，摘要
`09f107f265986afd0dcc0535de84d2df37ac47ddeff78d20569c2bb8a5513e88`，合计 340529152 B / 13681。
这不是再次收集原机数据、执行旧 batch、释放义务或证明当前 guest 准入。
不再要求 Owner 提供已经通过该关系取得的相同历史原件。

首次新 horizon 代码验证曾在历史 `20261001e/client-intent` 的一个 decimal 计时值处失败。
现仅对该准确 pinned 历史 member 保留 Decimal，不转整数，不将它写入新的 canonical artifact；
新 JSON 仍拒绝 float/NaN/Infinity。修复后真实 archive 复算通过，原件未改动；不把首次失败抹除。

later-nonissuance 的第三份 review 在当前 main 有后续附加内容，不能用当前字节冒充 A 的 pin。
已从 `9a87df50c51d863014723aa6c3c3584077429fd3` 取得该 repo path 的原字节，SHA-256 恰为
`e64f1be1287ac8bed5f582b01e179b66dd79ead0eb91e8ccf1c71d3ea0095da0`。固定 producer commit/path
的 blob/SHA 也匹配 A；不要求 Owner 重找这些来源。

## 六文件采集与终结集成

`tests/e3_host/q2_core_capture.py`（SHA-256
`7d045ea603cf20175aa6aaa1eeac033cba950bb0701a74cf0683d8f17ec758f1`）已接入
`q2_core_delivery_entry.py`（SHA-256
`2d081430223db297aaf04eb34a3b455a44d633887d1067a6d13474503e6b8c99`）：

- marker 与五文件共用原调用进程的 capture 实例；固定 O_EXCL/0600/single-link、实际 bound
  writer/anchor、固定角色与两流 52 MiB。每次 create/write/file-fsync/parent-fsync 后，对全部已创建
  文件观察 `st_blocks*512`；保留峰值，超额/未知/漂移即停止，不覆盖、删除、换名或重试。
- 原 900s 双钟严格 `<`，BOOTTIME-first；positive short-write 即使晚返也计费。回读使用同 parent、
  NOFOLLOW/NOATIME、同 inode 和完整字节比较，无 weaker fallback。
- receipt 最后 fsync/回读/parent fsync/allocation/双钟全部及时完成，原 live 调用才可成功。
  盘上 COMPLETE 后若晚返仍失败，不改写已有 bytes，不补第七文件，不从重读派生成功。
- capture/receipt 保留 v1 shape，限额 256 KiB/64 KiB；live-only `capture_accounting` 明确
  `full_filesystem_peak_proven=false`。撤下 `st_blksize` 取整作为分配证明。
- transport 保留原 60 MiB/frame 拒绝线，但先执行 52 MiB 两流门；remaining+1 溢出 chunk 不进入
  capture。execve/select/read/write/poll/terminate/wait/close 检查原双钟，保留 15s reserve，
  不追加 905s 尾窗或第二 request；晚返时 actual execve/positive stdin write 仍如实计入。

这些临时文件/假管道测试不是现场 writer/anchor 或真实 H01 验收。D1 v2 binding 尚未完成，入口
拒绝未绑定 writer，release allowlist 仍为空。D3 仍须与完整 private package/现场输出集成验收。

首次组件测试发现工具进程的 supplementary group 原列表含重复项，已按 A 生成升序去重 membership
array，不改变实际身份。首次接入回归中的旧 combined-stream fixture 仍按 60 MiB 设值，故在新的
52 MiB 拒绝线失败；已按批准边界修正 fixture，未扩大限额。两次失败均如实保留。

## 验证及剩余直接工作

`PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q`，范围为新三个组件的测试及现有
`test_e3_q2_core_delivery_{contract,package,freeze,entry,bootstrap,dispatcher,loader}.py`：
输入阶段为 **99 passed**。三份新组件测试合计 33 项；覆盖 source/member 替代、字节漂移、重复、整数/decimal、
quota 重复/重排/溢出、原 manifest 不可近似复原、sudo group 语义、policy/argv/预算改动及 digest 边界。
采集组件 29 项和入口两项新 deadline 回归加入后，同一核心范围为 **130 passed**。
包含真实临时文件 fsync/NOATIME/回读与故障注入；fake carrier 只验证协议和失败回收，不证明任务执行。

第一次完整 source suite 在工具沙箱内：**268 failed / 3625 passed / 110 skipped / 127 errors**，
409.20s，exit 1。已单独复核一个 `RECONCILIATION_UNPROTECTED_PATH` setup error：相同既有测试在
沙箱外 **1 passed**，未修改权限或系统配置。工具 root/ancestor owner 映射不等于真实宿主不支持；
其它失败不能仅凭这一例全部归因。第二次完整非沙箱复核为 **69 failed / 3972 passed / 91 skipped**，
423.25s，exit 1。保留的 JUnit 为私有临时测试日志，不公开原始机器路径。
剩余失败集中于临时 source/evidence/result 文件保护检查；对子进程设置 `umask 022`（不修改系统
配置或既有文件权限）后，准备快照、证据 seal、结果 JSON 三个原失败样例 **3 passed**。
这三个样例不等于完整 suite PASS。第三次非沙箱、子进程 umask 022 的完整 source 运行实际为
**1 failed / 4040 passed / 91 skipped**，428.36s，exit 1。唯一失败是既有
`LocalReadTests.test_real_opened_rejects_noncanonical_and_world_writable_ancestry`：它假定临时目录
祖先必然 world-writable，但本地 TMPDIR 为受保护路径，所以原保护函数正确接受，测试的拒绝预期不成立。
修复只在该隔离测试中新建明确 `0777` 的祖先、`0600` 的 leaf，仍要求原 `FIXTURE_PROTECTION` 拒绝；
不放宽产品保护，不更改系统 TMPDIR 或已有目录。首次完整结果保留，修复后的准确 CI 另行验证。
本次全量开始时 checkout 为 `d42dca8`；运行中 Windows-only import guard 修复已另提交，Linux 已收集
的测试与实际 capture/entry 实现未变。不将该次运行冒充后续提交的全量 PASS。
始终不把 SKIP/UNKNOWN 写成 PASS。
这些结果不是 D4 独立审计、installed suite 或真实 H01/Q4/H11 验证。

首次发布 `d42dca8a25151010d3dd38edabd285b89bccafa4` 的
[CI 37177207849](https://github.com/kongbu0621/infra-local-hand/actions/runs/37177207849)
在 Windows collection 暴露本轮新测试的平台 guard 顺序错误：先 import Linux-only capture，
才应用 pytest mark，Windows 没有 `time.clock_gettime_ns`，导致 collection error。
已将该 Linux-only 模块的 skip 移到 import 前，与既有 entry/bootstrap 测试保持一致。
这不增加 Windows E3 支持、不改变 Linux 实现或减少 Linux 验收；原失败保留，修复结果另按准确提交记录。

| 阶段 | 本轮准确状态 / 下一直接工作 |
| --- | --- |
| D1 | **部分实现**。上述固定输入组件及历史原件复算已完成；还须组装完整 approved-input artifact、独立 parser、local binding、package/HELLO v2 与 current admission。 |
| D2 | **未完成**。dispatcher 八组真实效果仍未接通；不能把现有 UNIMPLEMENTED 或 FakeEffects 当执行实现。 |
| D3 | **部分实现并接入本地终结器**。六文件采集和终结检查已实现，仍须与准确 v2 local binding、完整输出及 private package 集成验收。 |
| D4 | **未完成**。定向结果及非通过全量尝试均保留；完整 source/installed 验证、独立审计、双 build/parse、准确 package/release freeze 仍待闭合。 |
| F1 | **NOT_ISSUED**。全部前置门尚未通过；本轮 marker/carrier/H01/Q4/H11/真实任务/退出/结果证据回收均为 0。 |

此剩余工作仍在本次准确 CLOSED 范围内，不需要为相同 A 再要一次批准。固定产品 candidate/wheel/harness
未替换；新增输入组件提交不是新的 field-ready candidate。package 仍 null，release allowlist 仍为空。
source-only 验证不能代替现场成功；后续按原条件执行 H01 → Q4 → H11，H11 使用自己的 origin 原账本与
unit/grant/deadline，不重启业务、不延长期限、不重放旧批次。production guard 与暂停支线均保持。
