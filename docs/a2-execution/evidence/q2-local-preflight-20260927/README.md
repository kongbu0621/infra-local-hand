# 已批准 LOCAL_PREFLIGHT 的实现与交付证据

准确 D `0a456a909821fd1fc6a4fdec43b9e16bc88679f2`；原 A/C 沿用，未新增批准或
消费批次。此处为公开脱敏证据，实际路径、机器身份、原件和交付载荷保留在私有归档。

| 材料 | 证明范围 |
| --- | --- |
| [validation.json](validation.json) | 四份新增源码/测试与准确 D 字节一致；受影响整组 287 PASS / 2 SKIP；30 项新增定向验证 |
| [component-tests.txt](component-tests.txt) | 本轮最后一次实际 pytest 输出，不把 SKIP 算 PASS |
| [exact-package-check.json](exact-package-check.json) | 准确 D/tree/三条 C/48 工具 Git blob、47 分类来源、48 raw blobs、固定对象定位；两次组装相同；10 个拒绝负例 |
| [workspace-wrong-boot-pty-check.json](workspace-wrong-boot-pty-check.json) | 当前工作容器真实 PTY 完整输入，在 boot 不符时拒绝；没有访问原 host/guest，不能作现场 PASS |
| [upstream-source-manifest.json](upstream-source-manifest.json) | 16 份官方原文的固定版本、完整 commit、URL、长度及 SHA-256；只用于机制比较 |

私有包为 5,573,496 bytes，SHA-256
`733d34737fe2ae26f1e60e8f5dbc0690bda13831e667c35409c3a50243392a01`。
准确启动命令 9,190 bytes，输入帧 7,445,953 bytes，总计 7,455,143 bytes，低于
原 16 MiB。完整包 PTY 验证取得 4,324 bytes 输出、恢复原终端属性、无载荷回显，
在本工作容器的 `HOST_LOCAL_BOOT_CHANGED` 处停止。

接收、校验与现场读取沿用接收器最早双钟，准备不超过 140 秒；有限结果发送仍在
同一 300 秒总界内。输出预留框架余量。未验证包不会先执行；包内自报索引不能
代替 Git blob/祖先检查。错误源、削减 C、额外 ZIP、缺接收原点、磁盘 local 模式
及 `--run` 都拒绝。包不含 runtime TAR，不把 runtime tree 元数据校验说成其
完整源文件字节再次校验；原冻结 runtime/wheel 与旧离线包继续保留。

真实原 host 的 O_NOATIME 权限可能不满足，届时直接 BLOCKED；不提权、不恢复
时间戳、不以较弱读取重试。只读结果始终不是 HOST_RECORD_ADMITTED、远端硬截止、
完整账单、持久性、独立 stop/EOF 或 Q2 验收证据。
