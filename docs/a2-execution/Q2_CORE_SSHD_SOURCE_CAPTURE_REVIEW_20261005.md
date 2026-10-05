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

## 实现提交时的现场检查点（历史）

在此实现检查点，P3 尚未执行，`lhqsshd-20261005a` 新 marker 和 SSH request 均为 0。
真实 sshd 输入仍未取得，核心任务和业务证据没有新增执行/回收。旧三批 UNKNOWN、原件和完整承诺保留。
只有 P2 和同窗口全部本地门通过后才条件执行原一次诊断；失败不重试、不重连、不补采、不清理。
namespace/watchdog 等支线暂停，生产 `E3_SUPERVISION_UNVERIFIED` 保持。

## P2 准确冻结与发行核验

准确实现及实际执行 D 为 `bf8d391c3fdb24a5d4fc188b0ec9f2b36d9e5891`，直接后继独立 C。
上述 reader / runner 字节和摘要就是发行版本；本节及以下结果登记不改变实际执行源码。
[准确 D 的 CI 37297107615](https://github.com/kongbu0621/infra-local-hand/actions/runs/37297107615)
在现场前已 completed / success，三个 job 均 success：classify-change、semantic-core (Windows)、semantic-core (Ubuntu)。
这包含正常 CI 的源码与安装检查，不是现场验收结论，也不是后续文档提交的 CI 声明。

准确 D 默认入口的本地预检返回 `LOCAL_PREFLIGHT_PASSED`、`requests_attempted=0`；
随后执行入口重新进行同窗口核验，而非继承先前窗口或省略准入。已保存 marker 中
reader 摘要与上表一致，固定 argv/environment 的规范编码 SHA-256 为
`1192ec89516a1297bf6c85dd7911cc01db61032bde335db2f631f86845845eca`。
原管理 anchor、writer 保护、密钥关联、固定 SSH 参数和 196 MiB / 56 inode 当前容量条件均在消费前检查；
该检查不成为排他预留或完整历史容量证明。

## P3 实际单次采集已完成且机会已消费

固定 `lhqsshd-20261005a` 创建一次 marker、发送一次 SSH request；没有重试、重连、补采或清理。
本次返回 `COMPLETE / SNAPSHOT_VERIFIED`：SSH exit 0、stdout/stderr 均 EOF、本地原时限满足，
经身份/稳定性、schema、大小与摘要校验的当前快照有 **3 个文件、原配置共 3569 B**。
原文只留在既有受保护本地 capture，不进入本仓库、CI 或聊天。

远端状态准确记录为 `READER_REPORTED_COMPLETE`，`remote_supervision_proven=false`；
完整快照和本地 wait/EOF 不是远端独立监督闭合，也不能证明管理祖先进程的资源或退出情况。
三旧批次历史 UNKNOWN、原证据及完整承诺保持，没有按本次实际小文件退款。

四个原件仍位于原已绑定管理 anchor 的私有 capture 父目录。下表每个后缀均接在固定
`.lhqsshd-20261005a` 之后；不是公开下载地址。

| 私有文件后缀 | 字节数 | 当前已分配字节 | SHA-256 |
| --- | ---: | ---: | --- |
| `.consumed.json` | 495 | 4096 | `88f6c88c96d90effc2f06d15693bc04dd23353ef65825331275d0746e87e50a7` |
| `.stdout` | 7028 | 8192 | `7c22202275cc851bac0707c7a630a4b302d7d347de087b2705af2289ab4a5dcc` |
| `.stderr` | 0 | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `.receipt.json` | 1259 | 4096 | `1cc9fcdbf3179652d00e5c41cc37070e017f107f2ed96919a5ab0fbd64e5179c` |

总逻辑字节 8782 B、当前实际分配 16384 B、四个文件；新增承诺仍为完整 4 MiB / 8 inodes。
这是保存后观察，不声明全程文件系统物理峰值。取证后只在本地用 O_NOATIME / no-follow
复核四原件身份和摘要、receipt 与流关联以及快照结构；没有重新运行双解析器或追加远端操作。

## 当前输入的有界离线诊断

本次完整快照完成一次双解析器对照，各受原 5s 上限约束：

| 固定解析器基线 | 对真实当前输入的结果 |
| --- | --- |
| `71d6f43d98a8b71763e7925c43b2becaec184e11` | `REJECTED / CORE_ADMIT_SSHD_GRAMMAR` |
| `46b08d9640ca19505fa02aa89d5d71d298536489` | `REJECTED`，首个拒绝条件 `GLOB`，文件序号 1、行号 121 |

带诊断解析器的完整脱敏错误码如下；这是序号、计数与摘要，不含配置原文或私有路径：

```text
CORE_ADMIT_SSHD_GRAMMAR_GLOB_F1_L121_FILES3_BYTES3517_LINES131_INCLUDES1_PATHSHA256_83CA950C7ADAF0F96800E5A6B2157F72B14A68A476292FCCA2C8FD3D7284BE96_SHA256_64325541513D33EA1D2CCD19C77750D458E67E7967FD2E7EF81D92F0AA2FFE21
```

由此已取得真实当前输入，定位当前首个文法拒绝，不再只依赖合成 glob 用例。
但没有 05b 当时的配置原件，不能把这个当前行号提升为已证明的 05b 历史触发行；
也不能据此声称已检查完其余文法或有效 sshd 策略。

## 核心主线仍未完成的事项

P1–P3 的取证交付已完成。**本次没有执行业务任务，H01/Q4/H11 没有运行，业务结果和业务证据没有新增回收。**
直接后续工作是据这份已保留输入判断并处理 `GLOB` 拒绝：既有 CLOSED 范围缺陷按原规则精确修复；
若需要改变固定准入文法或信任合同，先准备相应最小 A，不在此取证批准下直接放宽检查。
本次不包含任何文法修复或下一批实现。后续真实核心验收仍需自己的准确批准，不能重放三旧核心批次或本次已消费的诊断。
业务顺序仍是正常链、取消、同 ledger / unit 恢复；生产 E3 限制和支线暂停保持。
