# E1 受监督启动准备：内部实现边界

本说明记录已批准 E1–E3 范围内的内部实现检查点，不修改需求、架构和实施方案的批准原文，不新增公开 Task／七工具参数或生产部署授权。准确候选提交、测试结果和构建产物由后续验证报告固定，此处不预填最终成绩。

**当前仍不可部署。** `SystemdManager.support()` 固定返回含 `E3_SUPERVISION_UNVERIFIED` 的 `UNSUPPORTED`；没有配置开关把合成测试变成真实 E3 验收。NAS 硬配额 provider 仍缺失，E1 整体和 E1–E3 全部出口都未完成。完整状态见 [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)。

## 1. 解决范围与文件责任

原实现将任务目录、配额检查与计划文件写入放在 broker 的 observer 线程中。线程不能独立停止被阻塞的文件系统调用。本次把这些启动准备动作放入独立 bootstrap unit，完成后才允许交付正式 helper unit。

| 模块 | 当前责任 |
| --- | --- |
| `policy.py` | 接收私有 profile 的预建 slot 身份和可选 evidence store 身份，校验目录边界、别名及共享资源约束 |
| `bootstrap_roots.py` | 仅做数据校验与本地账本操作；分配、持久消费和核对 root grant，不探测任务目录或挂载盘 |
| `broker.py` | 在执行意图事务中消费 slot；分别保存 bootstrap/helper 交付意图；第二次交付前核对准备证明及当前授权、取消、版本与资源状态 |
| `bootstrap.py` | 有界内部计划编码；在受监督进程中检查 namespace、cgroup、目录身份和硬配额，发布归属标记与 create-only 计划 |
| `budget.py` | 固定阶段绝对截止时间和两个内部单元的 CPU 分额，不新增一次公共操作预算 |
| `runner.py` | 两个确定性 unit 身份、依次推进、退出证明、取消、原身份恢复；helper 写入前再次核对 root 身份 |

进程内仍读取必要的主机／systemd 状态。这里的隔离范围是任务启动准备，不是宣称 broker 已不做任何 I/O。

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

实际服务装配要求同一 broker 的 bootstrap profiles 使用同一个准确 evidence store；按已准入身份打开预建目录，不在控制根下另建替代目录。重启库存检查从持久 execution/root grant 推导两个确定性 unit，准备单元不会被误判为孤儿。

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

## 4. bootstrap 与 helper 两次交付

同一个 phase 使用两个确定性 unit：bootstrap 名称由 `execution_id + ":bootstrap"` 派生，helper 保持原 execution ID 派生名称。二者共享该 phase 的 root allocation 和预算，分别保留交付及执行身份。

1. broker 完成持久意图后，runner 构造固定 bootstrap 命令；尚不打开任务根、查询其配额或写入计划文件。
2. 第一次 durable guard 核对当前取消、撤权、部署／策略代次、资源所有权、预算与 slot 消费，记录 `execution_id:bootstrap` 的唯一交付意图，再交付启动请求。
3. bootstrap 在独立 namespace/cgroup 中重新检查精确根身份、私有权限、回落写入位置和实际硬配额；只写已消费根下的归属标记及 create-only 计划，完成 fsync 和最后身份／截止时间检查后才返回成功。
4. observer 根据原 boot、unit、invocation、cgroup 的 systemd 状态确认 bootstrap 已退出、递归进程树为空、queued job 为空且退出码为零；这一分支不通过读取任务盘结果文件来证明准备成功。
5. 第二次 durable guard 再核对当前授权、取消、版本、资源和预算；确认准备证明准确绑定本 execution/unit，登记 `BOOTSTRAP_COMPLETE` 与 `execution_id:helper`，才允许 helper 启动。
6. helper 在自己的受监督边界内、产生写入前再次检查 allocation 和目录身份；业务结果仍按既有结果合同解释。

任一次 Popen 调用后的异常或回执丢失都不能证明“未开始”。已发生或可能发生的交付保留原 handle 和 UNKNOWN／资源屏障，不因重试换一个 unit 或清空历史。bootstrap 失败或部分写入也不释放已消费根。

