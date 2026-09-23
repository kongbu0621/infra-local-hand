# E1 受监督启动准备与结果读取：内部实现边界

本说明记录已批准 E1–E3 范围内的内部实现检查点，不修改需求、架构和实施方案的批准原文，不新增公开 Task／七工具参数或生产部署授权。[启动准备验证报告](E1_BOOTSTRAP_VERIFICATION.md) 记录上一源码检查点 `4be98b8`；其中的测试与构建结果不能代替本次结果读取实现的验证。

**当前仍不可部署。** `SystemdManager.support()` 固定返回含 `E3_SUPERVISION_UNVERIFIED` 的 `UNSUPPORTED`；没有配置开关把合成测试变成真实 E3 验收。NAS 硬配额 provider 仍缺失，E1 整体和 E1–E3 全部出口都未完成。完整状态见 [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)。

## 1. 解决范围与文件责任

原实现将任务目录、配额检查与计划文件写入放在 broker 的 observer 线程中。线程不能独立停止被阻塞的文件系统调用。上一检查点把这些启动准备动作放入独立 bootstrap unit，完成后才允许交付正式 helper unit。本次再把 helper 结果文件的打开、读取和核验移入独立 result-reader unit；observer 只接收有界非阻塞匿名管道帧，不再读取任务盘上的结果文件。

| 模块 | 当前责任 |
| --- | --- |
| `policy.py` | 接收私有 profile 的预建 slot 身份和可选 evidence store 身份，校验目录边界、别名及共享资源约束 |
| `bootstrap_roots.py` | 仅做数据校验与本地账本操作；分配、持久消费和核对 root grant，不探测任务目录或挂载盘 |
| `broker.py` | 在执行意图事务中消费 slot 并冻结监督版本；分别保存三个内部阶段的交付意图；每次交付前复核当前授权、取消、版本、预算与资源状态 |
| `bootstrap.py` | 有界内部计划编码；在受监督进程中检查 namespace、cgroup、目录身份和硬配额，发布归属标记与 create-only 计划 |
| `budget.py` | 固定阶段绝对截止时间及该监督版本的内部 CPU 分额，不新增一次公共操作预算 |
| `runner.py` | 三个确定性 unit 身份、依次推进、退出证明、取消、原身份恢复；helper 写入前再次核对 root 身份；observer 只作有界 IPC 接收 |
| `result_reader.py` | 受监督进程内核对原 result 的目录／文件／内容身份，输出 READY/RESULT 帧；父端解析器只处理内存中的有界字节 |

进程内仍读取必要的主机／systemd 状态。这里的隔离范围是任务启动准备与 helper 结果读取，不是宣称 broker 已不做任何 I/O。

## 2. 私有预建 root 准入

受信部署侧预先创建每个 slot 的 `work`、`temporary`、`evidence` 三个独立目录，并配置独立账户、权限及可核验的硬配额。执行器不创建 profile 父目录、不自行挂载、不授予 delegation、不调整配额，也不从用户请求接收可写路径。

每个 slot root 必须是对应 `work_root`／`temporary_root`／`evidence_root` 的严格后代；目录、inode 或相互包含路径不能制造另一份可用 slot。跨 profile 同样检查冲突；不能进入 broker、authority、禁止路径或只读输入范围。准入数据中的身份只是声明，真实身份仍须在 bootstrap 内观察。

| 私有 profile 字段 | 结构和含义 |
| --- | --- |
| `bootstrap_slots` | 1–1024 项的有限数组；每项恰有 `slot_id` 和 `roots`，slot ID 符合既有 ref 格式且不重复 |
| `roots` | 恰有 `work`、`temporary`、`evidence`，各自为一个 root binding |
| root binding | 恰有 `path`、`device`、`inode`、`uid`；path 是规范绝对路径，数值为受限整数，inode 大于零；声明 uid 与适用的 process-manager 账户一致 |
| `bootstrap_evidence_store` | 可选 root binding；有此字段时必须声明 slot 池。它是 evidence 阶段唯一可增加的保留写入目录，须准确等于 broker 的 EvidenceStore 根 |

