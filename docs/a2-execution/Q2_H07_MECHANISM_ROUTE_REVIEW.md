# H07 实际监督路线：冻结调用链的接入边界

2026-09-29 +08；只读源码基线 `65047d64934468acfca8e4f94aebe99ea56e6f93`。
接续[有限模型实现](Q2_H07_MODEL_IMPLEMENTATION_REVIEW.md)和
[现场资格复核](Q2_FIELD_QUALIFICATION_NEXT_REVIEW.md)。

**本轮未找到在现有来源和冻结约束下已经充分证明的实际 H07 接线方案。**
已确定的障碍是首次探测的保护顺序，以及独立 system manager 请求的未决状态；
不能通过旁挂一个 broker、增大超时或再取一次时钟样本消除。
这是对具体候选路线的审查结论，不是所有外部机制均不可能的证明。
本文件不是新的三层文档 A、Gate 关闭、部署指令或原批次消费。

## 固定依据

R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 的直接原件已复读，
SHA-256 `c6a749c4966f8b4c7d7a41e7d664f8cebe20eb68f344156d5fbd540353ab70f5`。
H A `8402f0cc82d8a0ac0b9a56716bf276f41cafea37` 与独立 C
`271c07cd16140aa5942dcf3fad468003c58b6b0e` 保持。
原三文档允许原机制内的专用 host 编排修复与隔离验证；不允许据此新增范围外
监督设施、改 SSH/systemd 配置、替换冻结 runtime、改变消费定位或刷新窗口。

| 固定源码位置 | 已确认行为 | 对 H07 的影响 |
| --- | --- | --- |
| [startup entry](../../tests/e3_host/q2_startup_retry_entry.py) 的 `run_host`、`guest_command`、`collection_command` | 首次 SSH/sudo/Python probe 返回后才构造 anchor；outer 与 collector 分别派发 | 后置相对期限不能追溯保护首次探测；collector 不自动属于 outer |
| [owner](../../tests/e3_host/q2_prepare_run.py) 的 `owner_identity`、owner 派发与清理 | endpoint 必须在 supervisor 停止树外；先提交、后观察 original | endpoint 独立性需要保留；缺 original 不能当作没有派发 |
| [supervisor](../../tests/e3_host/q2_supervisor.py) 的 `command`、`observe_start`、`stop_original`、清理分支 | 固定 `systemd-run --system`；已有原实例才能使用原停止证明 | 原提交是否仍会晚到，不能由之后的一次 stop/show 推出 |
| [管理域 adapter](../../tools/admin/local_hand_quota_observer/q2_runtime.py) 的 `command` | `--system` 直接派发，按独立 query/management parent 设置 `Slice` | manager 新建 unit 不因调用者在 outer 内就成为 outer 的子进程树 |
| [既有 broker](../../tools/local_hand_jobs/broker.py) 与 [runner](../../tools/local_hand_jobs/runner.py) | 启动 guard 只包围其登记的 runner 调用 | 它不是首次 SSH、outer、owner、supervisor、管理域和 collector 的全链强制入口 |

冻结 runtime 为 `b49d3df3d1e76813faf08e59ab4975e25279c2fc`。
上述事实来自准确仓库源码；没有以公开上游版本替代原机版本资格。

## 候选路线比较

| 候选 | 能提供的局部能力 | 准确缺口／本轮决定 |
| --- | --- | --- |
| 继续缩短相对 RuntimeMax、增加 Job timeout | 已激活 unit 或某个已排队 Job 的有限等待 | 不覆盖首次会话；相对开始点仍可能迟于原点；Job 取消也不等于 unit 停止。不能作为完整路线 |
| 停止 outer 或现有一个 parent | 对该准确实例及其真实子树执行停止 | 固定 sibling 与独立 collector 不被自动纳入；manager 未决请求仍需终结。不能扩大为全部域已停 |
| 给现 broker 旁挂 lease/watchdog | 可约束确实经过它的请求 | 冻结直接 `--system` 路径可绕过。该独占假设已被源码否定，不为这个假设另做可执行实验 |
| 预部署强制入口并使全部真实派发受控 | 在入口确实不可绕过时，可研究代际禁入与请求终结 | 必须改变调用路径或证明等价的外部控制；还涉及首次准备、来源、权限、费用和停止边界。当前没有准确 operational A，不安装 |
| 用整个 VM 或共享 manager/sshd 作为停止对象 | 控制范围更大 | 会触及未批准的对象或配置；现材料也不证明准确控制接口与资格。不是当前默认路线 |

单一可信底层的失败假设必须明确。普通 signal/timeout 不保证任意内核停摆或不可中断
I/O 都在三秒内消失。原 UNKNOWN/INCOMPLETE 是结果分类，不能充当已按期停止的证明。

## 必须分别证明的四件事

1. **事前有效。** 保护在第一项远端工作发生以前已经生效；通过这一项未受保护
   工作安装保护或取得其必要 mapping，不能再追溯证明该项受到保护。