## 5. 有界内部参数与硬配额

Bootstrap argv 传递规范 JSON 的 Base64，原始 JSON 上限为 **64 KiB**，编码长度另有上限；同时按宿主单参数限制与总 `ARG_MAX` 检查 argv 和固定环境，超限在交付前拒绝。内部对象有嵌套上界，拒绝重复 JSON 键、非规范编码和不允许的数据类型。

传输只应包含固定执行计划、路径引用、预算及 root grant，不传认证凭据或完整私有 policy。实现拒绝已列出的凭据字段及非固定环境变量；这不是对任意文本的通用秘密检测，也不允许把秘密放进其他字段来规避该边界。

目录检查使用保留描述符和预先声明的 device/inode/uid；配额观察也绑定同一根身份。当前查询仅支持实现声明的 ext4/xfs project hard-quota 路径，要求继承 project ID 和非零有限硬上限，并按去重后的 quota 身份核对总保留容量。成功的字段检查不证明某台真实磁盘上的配额已生效；真实文件系统行为归 E3。网络 NAS 配额不能由本地布尔值代替，相关 provider 仍明确不支持。

## 6. 固定预算与恢复

Phase 绝对结束时间在持久预留时确定，为 operation 截止时间与 `reserved_boottime + phase wall` 的较早者。启动准备、管理器排队、两个内部单元及阶段间隙共同消耗这个窗口，并在其中保留终止宽限；交付、helper 入口和执行过程继续检查原 boot／截止时间。

Phase 的 CPU 预算固定分为 bootstrap 的向下取整一半，以及 helper 的剩余部分。两个单元各设置对应 CPU 限额；份额不足以分别执行时拒绝，不向上补足，不退款、不续额。两者顺序执行，共享内存／进程／存储峰值约束；bootstrap stdout/stderr 为 null，只有 helper 使用既有日志额度。配置算术仍不等于真实全进程树累计 CPU 物理上限验收。

| 恢复对象 | 当前行为 |
| --- | --- |
| 旧版单 unit receipt | 按旧身份、boot、invocation、结果路径和保存的预算观察／受控停止；不创建 bootstrap，也不重放旧启动 |
| `manager.version=2` | 保存 bootstrap/helper 两个子 handle 和 allocation digest；分别核对原身份，恢复后只观察／停止，不接续 bootstrap→helper 启动转换 |
| 首次观察前崩溃／子 receipt 缺失 | 仍核对两个确定性原 unit，不用“没有保存回执”证明 helper 从未投递；不能据此重新启动 |
| 预算损坏或失效 | 不分配新运行时窗；可独立确认的原身份继续用于观察和停止，身份不明则保留 UNKNOWN |

一般恢复屏障保持。既有“已完成且已冻结工作第一次证据封存”的窄准入仍须满足其单独条件；它不授权重放已交付的 bootstrap 或 helper。

## 7. 尚未完成的真实边界

本次没有把所有 storage I/O 迁入独立进程。正式 helper 退出后，既有 `_inspect_unit` 仍在 observer 线程调用 `bounded_regular_bytes` 读取结果文件；字节数上界无法给阻塞磁盘／挂载 I/O 提供时间上界。该路径并非本次新增，但仍可能影响后续观察及取消／停止可达性，不能被启动准备隔离的完成描述掩盖。

真实 E3 至少仍需核对：部署账户与 slice/cgroup 委派、两个 unit 的 namespace/资源约束、真实配额、子孙进程和延迟启动、每个交付／回执窗口的 broker 崩溃、阻塞准备 I/O，以及上述结果读取阻塞时取消与受控停止是否仍可达。未确认未来启动已阻断及完整进程树退出时继续 UNKNOWN。若真实证据推翻实现假设，应按既有变更规则修正，不改验收目标。

旧宿主的 Unix socket `EPERM` 只保留在原报告；本次宿主是否支持及准确源码运行结果随后独立记录。E4 当前客户端连接／文件桥接、E5 GX10/S2 切换、E6 真实 NAS 恢复不由本说明完成或扩大授权。`E3_SUPERVISION_UNVERIFIED` 保持固定生产封堵。