保留 evidence store 不属于可回收 slot，不与任一任务父树、NAS writable tree 或 slot 重叠／别名。多个 profile 若共享它，必须是完全相同的 binding，并有共同 resource ID 使既有资源租约协调该写入范围。内部 `extra_roots` 只接受 evidence 阶段的 `evidence_store`，不构成任意附加目录接口。

实际服务装配要求同一 broker 的 bootstrap profiles 使用同一个准确 evidence store；按已准入身份打开预建目录，不在控制根下另建替代目录。重启库存检查从持久 execution/root grant 及监督版本推导确定性 unit：旧 version 2 为两个，新 version 3 为三个；不把任意附加 manager unit 字段当成已授权身份。

以下仅为**结构说明用的纯合成 profile 片段**。路径和设备／inode／uid 均为虚构值；它缺少完整 policy、实际目录、账户、配额、服务与验收条件，不能部署或直接运行：

```json
{
  "work_root": "/synthetic/local-hand/work",
  "temporary_root": "/synthetic/local-hand/temporary",
  "evidence_root": "/synthetic/local-hand/evidence",
  "bootstrap_slots": [
    {
      "slot_id": "example-slot-01",
      "roots": {
        "work": {"path": "/synthetic/local-hand/work/slot-01", "device": 42, "inode": 101, "uid": 12345},
        "temporary": {"path": "/synthetic/local-hand/temporary/slot-01", "device": 42, "inode": 102, "uid": 12345},
        "evidence": {"path": "/synthetic/local-hand/evidence/slot-01", "device": 42, "inode": 103, "uid": 12345}
      }
    }
  ],
  "bootstrap_evidence_store": {
    "path": "/synthetic/local-hand/retained-seals", "device": 42, "inode": 104, "uid": 12345
  }
}
```

这些字段保存在私有部署 policy，不进入公开源码默认值或公共 job request。Base64 计划是进程参数传输，不提供加密或秘密存储。

## 3. 一次消费与持久身份

Root grant 绑定 namespace、record ID、operation ID、execution ID、phase、slot ID、allocation ID、根路径／目录身份和 digest。账本保存 `BOOTSTRAP_ROOTS_RESERVED` 事件及独立 allocation owner 的路径／inode leases；消费与对应 `EXECUTION_INTENT` 在同一事务内提交。

业务阶段沿用**同一操作已经消费的 preflight slot**，核对原身份与归属标记。evidence、reconcile 及其 evidence 阶段分别消费新的空 slot。它们不是将旧 slot 释放后重新分配：同一历史 grant 的重取保持原身份，其他操作不能复用。

取消、失败、UNKNOWN、超时或 broker 重启均不退还 slot；普通 operation resource release 不删除 allocation owner 的永久消费记录。没有剩余 slot 时拒绝分配，不自动扩池或按超时抢占。修改 inode、改目录名、删历史 lease 或清空目录都不是受支持的复用方法；后续容量管理需要另行定义可追溯生命周期。

## 4. 三个固定单元与独立交付

新执行意图在投递前持久冻结 `supervision_version=3`。同一个 phase 的三个 unit 均使用 `lhj-<SHA-256>.service`：bootstrap 摘要输入为 `execution_id + ":bootstrap"`，helper 为原 execution ID，result-reader 为 `execution_id + ":result_reader"`。三者共享该 phase 的 root allocation 和原预算，分别保留交付及执行身份；reader 不再分配一个 root slot，也不获得任何任务目录写权限。

