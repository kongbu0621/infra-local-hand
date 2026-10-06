# Journal host-read：实现冻结与 R2 阻塞记录

状态：**R1 已实现；R2 本地窄验证通过，但静态输入准入及新候选 CI 尚未完成；R3 未开始。**
本记录不批准新的现场动作，不关闭未完成的验证，也不增加维护次数。

## 准确版本与顺序

- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`；本轮已完整读取固定直接来源并核对既有 SHA-256。
- A：`2b4448c7b89d1910840f7aee2ae2b781f970e179`，`LH-Q2-CORE-JOURNAL-HOST-READ-v1`，R1–R3。
- B：[保留的准确 Owner 决定](../governance/Q2_CORE_JOURNAL_HOST_READ_OWNER_DECISION.md)。
- 独立 bookkeeping-only C：`b5414d0cfd505b220ba4b68a454202f245c77f6c`。
- 实现 D：`8ce15f5786877e36c5983282b19a75d1439f6c47`，直接承接 C。

本记录是 D 后的证据登记，不与 C 合并。原维护 A、修订 A 的三份文档均保持准确字节和历史 OPEN 标签。
本地代码已提交，**本轮未推送**。此前仅针对两个旧提交的推送批准没有被扩展成此次发布授权。
后续若以本记录或其它子提交执行，须重新绑定实际完整 HEAD、payload 和相应 CI；不得把 D 的结果冒充另一版本的现场结果。

## 已接通的实现

1. host boot 采用既有严格内核读取组件；root writer 的自身 mountinfo 采用同一组件。
   普通读取只限批准的固定内核视图，guest、原件和证据的 O_NOATIME 不变。
2. 固定只读 root payload 从冻结的两个实现文件和既有内核模块生成；先验证源码长度/摘要，
   再校验 scope/session/D/nonce、五角色 dev/inode、双钟期限和检查点。
   不从可写仓库导入 root 代码，不提供任意命令、路径或表达式接口。
3. 八个原检查点串行、每点一次；首次预检的报告通过私有返回交接，执行复核必须进行新观察。
   静态 manifest 不采用第二次扫描的动态用量/PID，实际报告按 nonce/窗口/序号分别记录。
4. 固定 sudo/env/Python 文件身份复核，Python 的 root-owned 固定解释器符号链接与目标分别绑定。
   未执行 sudo 探测、认证保温或 root 观察；既有授权是否可用仍须在 R3 第一次正式观察验证。
5. 普通 coordinator、维护写操作身份保持；每次观察 15s/原窗口上界、输入/stdout 65536 B、stderr 4096 B，
   累计资源和捕获池沿用原限额。超时/失败没有重试或强杀；管道关闭不代表退出。

为保留两个文件各 65536 B 的原上限，对缩进/续行作了 AST 等价的机械整理，精简说明文字，
并在两个原文件之间移动 `ProcessIdentity`、`verify_writers` 和共享 writer 协议。
前两个移动定义的 AST 与旧定义相同；没有第三个新实现模块，没有预算扩展。

| 冻结对象 | 字节 | SHA-256 |
| --- | ---: | --- |
| `q2_journal_growth.py` | 65434 | `9f46f240e3682fb5cfa138c5f21aa18999b7a48afc5b575e918ae1be3ecbf54e` |
| `q2_journal_growth_guest.py` | 65280 | `a03fbaab3e6289ebcb52e16eacd1264bb6e4be23afbbcb390f34aa1d978d8341` |
| 复用 `q2_host_kernel_facts.py` | 15055 | `947469560ca3bdc4997a56739b42561c4a616a5dc8b250b919db589689eecc02` |
| D 的 root payload | 23707 | `026a712b882c5107f1999d78f235c82ca9c1a9a2b9766097c6a9e72033ce49bc` |

loader SHA-256：`081d3bed41e9f49153096cb893ee20980182831d551c41b9504b886fd0c46aca`。
`growth_sources(D)` 对完整 12 成员、两个 C 的祖先关系、两个 A 的文档和既有依赖 pins 校验通过。
payload 已编译检查；这不是 root 现场执行证据。

## 本地验证及保留失败

最终在真实宿主普通 UID 1000 执行原七文件窄测试，加
`test_e3_q2_journal_host_read.py` 和既有 `test_e3_q2_host_kernel_facts.py`：
**395 passed，0 skipped，2.77s**。

真实部分包括普通身份固定内核资格读取、原生 pidfd，以及独立合成 qcow2/ext4 的完整备份、增长和内容校验。
没有使用原 VM/原镜像完成这些测试。新 root observer 的调用、失败/超时、八次上限、跨 CLI 绑定和 sudo 拒绝是 mock/合成验证，
不能代替 R3 的真实权限、可见性或 writer 结果。现有权限/ABI/子挂载/路径替换/PID/FD drift 等拒绝测试保持。

保留的失败事实：工具沙箱下原生内核测试曾为 1 failed/77 passed/1 skipped，拒绝的是沙箱中的 root/proc 保护资格，
不能据此认定真实宿主不支持。真实普通宿主测试随后通过严格资格，未改读取保护。
真实宿主的组合测试曾两次出现 6 failed（其余分别 386/387 passed），另一次定位子集为 6 failed/128 passed；
带资源审计的失败现场显示 pytest 自身历史 `ru_maxrss=1667768 KiB`，超过 512 MiB。
失败的时钟/模拟 guest 流程测试错误地使用了整个测试运行器的累计统计。
修复只隔离这些合成场景的统计输入，并新增 CPU/RSS 超限拒绝回归；实际 helper 的 120 CPU-s/512 MiB 检查未变。
开发中旧 mock 补丁点和源码整理的中间失败亦已修复，不作为通过证据；最终结果以上述 395 项为准。

现有 sudo/env/Python 的只读文件身份资格检查通过，三者均 **NOT_INVOKED**。
身份摘要及完整局部返回留在本地执行记录；不提交机器身份原文。
**新 D 的 CI 未执行/未核验。原 `50ec8f2` 的 CI 不替代它。**

## 首个静态输入阻塞：INPUT_PROTECTION

在 D 上调用既有 `freeze_growth_inputs` 作本地静态校验，首个 `management_frame` 在内容读取和 hash 校验前被拒绝：

- 本地普通文件，5496087 B，uid/gid 均 1000，mode **0664**；组写入违反既有 `mode & 0022 == 0` 条件。
- 其余七份已知输入的只读元数据检查显示 mode 0600、owner 合格；这只证明其权限，不是这次重新完成了全部 digest/清单准入。
- `management_frame` 的预期 SHA-256 仍是 `c9f4bb2744d48f9e7174157a95761d081be038cf4dd4f67ae42620a1a9e6d315`；
  本轮没有把“长度相同”当成内容匹配。
- 未 chmod、未复制/覆盖/删除原件、未放宽 `Inputs.read`。私有路径可直接使用既有本地记录，无需 Owner 重传原文。

最小准备动作是让**这一份**输入满足既有保护条件，例如由 Owner 确认将原文件权限收紧为 0600，或提供已受保护且准确同字节的既有副本。
这不需要再次 SSH、重采、改 guest 权限或改准入代码。本轮没有从实现批准推定改变原件权限的授权。
若采用新的准备动作，先确认它符合已批准的原件保留和预算边界；不得用变更路径/权限暗中绕过保留要求。

## 未消费的现场边界与后续动作

本轮 **替代窗口 0，root writer 调用 0，marker 0，SSH 0，关机 0，备份 0，镜像增长 0，VM 启动 0，ext4 增长 0**。
R2 的只读静态输入失败不是新 J3 预检：没有构造维护 `Window` 或部分窗口 binding。
旧失败窗口和历史 UNKNOWN 全部保留，批准的一次替代窗口仍未开始，不能把它用于临时探测。

继续顺序：

1. 准备合格的唯一 frame 输入，重新完成同一静态 pins/清单校验；保留本次拒绝。
2. 取得本轮非强制发布许可，发布 C→D→证据记录，不 squash、不 force；确认实际候选 CI 成功。
3. 对准确干净候选重新冻结 payload/J2。然后才开始唯一替代 900s 窗口，完成第一次本地预检。
4. 全门通过后，在同一 boot/原起点内交接原 writer 报告、做第二次观察并复核 manifest，条件执行原单次维护。
   任何现场失败都停止，不刷新时钟、不重试、不重连、不补采、不清理、不强制关机、不自动回滚。

真实业务 **H01/Q4/H11 均为零**，没有业务结果或扩容 receipt 回收。现有一次维护授权不是业务验收授权。
namespace/watchdog 暂停，production `E3_SUPERVISION_UNVERIFIED` 保持。
