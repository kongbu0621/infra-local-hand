# Q2 本地预检现场截图复核

本记录只保留 2026-09-27 +08 的两个用户截图中可见事实及代码解释。
原始终端 JSON 尚未以文本收到；以下不是重新构造的原始 JSON、完整 seal 或
独立 host 身份鉴证。原图留在 Owner 私有材料中，不公开用户名、host 路径/boot。

| 私有原图 | bytes | SHA-256 | 可见结果 |
| --- | ---: | --- | --- |
| `image(20260927-152409).png` | 480220 | `9d4ecb9bd23096374595d9b6154f0bc7789e69a351c3b3bdb4499162e904432e` | 接收器输出 `RAM_RECEIVER_INTERRUPTED_14`，未消费、未远端调用 |
| `image(20260927-152711).png` | 1088937 | `9abbbc60165d131c1578b884aca8d677a035e96a3d17c1abb2fb2cbad79d52ec` | `host_boot` 阶段返回 `HOST_LOCAL_KERNEL_NOATIME_PERMISSION` |

原图按上述准确文件名、长度与摘要定位在本会话 Owner 上传附件，私有持久标识
由原上传记录保存；可以凭摘要核对再次取得的 bytes。未把截图写入公共 Git，
也未声称它们已加入上一版私有 Git bundle。

## 第二张截图的可见事实

- `implementation_commit`：`0a456a909821fd1fc6a4fdec43b9e16bc88679f2`。
- `source_tree`：`d29cc1cdea2800d9cca05cc3b33041abf319e695`。
- `offline_sources_verified: true`；`local_preflight_started: true`。
- `status: LOCAL_PREFLIGHT_BLOCKED`；`stage: host_boot`；`observations: {}`。
- `consumption_path_state: NOT_OBSERVED`；`window_consumed_by_this_invocation: false`。
- `host_persistence_attempted: false`；`remote_attempted: false`；`wrapper_executed: false`。
- `allow_consume: false`；`allow_run: false`；`joint_admission_proven: false`。

截图说明这次载荷已进入本地预检，已经超出只等待输入的阶段。但
`field_reads_performed: true` 在代码里于 boot 尝试前设置，不证明任何内容读取成功。
boot 值尚未取得，不能称 boot 不符；消费路径尚未观察，不能称该路径不存在，
只能说本次调用没有消费它。截图里其它缺项不自动补齐。

## 原因范围与操作纠正

接收器为原准备余量设置 SIGALRM；第一张截图的信号 14 与该超时路径一致。
第二张截图的权限错误来自 `_kernel_text`，它捕获该操作内所有 `PermissionError`，
没有保留具体 syscall/errno。因此 O_NOATIME 与普通身份的所有权限制是与现场
一致的已知机制，但截图不能进一步定位为哪个 open/stat/read 失败。

原 host A 的架构“原点、竞争与同步顺序”明确要求实际读/枚举带 O_NOATIME；
实施方案“拒绝条件”也没有内核视图例外。当前拒绝符合合同，而该合同妨碍普通
身份取得基本内核事实。让 Owner 原样重复粘贴或加 sudo 不是修复方案。
上一复核中的“原 host 待回传”现在由此截图事实更新；完整现场观察仍未取得。

提出[固定内核事实读取需求](q2-kernel-fact-read/REQUIREMENTS.md)、
[架构](q2-kernel-fact-read/ARCHITECTURE.md)、
[实施方案](q2-kernel-fact-read/IMPLEMENTATION_PLAN.md)。只重开内核两处读取合同，
不重批全部 host 窗口。原 A/实现/287 PASS、2 SKIP 的历史测试保留；本轮没有
代码更改、测试运行、新批次消费或原 host 后续命令。

## 官方接口依据

以下资料在 2026-09-27 查阅；用于接口语义，不当作实际 host 版本/能力已验证。

- [Linux man-pages open(2)](https://man7.org/linux/man-pages/man2/open.2.html)：
  O_NOATIME 要求文件所有者匹配或相应 CAP_FOWNER，普通只读权限并不充分；
  O_PATH 支持仅定位元数据及 fd 级文件系统查询。
- [Linux man-pages statfs(2)](https://man7.org/linux/man-pages/man2/fstatfs.2.html)：
  fstatfs 检查 fd 所属文件系统；procfs magic 为 0x9fa0。此事实不自动保证 atime 不变。
- [Linux man-pages proc(5)](https://man7.org/linux/man-pages/man5/proc.5.html)：
  proc 是内核数据结构的虚拟文件系统，不能将任意同前缀普通文件视为 proc 对象。
- [Linux man-pages proc_pid_mountinfo(5)](https://man7.org/linux/man-pages/man5/proc_pid_mountinfo.5.html)：
  视图对应指定进程的挂载 namespace；读取自己的视图不取得其它 namespace 的事实。
- [Linux man-pages statx(2)](https://man7.org/linux/man-pages/man2/statx.2.html)：
  AT_EMPTY_PATH 可对 held fd 查询；STATX_MNT_ID 的实际返回必须检查 stx_mask。
- [Linux man-pages pid_namespaces(7)](https://man7.org/linux/man-pages/man7/pid_namespaces.7.html)：
  proc 挂载对应挂载时的 PID namespace；数字 getpid 与 proc 名称空间对齐必须
  明示为原 host 执行环境假设，不能由文件系统 magic 或挂载 ID 自动推出。

原 R 的 Document evolution 要求架构约束实质变更先形成准确 A、Owner B 和独立 C；
此记录仅形成待审方案，不会自动删去保护标志或授权新实现。
