# Q2 启动失败：AppArmor 原因核实

2026-10-01。本记录修正先前故障排序，不声明实现修复或现场通过。
私有现场身份、原始日志及账本不进入本仓库。

## 证据与因果边界

最新只读证据包的六项查询均正常退出、捕获完整，成员摘要核验一致。
实际系统为 Ubuntu 的 systemd 255.4，内核启用了 AppArmor 和非特权
user namespace 限制。以下历史日志绑定到同一 boot、原 bootstrap 的
执行子进程 PID 和原失败时段：

1. 创建 user namespace 时，AppArmor 将该进程从 `unconfined` 转入
   `unprivileged_userns`。
2. 该 profile 随后拒绝 `sys_admin` 和 `setpcap` capability。
3. 原 unit 日志记录 `Failed to drop capabilities: Operation not permitted`，
   以 `218/CAPABILITIES` 退出；Python 业务入口未执行。

`setpcap` 拒绝与降 capability 的失败直接对应；现有日志不单独证明究竟
哪一个底层 capability syscall 返回错误。日志接收时间也不能替代内核事件时间。
同一 invocation 的 network namespace 警告表明隔离准备另有失败，不能把它
当作网络隔离已经生效。

原 bootstrap 退出早于 listener 超时约 1.076 秒。因此首个已证实失败是
普通 user manager 的隔离/降权准备；listener 超时和后续 bridge EOF 是
后续现象。先前时间预算调整没有解决这个原因，也尚未取得实际链路验证。
当前读取的 manager 配置与内核开关是当前观察，不冒充历史配置快照。

下一批使用新空账本时，还因同一 user manager 保留原失败 bootstrap，
在 `cli._compose_broker` 的 inventory 检查中先返回 `IO_UNCERTAIN`。
这次拒绝发生在新 bootstrap 交付之前，不能记为再次验证降权修复。
旧账本的 UNKNOWN、七条 lease 和原始捕获都继续保留。

## 已排除的局部改法

- 不删除 `PrivateUsers`、网络/文件系统隔离、空 capability bounding set，
  不把业务进程改成 root，不放宽 peer 或 PID/UID/GID 检查。
- 不关闭全局 AppArmor/user namespace 限制，不给通用解释器或全局
  systemd executor 添加宽泛放行 profile。
- 只加 unit 的 `AppArmorProfile=` 无法修复本次顺序问题：上游 v255 在
  创建 user namespace、降低 bounding set 之后才安排 `aa_change_onexec()`。
  给最终 Python 入口加 profile 同样晚于失败点。
- 不删除旧 unit、不执行 reset-failed、不清空账本、不把旧单元名塞进
  known 列表来让新账本通过。当前 failed/无 PID 不等于完整旧执行关闭证明。

核对来源：[systemd v255 执行器](https://github.com/systemd/systemd/blob/v255/src/core/exec-invoke.c)、
[AppArmor 同类问题记录](https://gitlab.com/apparmor/apparmor/-/issues/585)、
[Ubuntu 对 user namespace 限制的说明](https://discourse.ubuntu.com/t/understanding-apparmor-user-namespace-restriction/58007)。
上游源码用于解释执行顺序；现场日志用于确认这次实际拒绝。

## 下一项具体变更

建议由 PID 1 的系统级 systemd 创建隔离环境，随后以原普通身份、零
capabilities 执行业务阶段；普通 broker 不获得系统管理权限。
新增固定任务管理入口放在已有受监督 controller 内，独立于只读 quota observer。
原 SSH、Python 安装、旧 user manager 和全部现场保留。

这改变了已批准的 user-manager 启动边界，故形成单独的
[需求](q2-system-manager-repair/REQUIREMENTS.md)、
[架构](q2-system-manager-repair/ARCHITECTURE.md)和
[实施方案](q2-system-manager-repair/IMPLEMENTATION_PLAN.md)。
方案目前 OPEN，未新增执行代码、未安装配置、未发行新正常链 ZIP。
此结论不需要再次补采相同日志，也与平台内容检查无关。
