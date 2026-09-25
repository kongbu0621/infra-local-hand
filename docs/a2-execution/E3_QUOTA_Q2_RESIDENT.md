# Q2 第六批：首阶段常驻 broker 与一次装配入口

2026-09-25。继续 `LH-E3-QUOTA-HARNESS-v1` 已 CLOSED 的隔离开发范围，
不改变批准的 R/A/C 或三层文档。原 Q1 失败、预留和限定成功结论保留。

## 本批可运行边界

新增显式入口：

```text
python -I -B tests/e3_host/q2_launcher.py --fixture ABSOLUTE_PATH --sha256 SHA256
```

它在**已经独立监督的 root controller** 内，将固定测试请求的首个 preflight 阶段串起：
现有空 broker 账本 → 原预算/slot 准备 → 管理侧 grant/config/journal → listener/admission →
原 bootstrap/helper/result_reader → 管理账本关闭 → broker 关闭 ACK → resident 实际退出和双流 EOF。
默认没有 fixture 时退出 3、`BLOCKED / EXPLICIT_PRIVATE_FIXTURE_REQUIRED`。
成功最多报告 `PREFLIGHT_CLOSED`；所有结果仍 `q3_accepted=false`、`production_supported=false`。

这不是完整业务作业或 Q3 验收。外部监督者仍负责准确 root controller 的原身份停止与空 cgroup 证明。
resident 客户端退出不能替代这一证明；失败也不通过杀客户端制造完整 EOF。

## 共享核心与权限

`runner._SystemdExecutionCore` 保留真实 OS/账户/cgroup 检查；生产 `SystemdManager` 包装器始终
返回 `E3_SUPERVISION_UNVERIFIED`。`cli._compose_broker` 复用原 authority、已有 SQLite、inventory、
Runner、EvidenceStore 和启动围栏。生产 CLI/MCP 不选择 test-only composition，不新增 support 开关。
共享核心不导入 tests/admin；管理模块和宿主 harness 不打入默认 wheel/Plugin。

`q2_resident.py` 只接受受保护的固定 `host.inspect` 请求、`q2-synthetic-*` principal、精确 resolved plan、
已有空账本和单个 `preflight`。先固定安装 wheel 的 source/payload/module/program 摘要，再使用同一个
broker 进程、session 和持久启动围栏。bootstrap 的 argv 由同一纯函数从原 plan/allocation/budget 生成。
argv 内 runtime cap 固定于原 reservation；实际交付的 RuntimeMaxSec 仍按当前原 deadline 缩短。
延迟、过期或错绑定不能增加预算。

root 启动者使用固定摘要的 `/usr/bin/setpriv` 降为专用账户，清空全部 capability 集并设 NoNewPrivs。
要求原 controller 已有 SETUID/SETGID/SETPCAP，缺少即 BLOCKED，不临时加权限。
双方只继承一个已启用 SO_PASSCRED 的 SEQPACKET；每包核对准确 PID/UID/GID，保留 pidfd 和 start_ticks。
resident 在 root controller 的原 cgroup 中受同一总预算限制；普通工作单元仍进入既有专用 user slice。
实际 delegation 在 `user@UID.service` 核对，不能要求 slice 本身 `Delegate=yes`。

## 原预算装配

`q2_assembly` 模板只定义固定对象、完整原操作预算、generation、程序/源文件和有限管理开销。
活 resident 提供的 preparation 必须逐项匹配；原 budget/allocation 原样复制，管理发行时间取可信 BOOTTIME，
所有管理阶段必须装得进原阶段 deadline。没有新账号、目录、挂载、quota、slice 或服务安装。

管理员在已存在且固定身份的空目录内先以 O_EXCL 创建 reservation 并 fsync，然后创建有限 session、
管理 record、config 和请求 journal。失败保留所有部分文件和永久预留；不覆盖、不退款、不继续旧尝试。
bootstrap 命令摘要由 root 使用受保护 plan 和共享纯函数计算，不能信任非 root 回传的 argv。
装配文件及外层 launcher/resident/控制客户端的并发 CPU、内存、进程、输出、存储均计入既有声明。

