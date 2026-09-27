# Q2 本地预检与首次远端截止：后续复核

本轮继续准确 A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37` 已批准的
`LOCAL_PREFLIGHT`。该分支是 H2 尚未完成的交付，不要求 Owner 再批准同一范围。
原 A 三文档、R、B/C、冻结 runtime、预算和唯一未发行批次均保留。
本文件记录实现与证据判断，不是新的需求基线或远端执行许可。

后续现场更新：2026-09-27 23:27 +08 已收到原 host 终端截图，显示预检在
`host_boot` 阶段因权限阻断。见[现场复核及窄范围方案](Q2_LOCAL_PREFLIGHT_FIELD_REVIEW.md)。
下文的“待回传”保留为本轮当时状态；该截图不等于完整观察或新的执行批准。

实现 D：`0a456a909821fd1fc6a4fdec43b9e16bc88679f2`，tree
`d29cc1cdea2800d9cca05cc3b33041abf319e695`。只新增两个专用工具模块和两个
测试文件，原入口、消费组件、冻结 runtime 与 A 原字节不变。受影响整组
**287 PASS / 2 SKIP**，其中本地预检 22 项、真实 PTY 接收器 8 项。
准确源码摘要与实际输出见 [validation.json](evidence/q2-local-preflight-20260927/validation.json)。
合成来源/boot/mount 事实与真实本地文件、PTY 验证分开注明；这些结果不是现场准入。

准确私有包两次组装逐字节一致，离线来源检查与 10 个拒绝负例通过。完整载荷
在本工作容器的真实 PTY 测试中因 host boot 不符而停止，未读固定父目录或联系
guest。包与完整输入的准确容量、验证边界见[交付证据](evidence/q2-local-preflight-20260927/README.md)。
原 host 仍待通过已有终端回传实际观察，不能把此错机拒绝测试当成现场预检成功。

## 本地观察与后续执行分开判断

A 的需求“有限 host 子预留”、架构“原点、竞争与同步顺序”及实施方案 H2
明确允许：首次现场读前固定 MONOTONIC/BOOTTIME；在 140 秒准备和 300 秒双钟
上界内，只读检查本地 host/boot、受保护父目录与设备、消费名不存在、可用
bytes/inodes、已知 host 实际/承诺及记录峰值。创建标记前失败可以重新完整检查。

前一实现 D `f1814b27adbc1bcdb6d6ac14875e9d2ec6a795ff` 的统一事实门在所有
现场读以前拒绝，同时挡住了这条已获准分支。远端期限、完整账单或持久资格缺证
应阻止消费/派发；它们不必先于用于补证的准确本地只读观察成立。

本地入口始终只返回部分观察或阻断；它不创建消费目录，不连接 guest，不产生
host 诊断文件，不进入对账、发行或封存。实际缺项不会被填零。重复观察不继承
旧采样，也不产生一个可供后续消费接管的原点。

| 输入或观察 | 允许用途 | 不产生的证明 |
| --- | --- | --- |
| A 已固定的 carrier 与 host attestation | 复算唯一父目录、消费名及预期 host boot | 不把 attestation 的其它字段升级为执行来源 |
| 已留存且摘要固定的 host 对象清单 | 定位已知本地检查对象；当前结果逐件注明定位来源 | 不把旧 metadata 当成新增历史身份基线，不自动决定费用类别 |
| 原七份 host 文件 pin | 核对其原有完整性关系 | 不证明所有未用义务或原生日志峰值 |
| 当前 held/no-follow/O_NOATIME 观察 | 文件/目录 metadata、allocated blocks、完整成员、设备及挂载事实 | 不证明未来不变、完整联合容量或 fsync/掉电资格 |

新的观察只能回报本次实际读取的范围。未检查的已知对象、未证明的费用归属、
future、audit、wrapper 执行来源和远端监督均保留为缺项。不能把“已知对象定位”
转成新来源采用，或在这条入口中补一个远端 probe。

## 两项预算判断的更正

marker 的 64 KiB 是新分配空间/相关峰值的子预算，与 16 KiB logical 和 4 inode
分别核验。它不是整个设备一次 fsync 的写流量限制。JBD2 的既存保留日志空间、
文件系统元数据写回和 SSH/systemd/journald 的普通审计文件增长是不同对象。
不能每创建一次 marker 就重新收取整个既存 JBD2 日志；也不能只检查 4 KiB
几何就认定父目录增长、分配峰值、底层存储关系和同步资格全部通过。

原 D 只支持 root 身份、窄 ext4 几何和无目录索引等条件，这是实现支持范围，
不是 A 要求改变现场配置的理由。本地观察不要求用户为适配代码执行 chown、
关闭目录索引、改挂载、增加能力或提权；无法读取的事实明确报告缺失。

三个 owner 共池不能无条件写成 60 MiB 的 capture 严格下界。每池额度 C、
capture/declarations 实际 c、journal 实际 j 的 capture 暴露为
`c + max(C-c-j, 0) = max(c, C-j)`；类别最坏暴露与全局去重仍分别核验。
旧 host 五组留存文件合计 13,081,230 logical bytes，但缺少完整 allocated
及费用归属，其中 10,454,575 bytes 是三份派发输入副本。故“60 MiB + 约
12.5 MiB 必超 64 MiB”不是已证明结论。未知量仍阻断准入，不能为了通过门禁
改类别、释放旧义务、删除实际文件或把 host/guest 各套一份额度。

这些是计量与证据边界的澄清，不增加额度，也不改变已批准的成本归属。
若完整事实最终证明不可满足，届时以准确账单提出受影响决定。

## 首次远端截止的机制比较

目前的缺口是：现有材料没有证明首次 probe 前已有适用的跨机器截止机制；
取得监督所需事实又可能依赖该 probe 或新的准备动作。A 允许此时拒绝，不能
把这一具体依赖环写成“A 本身不可能”，也不能以新增布尔值宣布问题解决。

| 路线 | 当前能证明什么 | 缺口与决定边界 |
| --- | --- | --- |
| host 超时并结束 SSH client | 本地等待/进程状态有界 | 不能证明远端停止、原管道 EOF 或其它管理单位已停止 |
| 到达后设置相对 RuntimeMaxSec | 在对应 systemd 管理语义下限制激活后的服务运行 | 不覆盖到达前排队；不等于原 host 双钟绝对截止；outer cgroup 也未必包含经 manager 另建的单位 |
| 复用旧 clock anchor | 原件所包含的当时采样关系 | 旧件没有 host boot/BOOTTIME 对应；当前 boot 不能倒绑定历史；一次 offset 也不自动保证之后漂移/VM 暂停关系 |
| 预先有效的 guest 绝对监督 | 条件成立时可在派发前约束准确管理域 | 需先证明时钟关系、配置/版本、全部受影响域和有限收尾；实质改变原三文档的准备设施或顺序，须按原 R 批准准确新 A 后再实现 |
| 原 host 的 VM 管理停止 | 若既有通道及权限被证明，可观察 VM 层状态 | 现留存材料未证明 QMP/QGA 入口；VM 暂停不是进程死亡或存储收尾，不能为此操作整台原 guest/Q1 |

systemd v255 官方代码以 active-enter MONOTONIC 加相对 runtime 计算相关期限；
JobTimeout 取消 job 不等于停止 unit。这是版本参考语义，未据此声称实际发行版
补丁和完整版本已经匹配。Linux MONOTONIC 与 BOOTTIME 对 suspend 的语义不同。
QEMU 参考实现中的 STOP 状态也不能替代全部磁盘收尾或 guest 进程停止证据。

后续必须同时证明“派发前已生效的截止机制”和“准确对象的独立停止证据”。
失联、不可中断 I/O、缺 EOF 等仍保留 UNKNOWN/INCOMPLETE；不许把 kill 返回
成功或 client 退出当作终止事实，也不承诺软件可以消除所有内核阻塞。

## 后续顺序

1. 完成并交付本 A 已允许的本地只读观察；保留原唯一未发行批次，不取得/消费运行窗口，不为补齐这些事实新增批准。
2. 用返回的实际分配、保护和设备事实补账单/存储资格。来源分类及承诺从原件逐笔追溯。
3. 只对真实缺少的监督准备、首次远端探测顺序或新来源采用提出具体变更。
   若确需另一次 guest 只读采样，应独立说明它的时限语义，不能接着自动发行 owner。
4. 结构性前提闭合后，再完成同一原批次的消费、联合准入、对账、唯一发行与收尾接线。

本轮不存在新的 B/C。历史两次 INCOMPLETE、实际数据、全部未获准终止的义务、
旧 v1 和所有原限制均保留。

## 一手参考

- [systemd v255，固定 commit 的 service.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/service.c)
  及 [unit.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/unit.c)、
  [systemd.unit 文档](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.unit.xml)。
- [Linux ext4 Journal](https://docs.kernel.org/filesystems/ext4/journal.html)、
  [allocation policy](https://docs.kernel.org/filesystems/ext4/allocators.html)。
- [QEMU v6.2.0 固定参考代码](https://github.com/qemu/qemu/blob/44f28df24767cf9dca1ddc9b23157737c4cbb645/softmmu/cpus.c)。

版本固定的上游原文与摘要、原始离线检索和私有费用推导另随私有证据保留；公开
文本不包含真实 host/guest 身份、路径或 wrapper 原件。
