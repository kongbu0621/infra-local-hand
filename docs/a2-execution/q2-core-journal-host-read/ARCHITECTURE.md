# Journal 维护宿主读取修订架构

状态 **PROPOSED / Gate OPEN**。范围和预算仅来自[需求](REQUIREMENTS.md)。
代码检查基线 `9c63f25b43ef713f51930f8927e55456c9a0a9fb`；原维护 A 和已记录失败保持。
本提案没有实施 root observer、采用新 boot 或建立替代窗口。

## 固定内核读取

host 窗口绑定不再调用 guest 的 `boot_id/read_kernel`，改为准确 pin 的既有
`tests/e3_host/q2_host_kernel_facts.py` 的 `read_fact("boot", guard, report)`。
host 自身 mountinfo 如需读取，只能使用同一模块的固定 mountinfo 分支。
ABI、不被子挂载替代、root/当前 UID 的逐段保护、held fd 与名称复核保持。
报告记录实际读取模式、资格、动态元数据语义及失败 operation/target/errno，不记录私密路径原文。
这不是移除 guest 的 O_NOATIME，也不是任意 PermissionError fallback。
source manifest 增加该现有模块的准确 commit、长度和 digest，禁止加载不匹配的工作区替代品。

新窗口保存本次真实 host boot 与 MONOTONIC/BOOTTIME 原起点；后续进入执行必须完全匹配。
不拿旧失败的部分 binding 补造 boot；不把更改 manifest 摘要变成重新开始窗口的手段。

## 只读 writer 观察

保留原五个已持有 fd 的镜像身份、原 QEMU pidfd/starttime/executable/完整 argv 验证。
普通 coordinator 在每个既有 writer 检查点通过固定绝对路径 sudo，使用 `-n --`，
经固定 `/usr/bin/env -i` 和 root-owned `/usr/bin/python3 -I -B -c` 启动只读 observer。
固定环境只有必要 PATH、LANG/LC_ALL；禁用交互口令、shell、用户 Python 路径和文件导入。
不执行 sudo -v、sudo -l 或单独权限探测；第一项真实只读观察同时验证现有管理入口能否使用。
工具缺失、保护不满足或 NOPASSWD 不可用就是 BLOCKED，不申请密码或改配置。

observer 由现有两个维护实现文件内的固定生成逻辑产生，不建立第三实现模块。
完整 loader/payload/argv 算法和源码 SHA 在 J2 冻结；root 入口加载前验证长度、摘要、schema、
固定 scope/session、准确 D、nonce、五角色 dev/inode、原绝对双钟期限及当前检查点序号。
不得在 root 下从可写仓库 import，也不得接受任意命令、Python 表达式、文件路径或扩展读取字段。
源码摘要由受信任的本地执行者绑定准确提交，不将同一账号提供摘要误称为独立硬件签名。

允许的读取是原 writer 算法所需的真实 procfs：进程及线程 stat、FD 的元数据、匹配对象 fdinfo、maps、
必要的 proc 挂载资格。保留原 PID/TID/FD/总字节上限和扫描前后身份/集合比较，仍使用 O_NOATIME。
只返回匹配五对象的 writer PID/starttime/角色、完整性状态、固定错误字段与计量摘要。
不能返回全系统 maps 原文、cmdline、environ、FD 内容或其它机器秘密。
root 没有匹配 proc 视图、任一进程不可读、发生 drift 或存在额外 writer，均拒绝；无 sudo fallback。
观察成功仍不是排他锁，也不能证明后续 root 不会修改文件。保留原管理信任和 qemu-img 正常锁。

observer 本身不打开镜像内容，不调用 qemu-img、不发信号、不联网、不创建文件、不修改进程/服务。
这是经审阅代码的行为限制，不声称 sudo 或 Python 自身已变成强制的只读安全容器。
权限变化仅存在于该子进程，所有维护写操作仍由原普通身份执行。

## 检查点和证据

每个检查点只能消费一次 observer 调用，失败不能用剩余次数重试同一检查点。
总计最多八次，顺序见需求；不允许在循环中不断调用以等待一个稳定快照。
双钟子界是 `min(检查点起点+15s, 原窗口终点)`，不会改变原 780s 修改截止。
超时只停止后续操作并保留 PID/退出 UNKNOWN，不自动清理或继续维护。

marker 前两项只读报告在同一个执行者的私有内存/返回中复核；不以新持久文件替代 marker 消费语义。
创建唯一 marker 时绑定 root observer 的准确代码/工具/策略及已完成计数，现有 events 保存后续状态。
不把不同次扫描的 PID 或用量塞入必须跨两次 CLI 调用相同的静态 manifest digest。
各检查点的实际报告单独绑定 nonce、原起点及序号，不以缓存的前次 PASS 代替当前观察。
输出纳入原 capture 总池；任何异常原文都不得泄露到公共记录。

既有 sudo/PAM/audit 可能产生管理副作用；observer 回报与 root helper 最终退出之间仍可能存在
未覆盖用量。取得真实 wait/EOF 就记录，没有就 UNKNOWN；不把关闭管道当成退出。
不修改原第一阶段回报/继续令牌、正常关机、完整备份和第二阶段增长协议。

## 替代窗口和准确候选

原失败窗口永久保留为未进入执行的 BLOCKED，不再使用，不退款或改变旧历史。
只有准确 B 和独立 C、R1/R2 全部必要验证及新 D 的 CI 完成后，才能开始一次替代窗口。
固定 session 和所有输出名不变；预检首先发现任一旧目标文件即拒绝，不能删除或换名。
新预检失败、过期、host 重启、binding 缺项或执行摘要不匹配均终止，不隐式开下一窗口。
既有未消费维护次数仍只能在全门通过后使用，所有 SSH 和修改上限均不增加。
