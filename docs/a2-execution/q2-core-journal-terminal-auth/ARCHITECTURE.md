# Journal 终端认证架构修订

状态 **PROPOSED / Gate OPEN**；范围仅来自[需求](REQUIREMENTS.md)。
采用现有固定 writer payload 和八检查点协议，仅改变该子进程的认证与终端接入。

## 责任和可信边界

Owner 负责本机可信终端和直接认证；普通 coordinator 负责原输入、时钟、镜像和流程；
既有 root writer 仍只读取五个指定镜像的 proc writer 元数据。
不增加服务、常驻 root 代理、安装文件、sudo 策略或新的提权能力。
guest 管理入口保持原非交互契约，本修订不把宿主终端传到 SSH。

CLI 必须显式选择本机终端认证方式，并在 source/manifest 中记录该方式。
只读 writer 的固定 argv 保留原 env 清空、隔离 Python、固定 loader/payload 摘要及请求绑定，
仅不再带 `sudo -n`。不从可写仓库以 root import，不接受额外命令、路径或表达式。
禁止先尝试 `-n` 再交互：选定方式后每个检查点仅一次调用，不制造 fallback。
启动 sudo 本身也沿用原最小环境，不传 SUDO_ASKPASS、DISPLAY、WAYLAND_DISPLAY、WAYLAND_SOCKET
或认证插件选择变量；不能只依赖 sudo 之后的 `env -i`。终端不可用时停止，不走图形认证后备入口。

仅这个调用允许继承控制终端；其它 Command、QEMU、qemu-img、SSH 的 session/管道行为不变。
writer stdin 仍是 DEVNULL，stdout/stderr 仍是原有界独立管道；sudo 通过自身 `/dev/tty`
与本人认证。AI 不持有密码接口；不建立录屏、终端转发、askpass 或密码环境变量。
sudo 自身可能使用已有策略要求的 PTY/PAM；不能把成功创建子进程误认为认证或观察成功。

## 终端绑定与时序

新窗口前仅做普通身份静态检查：fd 0 必须是当前已有终端，进程处于该终端前台，
实际字符设备身份及当前 session 可取得并符合预期。不得新建 PTY 来冒充 Owner 在场。
从实际 fd 0 绑定设备/对象/session，不使用永远相同的 `/dev/tty` 复用节点设备号作为唯一身份。
终端原始路径与身份留在私有输入，公共记录仅保留资格、摘要和失败原因。

首次现场预检开始原双时钟窗口，manifest 加入明确认证方式和稳定终端身份；同窗 execute
必须复核它们。两个前台 CLI 的进程组可以不同，每次分别核对自己确为当前前台；
不能错误要求它们具有同一 foreground PGID。
每次 observer 发起前复核终端和全部原身份；消耗该检查点后创建一个固定 sudo 子进程，
不调用 setsid、不建立新 session，认证提示只发生在这次真实检查内。
终端绑定约束普通启动器；不要求 sudo 或 root helper 与它的 TTY/SID 相同，已有 `use_pty`
策略可能创建内部 PTY。只在调用前和返回后检查启动器的前台资格，不在 sudo 执行期间持续要求
启动器始终占前台；返回后未恢复就停止。writer 扫描不按 sudo/helper 名称豁免任何进程。

15s 起点仍在启动 sudo 之前。所有认证/调度/loader 开销占用该窗口；不暂停时钟等人输入。
root entry 保留 `min(原起点+900s, 检查点起点+15s)` 的双时钟检查，先校验期限和 boot 再扫描。
迟到认证不能启动超期扫描。该逻辑不是强制终止保证：父进程停止采集时子进程可能尚存，必须保留 UNKNOWN。
sudo 超时后也可能仍占用终端，须保留 PID 与终端尚未恢复的事实；780s 修改截止仍由原协调器负责。
不可因程序等口令而自动刷新窗口、重复 sudo、延长观察或给写操作额外时间。

输出保持原 schema 和选择器语义。认证提示可能直接出现在 TTY，程序不截获密码或建立额外密码管道。
终端交互字节量及 sudo/PAM 祖先开销不是完整可计量证明；既有观测限制继续披露。
报告后仍核对 exit/EOF、nonce、D、五对象、boot、两时钟及检查点；终端或当前身份漂移即停止。

## 选择和失败

此处选择有人在场的单次维护，复用宿主既有认证策略。
不采用另一个 shell 先 `sudo -v` 再重跑：缓存作用域和有效期不能保证覆盖两个 CLI 及所有检查点。
不选择配置新免密管理入口；未来若确需无人值守，须据实际需求另作决定，不能顺带加入本修订。

任一检查点认证失败后，不消费剩余检查点来重试。原窗口失败及所有现场计数保留。
若认证等待发生在关机之后，保持实际 VM/备份/镜像状态，不隐藏或自动补救。
用户中断的进程组信号、程序主动发送信号和自然退出分别记录；程序不新增 kill/terminate 清理。
普通身份未获得所需 sudo 权限时仍拒绝，不能扩大权限来满足成功预期。

技术依据：sudo 上游的 [tgetpass.c](https://github.com/sudo-project/sudo/blob/main/src/tgetpass.c)
描述控制终端认证，[exec_pty.c](https://github.com/sudo-project/sudo/blob/main/src/exec_pty.c)
描述内部 PTY 与 job control。这些来源支持方案机制，不替代宿主实际 sudo 版本、策略或验收结果。
