# sshd 单次只读取证实现与验证

2026-10-05，Asia/Shanghai。Scope `LH-Q2-CORE-SSHD-SOURCE-CAPTURE-v1`；准确 A
`f2eb31deb3c52d69ccd2079fb7d88608d1a25a62`，独立 bookkeeping-only C
`b346cbd44dd4f376d4386f72d7029b1311788229`。本实现是 C 的后继，不改变 A 三文档。
[逐字 Owner B](../governance/Q2_CORE_SSHD_SOURCE_CAPTURE_OWNER_DECISION.md)授权 P1–P3 和一次固定诊断采集。

## P1 已实现

新增固定 guest reader、独立 host runner 及窄回归。reader 仅把固定配置当 bytes 读取，使用 held fd、no-follow/no-atime、
原路径/元数据和目录清单前后复核；不执行 Include、不运行 sshd helper、不写 guest 文件或启动子进程。
host 默认仅本地预检，`--execute` 才走一次性 marker/request；旧核心入口、发行 allowlist、bootstrap 和业务 wheel 未改。

实现固定管理 pins、私钥/公钥关联、已知 endpoint、严格 SSH 参数、原双时钟窗口、四件 create-only capture、实际分配量观察和私有结果验证。
本地系统 executable 使用 protected root-owned 路径及 O_PATH held descriptor 绑定并经 fd 执行；这是元数据身份资格，
不是新增二进制历史摘要或业务运行时 attestation。预检对自身管理数据用 O_NOATIME；SSH 内部普通读取的副作用仍按 A 保留。
一旦创建 marker，任何后续失败保留原件；没有恢复、删除、换名或重连入口。所有消费/传送/退出/EOF/不完整封存状态分别记录。

快照返回后只有一次本地双解析对照，各最多 5s；从固定 `71d6f43` 和 `46b08d9` 提取原文法函数，
在独立本地进程编译这些已提交函数，输入仅为已验证 bytes。哈希和规范 JSON 用相同纯计算语义提供，
不导入/执行配置，不运行整个现场 dispatcher。输出只含版本、固定错误码和摘要/序号，不打印配置或私有路径。
当前快照不能恢复 05b 历史触发行；解析接受也不是有效 sshd 策略或 H01/Q4/H11 通过。

## P2 离线验证

- 新范围在工具沙箱及两组原准入回归：225 passed / 3 skipped / 1.72s。
  两个旧跳过项要求 root；新增跳过项是沙箱将 host root 映射为 65534，不能据此判宿主失败。
- 在真实宿主视图只跑本新增离线测试：84 passed / 0 skipped / 0.85s。
  真实宿主 `/usr/bin/ssh`、`ssh-keygen` 为 root-owned 755。此检查和全部本地临时 fixture 不发 SSH 连接。
- 覆盖 65 文件/1 MiB、目录项上限、私有路径保护、缺失目录、特殊文件、别名/漂移、输入非 ASCII、
  JSON/base64/摘要错误、一次性竞争、部分 marker、创建/同步失败、短写、双流超限、无 EOF、截止和不能确认退出。
- 本地真实子进程验证降限与流处理；合成 root metadata 只用于 host validator 的单元测试，不是 guest 证据。
- 保留首次验证失败：测试默认 umask 导致夹具过宽（修正夹具，未放宽 reader）；目录最后复核未重新枚举，已修复并有回归；
  沙箱 root 映射导致 native executable 检查不能通过，转在宿主只读验证，不添加 UID fallback。
- `git diff --check` 通过；没有本地全量 source/installed 重跑，没有重新遍历旧私料。

| 文件 | 字节数 | SHA-256 |
| --- | --- | --- |
| `tests/e3_host/q2_sshd_source_reader.py` | 8656 | `68c594cedbea15768789690b4afd0797bfff1057760a522f931e16a4a7ca3108` |
| `tests/e3_host/q2_sshd_source_capture.py` | 33426 | `cbf8e3de028f987ca5e034a12dc7d870dcb163c48e1e8713cfc72108b9e5ee91` |

reader 加固定 launcher 仍小于 32768 B，runner 小于 65536 B。准确实现提交由包含本记录的 Git commit 定位；
现场前还必须通过该准确版本的相关 CI，以及真实管理 anchor 的本地预检、参数冻结和同窗口准入。

## 当前现场状态

在此实现检查点，P3 尚未执行，`lhqsshd-20261005a` 新 marker 和 SSH request 均为 0。
真实 sshd 输入仍未取得，核心任务和业务证据没有新增执行/回收。旧三批 UNKNOWN、原件和完整承诺保留。
只有 P2 和同窗口全部本地门通过后才条件执行原一次诊断；失败不重试、不重连、不补采、不清理。
namespace/watchdog 等支线暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。