2. **准确代际不再激活。** 同一 batch/generation 的新提交能力失效，并且每条在途
   请求已终结或已受到等价的迟激活拒绝。它不要求禁止全机器的其他合法工作。
3. **现有实例终止。** 逐个核对原 unit、InvocationID、PID、cgroup 身份、停止及树空；
   同名新实例不能补原实例的证据。空树、cancel ack 或 EOF 单独不能满足第二项。
4. **端点后置退出事实。** 局部 seal 形成后，由明确的外部观察者核对端点真实退出
   及原双流 EOF。保留冻结输出的自退未证字段；不能让端点在退出前自封“已退出”。

外部观察者的可信 OS/manager 边界、权限、隔离、时钟和失效结果应准确声明；
不需要无限增设“监督监督者”，也不能用此边界免除被测工作域的停止证据。

## 最短反例与判据

以下为静态推演及未来验收要求，**本轮没有执行这些现场实验**。

| 反例 | 不足的局部证据 | 应保留的结果 |
| --- | --- | --- |
| Start 请求发出后丢失回执，尚无 original | client 已退出、暂时没有 Job | `UNOBSERVED_PENDING`，不能补成未派发 |
| 一次 stop/空树之后，先前在途请求才到达 manager | stop 应答和该次树空 | 未来激活未禁；必须拒绝闭合 |
| 外层 unit 停止，query/management sibling 或 collector 仍活 | outer 的准确退出 | 域覆盖不全，保留独立未决项 |
| 第一个 SSH 输入越过原截止后才送达 | 到达后开始的相对超时 | 原期限未证，不准刷新原点 |
| 一个端点输出成功 seal 后挂住 | seal 内容完整 | 自退与原 EOF 未证 |
| 取消与首次实例绑定竞争，同 unit 换 InvocationID | 某个 cancel/stop 成功 | 不跨实例覆盖，不把未知补成成功 |

## 尚有价值但未启动的有限研究

后续[准确未决请求源码复核](Q2_H07_PENDING_REQUEST_SOURCE_REVIEW.md)已解析其中一个
候选：所查 systemd v255 的超时、断连、AddRef 回收及一般错误回复都不是启动
撤销事务，入队后也仍有错误返回点。无需为否定这一保证再做现场试跑。
同时明确本页“直连”意为绕过本仓库 broker；项目的 `--wait/--pipe` 在所查版本
选择 system bus，不能混称必然走 manager 私有 socket。以下较广问题仍须
先给出具体服务端终结/禁入原语；不得继续以客户端退出充当这个原语。

贴近原链的未知问题是：**在一个准确版本的隔离 system manager 中，针对准确单条
已经提交、尚未收到 Job/实例回执的 StartTransientUnit，请求层能否取得有界且可信
的终态证据？** 可以研究原请求、原连接、manager 接收/Job 身份及停止结果之间的关系。
不同连接上的后来一次查询不是默认的全局处理屏障；不得用轮询“暂时没有”代替证明。

若选择可执行实验，先固定单一候选原语、manager 版本、独立 fixture/epoch、准确
资源和 setup/清理权限、故障注入方式与停止条件，并核对既有 H4 是否已经覆盖。
既有范围内的隔离验证无需重批；只有新增设施、权限或机制等实质变化才形成
该最小受影响范围的三文档 A，按 R 取得准确决定后实施。
fixture 预置不证明原机 prearm；只用合成对象，不用原 Q2 私有定位或消费权。
未知停止、残留或缺 EOF 即停止后续 case，不换 ID 重试补成功。
这一局部实验即便成功，也不证明首次 SSH、跨钟、全域禁入或原链已可接线。
在候选尚未固定时，不请求 Owner 批准“任选机制”的实验或现场安装。

原 CLOSED 内的离线来源、费用覆盖和模型修复可以继续；完整账单、FS 资格与
工具/环境采用独立成立后，才可能进入原 H3/H5 的条件接线。
相同 11 项补证和权限维护无需重做，新 startup batch 仍 **NOT ISSUED**。

## 一手资料与适用边界

- systemd 固定上游 `db11bab38ccf1ed257f310d29070843d4c58ea01`：
  [service](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.service.xml)、
  [unit](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/systemd.unit.xml)、
  [manager API](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/man/org.freedesktop.systemd1.xml)。
  RuntimeMax、Job timeout、Stop/Cancel 各有不同作用；这些接口没有自动提供本项目的
  全代际禁入证明。最后一项判断是结合固定调用链作出的推论。
- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html)：populated、freeze、kill
  作用于相应进程子树；据此不能推断独立 manager 未来不再创建单位。
- [OpenSSH sshd_config](https://man.openbsd.org/sshd_config.5)：关闭超时 channel 不保证
  所有关联资源终止，也不自动禁止再次请求 channel；ForceCommand 使用登录 shell。
  这是机制参考，不证明现场 OpenSSH 版本或配置，更不授权修改它们。

上游资料用于解释能力边界，不作为当前 host/guest 二进制、部署、时钟或预算资格。