1. broker 完成持久意图后，runner 构造固定 bootstrap 命令；尚不打开任务根、查询其配额或写入计划文件。
2. 第一次 durable guard 核对当前取消、撤权、部署／策略代次、资源所有权、预算与 slot 消费，记录 `execution_id:bootstrap` 的唯一交付意图，再交付启动请求。
3. bootstrap 在独立 namespace/cgroup 中重新检查精确根身份、私有权限、回落写入位置和实际硬配额；只写已消费根下的归属标记及 create-only 计划，完成 fsync 和最后身份／截止时间检查后才返回成功。
4. observer 根据原 boot、unit、invocation、cgroup 的 systemd 状态确认 bootstrap 已退出、递归进程树为空、queued job 为空且退出码为零；这一分支不通过读取任务盘结果文件来证明准备成功。
5. 第二次 durable guard 再核对当前授权、取消、版本、资源和预算；确认准备证明准确绑定本 execution/unit，登记 `BOOTSTRAP_COMPLETE` 与 `execution_id:helper`，才允许 helper 启动。
6. helper 在自己的受监督边界内、产生写入前再次检查 allocation 和目录身份；业务结果仍按既有结果合同解释。
7. observer 独立确认原 helper 的 queued job 与递归进程树均已退出；只有退出码或命令行客户端退出不够。此时尚未验证业务结果，不能据此判定业务成功。
8. 第三次 durable guard 确认 version 3 是原执行意图已经冻结的版本、前两次交付确实存在，保存原 helper 退出证明与 `execution_id:result_reader` 交付意图。取消、撤权或预算不足均阻止新 reader 启动，不改用 observer 直接读取。
9. 固定 reader 在受监督、只读的任务目录视图内检查原 evidence root 与确定性 result 文件，输出有界帧。父端将帧中的 helper／reader 身份与独立 systemd/cgroup 观察绑定；只有完整帧和 reader 成功退出、进程树为空、本地 collector 已停止都成立，才接受该业务结果。最终仍保留原 helper 的退出码，reader 成功不等于业务成功。

任一次 Popen 调用后的异常或回执丢失都不能证明“未开始”。已发生或可能发生的交付保留原 handle 和 UNKNOWN／资源屏障，不因重试换一个 unit 或清空历史。bootstrap 失败或部分写入也不释放已消费根。

Reader 使用 `systemd-run --pipe`。该客户端会等待服务结束；`RemainAfterExit=yes` 又使已退出的服务保留 active/exited 身份，因此客户端 `poll()` 不能用作启动 ACK 或 unit 退出证明。管理器按准确 unit、invocation 和 cgroup 观察／停止 reader，即使本地客户端仍存活。原 reader 退出已确认后，父端只清理自己保留的本地客户端与管道；杀掉客户端从不代替 unit 退出证明。

## 5. 有界内部参数与硬配额

Bootstrap argv 传递规范 JSON 的 Base64，原始 JSON 上限为 **64 KiB**，编码长度另有上限；同时按宿主单参数限制与总 `ARG_MAX` 检查 argv 和固定环境，超限在交付前拒绝。内部对象有嵌套上界，拒绝重复 JSON 键、非规范编码和不允许的数据类型。

Reader 复用这个有界 argv 编码，只接收准确 execution／phase、原预算、root allocation、原 helper 身份和确定性结果文件名。结果正文上限为 **1 MiB**；READY/RESULT 两帧另有固定头部和总字节上界，帧头余量不能扩大正文上限。父端每轮最多非阻塞读取 64 KiB；完整帧、顺序、重复／尾随字节、JSON 复杂度和身份均核验。未能建立非阻塞模式时绝不尝试读该管道，也不退回磁盘文件。

传输只应包含固定执行计划、路径引用、预算及 root grant，不传认证凭据或完整私有 policy。实现拒绝已列出的凭据字段及非固定环境变量；这不是对任意文本的通用秘密检测，也不允许把秘密放进其他字段来规避该边界。

目录检查使用保留描述符和预先声明的 device/inode/uid；配额观察也绑定同一根身份。当前查询仅支持实现声明的 ext4/xfs project hard-quota 路径，要求继承 project ID 和非零有限硬上限，并按去重后的 quota 身份核对总保留容量。成功的字段检查不证明某台真实磁盘上的配额已生效；真实文件系统行为归 E3。网络 NAS 配额不能由本地布尔值代替，相关 provider 仍明确不支持。

## 6. 固定预算与恢复

Phase 绝对结束时间在持久预留时确定，为 operation 截止时间与 `reserved_boottime + phase wall` 的较早者。启动准备、管理器排队、三个内部单元及阶段间隙共同消耗这个窗口，并在其中保留终止宽限；交付、各受监督入口和执行过程继续检查原 boot／截止时间。Reader 只能使用原窗口剩余时间；前面已经用尽时，结果保持 UNKNOWN，不补一段读取时间。

