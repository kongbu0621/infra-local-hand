# Q2 首批：严格协议、事实绑定与有界客户端

状态：2026-09-25 实现合同；遵循批准 A 的 8 KiB 请求、32 KiB 响应和原 deadline。
前置依据为 [Q1 限定 guest 复核](E3_QUOTA_Q1_GUEST_CAPACITY_REVIEW.md)。
本批实现无特权纯协议及客户端，不安装 listener、不查询 quota，也不启用普通作业入口。
服务端持久防重、多根查询装配、管理预算和 bootstrap 接线属于 Q2 后续批次。

## 字节、传输和身份

Linux AF_UNIX / SOCK_STREAM，一连接一次请求和响应。每帧为四字节 big-endian 长度，
随后精确长度的 UTF-8 JSON；长度不含四字节头。请求发送后 client 关闭发送方向；响应后
server 必须关闭发送方向。client 必须在原请求的 BOOTTIME deadline 内收到完整响应和 EOF。
额外字节、超长、半包、缺 EOF、peer 不符、异常 ancillary data 均失败；不重新连接或重发。
所有收到的 SCM_RIGHTS 描述符在拒绝前关闭；不把传入 FD 暴露给调用者。

严格拒绝重复键、额外键、NaN/浮点、布尔伪整数、非法 UTF-8、surrogate、溢出和深度超限。
请求最大 8192 bytes / 深度 4；响应最大 32768 bytes / 深度 6。规范字节为排序 ASCII 键、
无空白的 JSON，ensure_ascii=true；摘要覆盖全部请求字段，包括原绝对 deadline。
时间与一般计数使用 0..2^63-1；UID/GID 和 project ID 使用准确较小范围。

endpoint 来自 bootstrap 受保护安装配置，不由请求携带。client 核对绝对 canonical 路径、
管理员保护且不可被普通身份替换的祖先、socket owner/权限及前后 inode，再以 SO_PEERCRED
核对服务 UID/GID，PID 仅作观测。不能用同 UID 判定服务端所见的客户端角色；服务端还需
后续批次的 bootstrap 阶段、分配和入口隔离校验。通信成功不授予启动或释放资格。
客户端对 socket 拒绝所有 other 权限及特殊权限位；祖先拒绝 group/other 写权限。

## 请求 v1

所有字段必填，无路径、quota ID、FD、argv 或预算覆盖字段。

| 字段 | 类型/约束 |
| --- | --- |
| schema / operation | local-hand-quota-observe/v1 / observe |
| request_id | 32 位小写 hex |
| authority_digest / installation_digest / manifest_digest | 64 位小写 hex |
| epoch / generation | 32 位小写 hex |
| boot_id | canonical 小写 UUID |
| slot_ref | 1..128 位已有 ASCII ref 格式 |
| execution_id | 保留完整 namespace-record-phase；1..200 位已有 runner 标识符字符集 |
| phase | preflight / business / reconcile / evidence；执行 ID 的结尾与 phase 一致 |
| allocation_digest / observation_grant_digest | 64 位小写 hex；仅摘要校验不等于授权 |
| deadline_ns | 原绝对 CLOCK_BOOTTIME 截止时间，正整数 |

Q1 的 execution_id=32hex 不作静默兼容；Q2 请求完整保留 job/reconcile 执行身份。
query unit 固定为 `lhqo-<规范请求 SHA256>.service`，不接受响应提供其他 unit 来替代绑定。

## 响应 v1

准确字段为 schema、request_digest、status、reason、deadline_ns、started_ns、finished_ns、
query、roots、calls、exit。schema 为 local-hand-quota-receipt/v1。
status 为 OBSERVED / UNKNOWN / REJECTED / UNSUPPORTED；reason 为有限 ASCII 诊断码。
失败可保留已获得的完整 root 事实和 syscall 前缀，不能生成伪造的零 errno。

query 可为 null（未取得启动身份），否则准确字段为 unit、invocation_id、cgroup。
它必须属于原确定 unit；cgroup 为绝对 canonical 路径，末级为该 unit。
成功时 query 必须存在。退出元数据始终包含 proof_digest（可为 null）与以下事实：
delivery_settled、future_start_blocked、job_empty、unit_terminal、tree_empty、
collectors_stopped、stdout_eof、stderr_eof、exec_main_code、exec_main_status、client_returncode。
OBSERVED 要求全部布尔事实 true、code=1/status=0/client=0、proof_digest 非 null。
这些字段是受认证服务的报告，不是从任意 JSON 获得的独立 OS 证明。

每个 root 的准确字段为 role、device、inode、uid、gid、mode、filesystem、filesystem_uuid、
project_id、xflags、hard_bytes、accounting、enforcement、identity_unchanged。
role 为 work/evidence/temporary/retained_store；必须是普通身份的 0700 目录、非零 project、
有 project 继承、非零且按 1024 字节对齐的 hard limit。前三根必需；第四根仅允许 evidence
阶段，且必须与受信预期集合完全一致。拒绝根 inode 别名、FS UUID/device 矛盾、同域不同额度。
域以 FS UUID/project 去重，合计不得溢出；此计算不自行批准容量。

每次 call 的准确字段为 role、operation、rc、errno；每根只接受 STATE_BEFORE、GET_QUOTA、
STATE_AFTER 的有序前缀，最多 12 次。成功须每根三次 rc=0；成功 syscall 的原 errno 仍保留。
首个 rc=-1 后不能再有后续 syscall。响应中不得有额外角色或无对应固定根的事实。

成功事实必须与调用者从受保护配置取得的完整 expected roots 相等；禁止只检查某一根。
request digest、boot/epoch/source 安装关系由原请求绑定；receipt deadline 只能收紧。
OBSERVED 要求 started <= finished < receipt deadline，且消费时未过期。
格式、绑定或期限失败是客户端 UNKNOWN/拒绝，不触发查询重试或变更服务端原记录。

## 本批验证与后续门槛

覆盖准确字节边界/深度/类型、全字段绑定变异、多根/第四根/同域去重与矛盾、旧 phase/请求、
完整退出字段和原时限、真实 Unix socket 分片/半包/多余字节/缺 EOF/错误 peer/SCM_RIGHTS。
测试中的服务对端只发送合成事实，属于真实 IPC + LOGIC_ONLY；不能覆盖 systemd/quota。

本批的客户端只返回经过格式与绑定检查的不可变事实，不启动业务、不发布 bootstrap plan、
不修改 broker 账本、不释放资源。生产封堵保留。服务端来源认证、原预算准入、持久意图、
多根 query、全部 collector 的真实退出和 bootstrap 最终本地根复查完成后，才能接通后续阶段。

实际第一批源码、31 项逻辑通过及 11 项 IPC 未验证结果见
[客户端验证记录](E3_QUOTA_Q2_CLIENT_VERIFICATION.md)；本节描述的实测用例不代表已运行通过。
