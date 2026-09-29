# H07 未决启动请求：源码终态复核

2026-09-29；仓库基线 `ff0fdcd591507b55b43d5884297602f1c9f06b4a`。
上游 systemd 固定为 `db11bab38ccf1ed257f310d29070843d4c58ea01`（v255）。
这是静态来源研究，不是原机版本鉴证、隔离实验或现场运行。

**所查实现没有把客户端退出、等待超时或一般错误应答变成启动撤销事务。**
因此不再把“断开原客户端是否自动撤销”作为需要现场试跑才能判断的开放假设。
这项结论排除一个候选原语，不证明其他机制不可能，也不把 H07 判为完成。
准确 R/H A/C 沿用 [AGENTS](../../AGENTS.md)；本记录不改三层文档、Gate 或权限。

## 1. 先确定调用走哪条连接

本项目 outer 使用 `--system --wait --pipe`；owner 调用复用 supervisor 的同一组标志；
controller 同样使用它们；管理域 listener/admission/query 使用 `--system --pipe`。
参照固定仓库的 `q2_startup_retry_entry.guest_command`、`q2_prepare_run.command`、
`q2_supervisor.command` 和 `local_hand_quota_observer.q2_runtime.command`。

所查 [run.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/run/run.c#L1965-L1972)
在 `--wait` 或非 NONE stdio 时选择 `bus_connect_transport`；本地 system 分支走
[system bus](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/shared/bus-util.c#L270-L303)。
因此这些调用在此上游版本中不是 root 私有 socket 分支。
此前“直连 manager”准确含义是**没有经过本仓库 job broker 的强制准入入口**，
不是已经证明绕过系统 D-Bus daemon。现场二进制、环境和补丁仍未资格化。
不能据这个细节反推“现有总线策略已提供批次禁入”；当前材料没有该证明。

## 2. 请求、回执、引用回收各自证明什么

| 固定源码 | 可核对事实 | 本项目的结论 |
| --- | --- | --- |
| `run.c:1171–1239,1365–1373` | 构造 StartTransientUnit；同步调用失败直接返回 | 错误退出不是额外的 CancelJob/StopUnit 事务 |
| `sd-bus.c:2380–2528` | 发送请求后等待对应 reply cookie；超时/断连走错误返回 | 本地超时不证明 manager 没接收或已撤销；不能补为 NOT_SENT |
| `dbus-manager.c:1087–1123` | 权限处理之后构造瞬态 unit，最后提交 JOB_START | 请求存在多个处理阶段；“未收到 original”不标识服务端阶段 |
| `dbus-unit.c:1825–1842,1888–1919` | 先 manager_add_job，再跟踪 sender、构造路径/应答并发送 | 入队之后仍有失败点；一般 METHOD_ERROR 也不能统一解读成“没有 job” |
| `dbus-manager.c:1156–1172` 与 `dbus-job.c:43–66` | CancelJob 查准确 job ID，再结束该 job | 不是按未知请求 cookie 撤销尚未识别的启动；取消不代替运行实例停止 |
| `run.c:672–680` 与 `dbus-unit.c:2558–2572` | bus 客户端通过 AddRef 保留 unit；最后引用消失只触发空组/GC 检查 | AddRef 是生命周期引用，不是客户端死亡自动杀服务的租约 |
| `dbus-job.c:315–325`、`job.c:1432–1487` 与 `service.c:5074–5162` | sender 消失尝试 job GC；GC 要求类型的 gc_jobs，service vtable 未开启 | 本次 service 启动不能借 job 引用回收获得撤销保证 |
| `unit.c:433–495` | 有 job、active 状态或活进程等条件阻止 unit GC | 失去 AddRef 不等于停止、树空或永久禁止后续激活 |

“入队后仍可能错误返回”是明确控制流推论：`manager_add_job` 成功后，后面的
sender 跟踪、路径/消息分配或发送可能失败；所查返回分支没有对应的事务回滚。
不声称本机发生过这些故障，也不把所有错误都称为已入队。
同样，某些在创建前可准确定位的拒绝可证明更窄事实，但仅凭错误字符串不足以
证明其发生阶段、请求身份和未产生的副作用；不得增加一个通用“error=未启动”规则。

## 3. 对未来停止合同的具体约束

| 取得的事实 | 能保留的事实 | 仍不能清除的义务 |
| --- | --- | --- |
| 原调用超时、断连或客户端被杀 | 原客户端等待失败/退出 | 请求终结及可能的已创建 unit/job |
| 一般错误回复 | 原请求返回错误，须进一步分类阶段 | 入队/实例及早期瞬态对象副作用 |
| 准确 JobRemoved/canceled | 该 job 的结果，绑定原 manager epoch 与 job 身份 | 已运行实例、其他请求、后续提交 |
| 准确实例 stop、树空、原双流 EOF | 该实例及对应流的已观察终态 | 独立未决请求和未来激活入口 |
| 客户端引用消失、unit 被回收 | 相应引用/对象当时已不存在 | 同名对象未来重建与同批次晚到请求 |

因此，下一实际候选必须明确**哪一处有权阻止晚到请求产生执行副作用**，
以及原请求应答丢失时如何在原期限内得到服务端终态，不能把这些责任交给
客户端超时、AddRef 或事后轮询。固定 unit 名可辅助定位，但不能单独成为永久禁入标记。
关闭入口、排空在途请求、停止已运行实例和端点后置退出仍是四项分别验收的责任。

## 4. 本轮决定与后续入口

1. 不开展仅为演示“杀客户端后任务仍可能存在”的现场实验；静态证据已足以
   否定该保证。也不将成功 stop 一个已知实例的实验包装成全链监督验证。
2. 保留现有离线模型的 pending 与实际 fence 未证明语义；本轮不增加另一个
   模型、不修改生产停止路径，也不重跑已有 11 项补证。
3. 下一设计交付必须给出首次远端前有效的控制点和所有实际提交边的覆盖，
   明示冻结调用路径/既有管理机制中哪些保持、哪些确需改变，并附同一预算内
   的控制和收尾成本。若没有具体控制点，就仍是路线未成立，不能发布 READY。
4. 确有新机制或部署边界变化时，先做该最小范围的三层方案及准确 A，再按 R
   请求决定；既有 CLOSED 内的静态核查和明确不受影响的工作不需重复批准。
   本轮尚未提出可批准的实际安装 A，不让 Owner 预批未知设施或请求再次运行。

现场来源/版本、跨钟、首次会话、全域覆盖、FS 写前上界与完整共同账单仍独立
未闭合。完整 Q2 未验收，原新 startup batch 仍 **NOT ISSUED**。

## 来源与复核边界

上表行号均对应本页固定 systemd 提交。除已链接文件外：
[sd-bus.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/libsystemd/sd-bus/sd-bus.c)、
[dbus-manager.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/dbus-manager.c)、
[dbus-unit.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/dbus-unit.c)、
[dbus-job.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/dbus-job.c)、
[job.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/job.c)、
[unit.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/unit.c)、
[service.c](https://github.com/systemd/systemd/blob/db11bab38ccf1ed257f310d29070843d4c58ea01/src/core/service.c)。
九份读取内容的 UTF-8 摘要及项目调用位置登记于
[静态证据清单](evidence/q2-h07-pending-request-20260929/source-review.json)。
没有运行 systemd/SSH/guest 实验；静态推论不带有新测试 PASS 计数。