## 一次性 fixture 字段

顶层版本 `local-hand-q2-launcher/v1`，purpose `ISOLATED_Q2_PREFLIGHT`：

| 字段 | 管理侧必须交付的固定内容 |
| --- | --- |
| `source` | 准确 clean source commit；全部运行模块及两个 harness 入口的 SHA-256 |
| `resident` | root 保护的安装 wheel/module/program pins；原私有 policy 的路径和语义 digest；专用 UID/GID、初始 userns、普通 parent、broker cgroup；固定 principal/request/完整 plan；phases 只含 preflight |
| `assembly` | `local-hand-q2-assembly/v1` 模板；准确 allocation/roots、原 operation budgets/generation、有限 capacity、独立 query/management parent、固定 endpoint、peer interpreter/runner |
| `controller_envelope` | 当前独立 controller 原 unit/invocation/cgroup、有限原 deadline、资源和存储预算 |
| `setpriv` | 固定 `/usr/bin/setpriv` 路径与摘要 |
| `output` | 已存在、root 0700、空的私有结果目录及 dev/inode |
| `declarations` | 已存在、root 0755、空的 resident 声明目录及 dev/inode；只新建 root 0644 固定声明 |
| `session` | 固定 64 位十六进制传输 nonce；不冒充 broker 自己产生的原 session |

目录必须彼此及与安装、账本、工作 roots 分离。`assembly.output/journal/evidence` 仍须为空且 root 0700。
外层 storage 至少 1 MiB，另按实际 grant 开销合算；不是把目录存在当作容量准入。
这些均是私有宿主真实字段，不提供可误当为真实主机对象的默认 fixture。
原始 plan、配置、stdout/stderr、journal 和 host 身份只保存在隔离 fixture 中。

## 同批修正

- listener 先以 000 保留 socket 路径，完成 listen 后才发布最终权限，消除 ready 早于 listen 的竞争。
- resident 在明确 start 之前不 tick，避免 bind 唤醒调度后再次 start 导致 CONFLICT。
- 单阶段 snapshot 自适应轮询最多 48 次，保留原通道的 bind/start/close/finish 消息额度。
- 管理监督为停止后核验预留有限调用；原服务已停止后只继续采集原 EOF，不耗尽 systemctl 预算。
- 最后关闭 ACK 后 resident 等待固定 finish，避免 peer 过早退出使已入队 ACK 被 pidfd 活性检查拒绝。
- 普通临时单元停止后被 systemd 回收时，只能依靠已保留的准确终态、一次原 StopUnit ACK、
  同一空 parent、实际原客户端退出和双流 EOF 证明关闭；未曾观察到原终态的缺失仍拒绝。
- launcher/resident 直接执行已校验并保留的源码字节，拒绝预导入及未声明模块；
  `-B` 本身不禁止读取旧 `.pyc`，不能单独作为源码绑定。
- 创建失败、原输出不完整、摘要不匹配或关闭/持久化错误均保留 INCOMPLETE。

## 仍需完成

1. 当前是首个 preflight 的完整单次装配。business/evidence 的未来 grant 依赖各自尚未发生的原 reservation；
   管理 journal 当前固定完整 grant table，不能为每个后续阶段另建单 grant journal 来绕过前驱 CLOSED。
   下一步需实现可核验的同一操作跨阶段装配与持久前驱关联，同时维持总容量永久占用和不重放。
2. 外部 controller 的完整启动、独立停止及证据封存尚未合并为完整 Q3 launcher；本入口要求它已存在。
3. 当前执行器没有实际 systemd/专用账户/委派/真实 quota fixture。H01–H05 尚未执行，随后才是 H06–H13。

因此剩余阻塞同时包含源码整链装配与实机输入，不能写成“代码全部完成，只差换主机”。
本批准确验证和发布映射由后续独立验证记录给出。
