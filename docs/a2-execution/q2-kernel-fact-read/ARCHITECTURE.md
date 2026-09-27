# Q2 固定内核事实读取：架构补充

- Authority：Owner；状态：**PROPOSED / Gate OPEN / AWAITING OWNER**。
- Scope/R 与[需求](REQUIREMENTS.md)一致；仅在独立 B/C 后实施。

## 组件边界

增加独立的固定内核视图读取器，供 `q2_host_window_preflight` 使用。其入口按
内部枚举选择 boot 或自身 mountinfo；不接受调用者任意路径、PID 或可关闭保护的开关。
原 `q2_reconciliation_io`、证据文件/目录读取、消费入口及 full execution 保持不变。
专用读取器不执行外部命令、不接触 guest、不建立标记或生成 host 文件。

boot 仍在父目录/消费路径/证据树观察之前读取并匹配旧 pin；只有 boot 合格才继续
原预检。mountinfo 保持原文件系统观察时机，使用 `os.getpid()` 的十进制路径，
不用 `/proc/self` 符号链接。两次读取都计入接收器最早的原双钟和准备预算。

执行环境限定为原 host 的已有本机终端，未进入容器或新的 PID/mount namespace。
该进程 PID namespace 与原 `/proc` 挂载对应，是本范围明确的可信环境前提。
数字 `getpid()`、procfs magic、mount ID 或 boot 匹配单独均不证明这项对应；
报告须将其标作环境假设，不冒充已测证明。已知不对应或无法满足该使用环境
则停止，不进入/重挂 namespace，也不另读其它 proc 文件来扩大本范围。

## 内容读取前的资格与绑定

1. 以 `O_PATH|O_NOFOLLOW|O_DIRECTORY|O_CLOEXEC` 逐段持有根及祖先，验证
   类型、允许 owner（root/当前 euid）、非群组/其它用户可写及名称到 fd 身份。
   不对这些 fd 读内容或枚举目录。叶项先以 no-follow `O_PATH` 持有并验证普通
   文件类型、单链接及保护；拒绝 symlink、设备或其它类型。
2. 对 `/proc` 及其下所有 held 对象执行 fd 级 `fstatfs` 与
   `statx(AT_EMPTY_PATH)` 的挂载 ID 元数据查询。必须是 `PROC_SUPER_MAGIC`
   (`0x9fa0`)，且同一 proc 挂载 ID/设备；禁止跨入子挂载或以同名字串代替证明。
   `statx` 请求 `STATX_MNT_ID`（0x1000），返回 `stx_mask` 必须包含该位，并
   比较 `stx_mnt_id`；无支持、无法绑定或调用失败均阻断。持有原挂载引用直到
   读后复核，避免把已释放挂载 ID 的复用当作原对象身份。
3. 从 held 父 fd，以 `O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK` 打开固定叶项，
   **明确不加 `O_NOATIME`**。读前复核与 O_PATH 对象相同的设备/inode、类型、
   owner/mode/nlink、procfs 类型及挂载 ID，并复核全部 held 名称链，之后才能读。
4. 读取及 EOF 检查有界：boot ≤64 bytes；mountinfo ≤1 MiB；每步检查原双钟。
   读后再核对名称、fd、挂载及保护身份。boot 格式及旧 pin 保持原严格检查。
   不用未知长度 `read()`，不把 stat size=0 当作 proc 内容长度。
5. 报告两个内核视图读取前后可得元数据、实际长度/摘要、资格检查及错误。
   内核视图的访问/动态元数据变化单独记录，不作为历史文件完整性通过；
   设备/inode、mount ID、类型、owner/mode/nlink 变化仍拒绝。证据文件的
   原全字段元数据比较不受影响。

资格从无内容读取的 fd 系统调用取得，不依赖先读 mountinfo 才能批准 mountinfo
自身读取。不存在先用旧方式失败后去掉标志重试的分支；只对上述两项采用明确
独立的读取合同，其余对象继续走原严格读者。

## ABI、错误与审计

初始支持范围限定为原 host 的 Linux x86_64、64-bit native ABI，使用已有
Python 标准库 `ctypes` 调用当前进程已有 libc 的 `fstatfs/statx` 符号。结构布局、
整数宽度与返回 mask 必须有独立验证；缺符号、不匹配或未知平台即阻断。
不编译/安装 host helper，不下载依赖，不使用随意 syscall number 或遍历进程。
原 `O_PATH` 链保护对证据读取的语义保持；此组件不改变进程 namespace。

错误记录固定操作标签、固定目标类型及准确 errno；不再把所有 `PermissionError`
命名为已经确定的 O_NOATIME 原因。无错误可升级 READY；异常/超时按原边界关闭
fd、恢复终端并输出有限 JSON。该结果不是新的持久封存或批次执行权。

读取引发的内核视图元数据及原生审计按 K03/原 A 边界处理；未知账单仍缺失。
无需也不得通过提权、remount、时间戳回写、替换 boot pin 或降低证据保护来通过。

## 选型与未采用路线

| 路线 | 判断 |
| --- | --- |
| 原样重跑旧包 | 无法消除相同权限约束，保留作历史拒绝证据 |
| sudo/CAP_FOWNER/改 owner | 扩大现场权限且影响其它边界，不采用 |
| 所有文件去掉 O_NOATIME | 破坏原证据保护，不采用 |
| 只看 `/proc` 路径前缀 | 不能证明实际文件系统与挂载对象，不采用 |
| 固定两项 + fd/挂载资格 + 普通读取 | 本提案选择；需要本窄范围 B/C 与实际验证 |

官方接口依据见[现场复核](../Q2_LOCAL_PREFLIGHT_FIELD_REVIEW.md)；它们证明接口
语义，不证明原 host 已经满足 ABI、访问权限及挂载资格。
