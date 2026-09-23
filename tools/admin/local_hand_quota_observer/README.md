# Q1 原生 quota 查询原语

批准范围：`LH-E3-QUOTA-HARNESS-v1`，A `415327ebdcc251bb055da9931a7a88990f750b7a`，
独立 CLOSED 记录 C `5a4ea852091db06549a876e42bbd5f95d5869d3b`。

`quota_fd_query.c` 是管理侧 observer 的内部 ABI 原语；当前还没有 observer 服务、
持久请求账本、peer 鉴权、manifest 准入或进程监督装配。它不接入 broker，也不打进 wheel/Plugin。
**本目录当前只能作为 Q1 开发检查点，不能安装或提权后独立运行。**

## 精确行为

- 零参数；只接受管理侧父进程继承的固定 directory FD 3，不打开任何客户端路径或 block device。
  这不是公开 FD 接口：未来 observer 必须拒绝客户端传入 FD，只从自己的受保护 manifest 映射打开根。
- 检查真实 directory/只读 FD、ext-family/XFS magic、非零 project ID 和继承标志。
  ext 系列共享 magic；这里只作预筛，不据此证明准确 ext4 类型或完整 filesystem 准入。
- 用本机已审阅 Linux headers 的 `SYS_quotactl_fd`，不猜 syscall 编号；缺少 ABI 则 UNSUPPORTED。
- 固定三次 quota syscall：`Q_XGETQSTATV/PRJQUOTA` → `Q_GETQUOTA/PRJQUOTA` →
  `Q_XGETQSTATV/PRJQUOTA`。前后状态须具有 project accounting/enforcement 标志；
  generic Q_GETQUOTA 的 hard limit 是 1024-byte 单位，并检查有效位、零值和换算溢出。
- 中途失败立即停止后续查询，不重试、不更换 API、不设置 quota；逐项保存原 rc 和即时 errno。
- 再次观察 FD 的 dev/inode/uid/gid/mode 和 project/继承，保存前后事实；漂移/复查失败为 IO_UNCERTAIN。
- 固定有界 JSON，小于 4096 bytes；不输出路径，不把错误文本拼成协议。
  `hard_bytes` 未能验证/换算时为 null。保留成功 syscall 的 errno 快照，判定以 rc 为准。
- close 只调用一次；失败保留原 substantive error，不能用清理错误覆盖原权限错误。
  输出不完整、非正常退出或无原记录时，未来监督器必须记 UNKNOWN。

退出码：0 = OBSERVED（仅取得该次事实），2 = REJECTED，3 = UNSUPPORTED，4 = IO_UNCERTAIN；
70/74 或信号退出表示报告内部/传输失败。所有 JSON 固定保持 admission_proven、real_e3_accepted、
production_supported 为 false。没有 PASS 或支持启用开关。

当前不核验已准入额度、mount/boot/namespace/generation、原执行或预算，也不证明查询原子性、
身份不会在未来变化或真实超限写入已被拒绝。前后观察不是连续保证；这些须由后续受信绑定与实测补齐。
Q_GETQUOTA 仍可能等待存储或涉及 quota 元数据，父进程须有独立监督和停止/未知保留机制后才能实机调用。
禁止添加 setuid 或文件 capability；普通作业始终不携带 host 管理能力。

## 开发验证

独立输出目录内编译，不安装到主机路径：

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -Wconversion -Wformat=2 \
  -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
  tools/admin/local_hand_quota_observer/quota_fd_query.c \
  -o /absolute/new-build-directory/quota_fd_query
python3 -m unittest discover -s tests -p test_e3_quota_abi.py -v
```

测试真实 binary 的“无 FD”和“拒绝参数”负例，不进行 quota syscall。
成功/权限/限额/漂移分支通过单独链接 `tests/fixtures/quota_query_syscalls.c` 验证；
该 test-only shim 拦截全部 quota syscall，结果为 **LOGIC_ONLY**，不是宿主 quota 验证。
生产原语没有该 shim 的环境开关。准确编译器、headers 和二进制摘要须随每次产物记录；
云端 x86_64 编译不能替代 GX10 aarch64 的 ABI 和运行验证。

## 来源与下一步

固定 Linux `adc218676eef25575469234709c2d87185ca223a` 的
[fs/quota/quota.c](https://github.com/torvalds/linux/blob/adc218676eef25575469234709c2d87185ca223a/fs/quota/quota.c)
中 `quota_getxstatev` 使用 filesystem `get_state` 返回 accounting/enforcement，
`quotactl_fd` 仍走原权限检查，不能仅凭 FD 解决权限。目标 filesystem 不支持这些观察即停止。

Q1 仍缺最小权限过滤/受监督装配、管理侧固定对象准入和真实 fixture 结果；Q2 的认证通信、
持久防重、绑定/预算、Q3/Q4 三单元和故障 harness 也未完成。生产 support 封堵保持。
后续先补可审阅装配与监督，再交接准确隔离对象；当前不向 GX10 发起新的盘点或安装命令。