Version 3 的 phase CPU 预算给 bootstrap 与 reader 各 `floor(total/3)`，helper 获得剩余部分。旧 version 2 保留原 bootstrap 向下取整一半、helper 取得余数的分额；不能在旧预算上补发第三份。各份不足以执行时拒绝，不向上补足，不退款、不续额。三个任务单元顺序执行，共享内存／进程／存储峰值约束；bootstrap stdout/stderr 为 null，只有 helper 使用原日志额度，reader 帧是另有固定大小上界的结果传输，不写一份新磁盘日志。配置算术仍不等于真实全进程树累计 CPU 物理上限验收。

| 恢复对象 | 当前行为 |
| --- | --- |
| 旧版单 unit receipt | 按旧身份、boot、invocation、结果路径和保存的预算观察／受控停止；不创建 bootstrap／reader，也不重放旧启动；observer 不再读取旧结果文件 |
| `manager.version=2` | 保留两个子 handle、allocation digest 和原 CPU 分额；只观察／停止原身份，不接续启动、不升级第三单元、不直接读取结果 |
| `manager.version=3` | 保存三个子 handle 和 allocation digest；恢复时独立观察／停止每个原身份，不接续任一新交付，丢失的管道不重新创建 |
| 首次观察前崩溃／子 receipt 缺失 | 按原持久版本推导确定性原 unit，不用“没有保存回执”证明从未投递；不能据此重新启动 |
| 预算损坏或失效 | 不分配新运行时窗；可独立确认的原身份继续用于观察和停止，身份不明则保留 UNKNOWN |

恢复后如果三个原 unit 都已证明无 queued job 且进程树为空，这些事实可独立成立；丢失结果管道不能把真实退出事实也改成未退出。此时保留原 helper 退出码及 `future_start_blocked/tree_exited/writers_stopped=True`，但结果为 UNKNOWN、`effects_checked=False`、`helper_result_verified=False`。旧本地 `systemd-run --pipe` 客户端可能仍在观察 systemd，不能证明已清理，因此 `collectors_stopped=False`。它不再执行任务或写任务盘；不按未知 PID 杀进程，也不以这种情况伪造 collector 已停止。

该分离证明允许按既有合同和当前授权显式启动独立 reconcile；不能据此封存或释放原业务资源，也不把新的核对变成重跑原程序。若任一原 unit 的排队／退出仍不明，就继续保留原执行屏障。一般恢复屏障保持；既有“已完成且已冻结工作第一次证据封存”的窄准入仍须满足包括 collector／effects 证明在内的单独条件，不能绕过丢失管道或重放任何已交付单元。

上述 `--pipe` 等待、一次启动请求与其后重连观察的源码依据是 systemd v257 固定提交 [`70bae7648f2c18010187c9cf20093155eaa26029`](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/src/run/run.c) 及[同提交手册](https://github.com/systemd/systemd/blob/70bae7648f2c18010187c9cf20093155eaa26029/man/systemd-run.xml)。这不是当前宿主或所有 systemd 版本的真实 E3 验收。

## 7. 尚未完成的真实边界

本次已移除 `_inspect_unit` 对 helper 结果文件的直接读取，包括旧 receipt 路径。结果读取挂起现在属于独立 reader unit；控制观察只接收非阻塞管道。但 reader 被超时或 KILL 仍不等于已退出，恢复后丢失本地客户端／管道的限制也没有被隐藏。这不是全部存储接口都已完成实际验收的声明。

真实 E3 至少仍需核对：部署账户与 slice/cgroup 委派、三个 unit 的 namespace/资源约束、真实配额、子孙进程和延迟启动、每个交付／回执窗口的 broker 崩溃、阻塞准备与结果读取 I/O、匿名管道和本地客户端生命周期，以及挂起时取消与受控停止是否仍可达。未确认未来启动已阻断及完整进程树退出时继续 UNKNOWN。若真实证据推翻实现假设，应按既有变更规则修正，不改验收目标。

上一检查点的宿主 AF_UNIX 限制和 Linux CI 准确结果仍由其[验证报告](E1_BOOTSTRAP_VERIFICATION.md) 记录，不能当作本次运行结果。E4 当前客户端连接／文件桥接、E5 GX10/S2 切换、E6 真实 NAS 恢复不由本说明完成或扩大授权。`E3_SUPERVISION_UNVERIFIED` 保持固定生产封堵。
