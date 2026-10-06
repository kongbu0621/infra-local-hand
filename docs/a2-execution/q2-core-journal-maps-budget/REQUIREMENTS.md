# Journal 全量 writer 扫描的累计读取预算修正

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope：
`LH-Q2-CORE-JOURNAL-MAPS-BUDGET-v1`，仅 MB1–MB2。Authority：Owner。
原 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、Owner mandate、无例外和
准确 A→Owner B→独立 C→D 顺序不变。本文件与[架构](ARCHITECTURE.md)、
[计划](IMPLEMENTATION_PLAN.md)构成待决三文档；没有批准或实现本变化。

## 问题与目标

服务于原 journal 256→512 MiB 扩容，解除 Local Hand 核心执行之前的容量阻塞。
[v2 现场记录](../Q2_CORE_JOURNAL_DIAGNOSTIC_RESUME_V2_FIELD_20261006.md)表明：准确 D
`4236ac62e61c0cdf62b49f3620c325454e8fba99` 在 checkpoint 1 返回
`GROWTH_PROC_LIMIT_MAPS_TOTAL_BYTES`，首次累计值 67,115,642 B 超过 67,108,864 B。
这是逐 task 读取的 maps 文本预算，不是 RSS、journal 容量或唯一映射大小。
6,778 B 只是首次越界量；完整扫描所需字节、耗时及其它准入结果仍未知。
该记录依据截图和源码解释，原始流未独立认证；不能补写此前失败的原因。

目标是以固定、受限的读取余量替换已触发的 64 MiB 总额，同时保留完整扫描及全部身份、
writer、锁和内容判定。禁止把减少覆盖、忽略未知、取消资源界或更名视作修复。

## 精确变化

1. 每次 `collect_image_writers` 调用中，完整 maps 文本的累计接受上限由 **64 MiB 改为
   512 MiB（536,870,912 B）**。仍逐 task 实际读取、累计，不去重、不缓存、不跳过任务。
   仍在同一位置比较 `observed > cap`，超过即停止；不动态调大，不暴露可调参数。
2. 这是明确增加八倍的累计读取预算，不声称所有安全/资源上限原封不动。512 MiB 是本方案
   提请 Owner 接受的有限工程预算选择，不是从 6,778 B 推算的需求，也不保证现场通过。
3. 在本范围准确批准、实现、发布、相关验证和最终 D 的 CI 完成后，允许沿用
   `lhqjgrow-20261006a`、原对象和原输入，**再一次**替代预检窗口。全门通过才在同窗
   完成尚未消费的原 journal 维护；它不是另一轮只收日志的试跑。

其余规则继承原扩容 A `59948ec4fedb807a31cdbff77acc134e84414160`、宿主读取 A
`2b4448c7b89d1910840f7aee2ae2b781f970e179`、终端认证 A
`2b236865dc0a89e475c4021cac44d7193f252f67`、替代 v1 A
`ef46ac169fd9084875cb5c5148a9c4985ace680c` 与替代 v2 A
`4341487c9be9ef64cf6fccbd973ed438a66e7483` 的未受影响要求。
本方案仅在将来批准后替代其中“累计 maps 保持 64 MiB”和“没有下一窗口”的对应限制；
旧文档、批准、现场结果与已消耗窗口均保留，不追溯改写。

## 保留边界与验收

- 每个 maps 文件仍 ≤1 MiB；PID/TID/FD/其它读取数量及长度、初读/复核、完整可见性、
  drift 拒绝和匹配五镜像 writer 的判断全部保持。不存在以部分扫描取得 PASS 的路径。
- 每 writer 15s（含原终端认证）、900s 总窗、780s 修改截止、最多八个串行且各一次的
  检查点、AS 256 MiB、FD 128、120 CPU-s/512 MiB 部分观测及原输入/stdout/stderr/
  capture/存储预算保持；只有前述累计 maps 读取额改变。
- 仍只有固定只读 writer 使用现有 sudo；密码只在 Owner 原有真实前台终端输入。
  不改 sudoers、权限、helper、服务、安装、SSH 或原静态输入，不加探测、补采或重试。
- 旧窗口永久已消耗。新窗口一旦开始即消耗；失败、未知、漂移、超时立即停止后续步骤，
  不自动重连、强杀、清理、恢复、回滚或另开窗口，原副作用及中间状态风险保留。
- 累计维护仍最多一个 marker、两条固定 SSH、正常关机/完整备份/镜像增长/VM 启动/
  ext4 增长各一次。没有原合格 receipt 不记成功。

MB1 成功须证明新边界、旧 64 MiB 以上的继续全量检查、真实源/生成 payload 一致和全部
未受影响拒绝条件；准确候选与 CI 完成才能交接 MB2。MB2 只有内容/身份保留、两层增长、
完整备份及普通可用至少 400 MiB/32768 inode 全部满足才记 `JOURNAL_GROWTH_VERIFIED`。
完整扫描是否在新限额和原期限内完成，由这唯一窗口验证；未知不作为已通过。

本范围不执行 H01/Q4/H11，也不授权新 boot 核心采用、namespace/watchdog、生产部署或支线。
维护合格 receipt 是下一步核心验收接续的输入；`E3_SUPERVISION_UNVERIFIED` 保持。
