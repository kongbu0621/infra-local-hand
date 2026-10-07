# Journal 一致性拒绝的分支诊断修复

源码基线 `a64a76dadf75d995d049f08c96c94db855ec56ff`。本次为已有 CLOSED 开发范围内的
离线诊断修复，不修改批准文档、扫描策略或现场次数。最新 W2 仍为 CONSUMED / FAILED；
其 `PID_RECHECK` / `GROWTH_PROC_DRIFT` 只能证明该阶段拒绝，不能由新测试反推历史分支。
原现场事实保留于 [W2 返回](Q2_CORE_JOURNAL_SCAN_WORK_FIELD_20261007.md)。

## 修改与边界

只修改 `q2_journal_growth.py` 的原拒绝点；实际 writer payload 从同一函数生成。
原通用前缀保留，细分为以下固定后缀，不输出路径、进程标题、文件内容或异常原文。

| `GROWTH_PROC_DRIFT_` 后缀 | 实际拒绝条件 |
| --- | --- |
| `DUPLICATE_PID_ENTRIES` / `DUPLICATE_PID_ENTRIES_RECHECK` | 初始 / 最终 PID 枚举出现重复名称 |
| `DUPLICATE_TASK_ENTRIES` / `DUPLICATE_TASK_ENTRIES_RECHECK` | 初始 / 复核 task 枚举出现重复名称 |
| `FD_IDENTITY` | 匹配镜像的 FD 再次 stat 身份不一致 |
| `FDINFO` | 匹配 FD 的两次完整 fdinfo 字节不一致，不仅指 flags |
| `FD_SNAPSHOT` | 同一 task 的两次 FD 名称到身份映射不一致 |
| `TASK_START` | task starttime 复核不一致 |
| `PID_TASK_SET` | 同一 PID 的前后排序 task 列表不一致，包括数量相同但成员变化 |
| `PID_START` | task 列表相同后，PID starttime 复核不一致 |
| `PID_SET` | 最终全局 PID 列表与初始列表不一致 |

PID 复核原 `require(A and B)` 拆成两个顺序 require；A 失败后依旧不执行 B 的读取。
所有拒绝仍停止扫描；不会把正常线程活动假定成安全，也不将部分扫描写成成功。
不增加读取、时钟采样、输出字段、重试、补采、缓存或去重；全部覆盖、预算、权限与期限保留。
v2 的 160 字符 ASCII reason 和固定 progress 合同不变；11 个可达新码最长 48 字符。
旧通用 reason 仍是合法历史结果，不修改旧证据或 guest 中无关的 `proc_bytes`。

独立 AST 复核：仅归一化诊断文字、将该 PID require 对重组成旧逻辑后，整个 host AST
与基线完全一致；真实生成 payload 的完整 AST 同样一致。guest、kernel 源字节未变。

## 验证

Python 3.12.14。两个直接相关测试文件 **217 passed，0 skipped，14.56s**；
十五文件 journal / proc / payload / transport / coordinator 相关回归
**773 passed，3 skipped，35.53s**。SKIP 不计 PASS，不代替普通身份与真实现场验证。
新增 26 个参数化用例覆盖 source/generated 双路径、四种重复枚举、PID 复核稳定与各拒绝
分支、同数量不同成员的 task 集合、匹配 FD 身份和 fdinfo 的先后顺序。
完整合成 I/O 序列证明失败后无新增读取；实际生成入口经 v2 parser、父 observer、CLI
safe_reason 保留精确原因，失败后仍禁止第二次调用。全部使用隔离夹具，无原现场扫描。
内存编译、独立 AST 对比及 `git diff --check` 通过；准确发布提交的 CI 状态另行核对，
不沿用旧 W1 候选的 3/3 success。

## 静态尺寸

host 源 68095 B，SHA-256 `9b833210ed79eb82ead9b6813daf7cacec73be0e67b026beee7668140a7d58c7`；
guest 源 68195 B。用明确合成 D（40 个 `d`）生成 payload 为 26405 B，内存编译通过。
两源 98304 B、payload 32768 B 限额保持。合成 writer argv 的 canonical 字节数为 36282。
19 B 合成 descriptor 的压缩 bundle 为 36335 B，合成 remote argv 为 50523 B；
原 49152/65536 B 门通过。这些只是静态尺寸验证，不能替代原私料或实际现场准入。

## 后续交接

本地 Codex 可同步并继续同范围离线复核，保留旧 terminal 变量、失败输出与冻结交接。
本修复解决的是“同一错误掩盖具体检查项”，没有证明宿主一致性问题或 journal 扩容已解决。
不再次执行旧 W2，不调用 sudo/writer/proc/SSH，不补采、重装或清理现场。
依据 AGENTS 的已消费 W2 边界，新的现场窗口或实质一致性策略变更仍需准确范围与 Owner 决定。
不要再次单纯提高 maps/FD 预算：本次观察到的首因是一致性拒绝。
H01/Q4/H11 与扩容后新 boot 的核心接续尚未完成，支线继续暂停。
