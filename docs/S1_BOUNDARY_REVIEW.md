# S1 输入、发布与安装载荷边界复核

日期：2026-09-22。公开主干输入 `936f05e2eb26c5b1ae3addf79467985a00958ceb`；实际验证的产品候选 `da2e82d41be88ada97b6a852f8e8c7e8ba6143d4`，tree `ff17cfbe9c7a08c46cc21ff1fc26796b40f8d141`，直接 parent 为输入主干。发布说明作为该候选的文档子提交，不改变已验证产品字节。

Owner 要求继续检查、有问题直接修复，既有“全部提交推送”授权继续适用。本轮先按链路范围执行，Owner 随后明确“可以全量测试”，因此增加同一候选的完整源码 pytest。仍在 S1 授权范围内；R、A、Owner 关闭决定及顺序不变，三份批准文档与依赖、工作流字节未改。

## 确认并修复的问题

| 边界 | 原问题 | 修复与验证 |
| --- | --- | --- |
| Controller 文件发布 | 最终路径直接写入遇到部分写后 ENOSPC 会遗留半文件；零进度写入可能无限重试 | 同目录唯一临时文件，完整写入并 fsync 后用硬链接原子创建最终路径；不覆盖并发胜者。发布前失败可重试；发布后目录同步失败保留完整文件并报告不确定。源码覆盖短写、零写、write/fsync/close 失败、已有路径与并发胜者；安装态真实 init/build 失败→同路径成功→重复拒绝。 |
| Task 队列接纳 | 空 action 被接纳后无法形成合法 Result，阻塞后续任务 | 不可表示的 action 身份留存原 Task 并跳过；未知非空字符串仍生成带原身份的拒绝 Result。安装态 8 个异常 Task 后的合法 CAS 成功，重复轮次不重放写入，原 Task blob 保持不变。 |
| 有界读取的打开竞态 | lstat 后文件变为 FIFO，阻塞发生在大小检查之前的 open | 支持的平台使用 O_NONBLOCK 打开，再校验普通文件及 inode。真实 FIFO 置换覆盖底层读取、fs.read_text、CAS；拒绝后恢复合成文件，新 Task 正常执行。 |
| CAS 摘要契约 | 以整数解析 64 字符可能接受符号、空白等非法 SHA-256 拼写，并被 already_applied 隐藏 | 精确要求 64 位 ASCII 十六进制；合法大写摘要与幂等重试继续支持。 |
| 目录观察错误 | DirEntry 分类 I/O 错误被吞成成功的 other | 报告 directory_entry_unavailable / indeterminate，保留 errno；真实 FIFO 仍可正常观察为 other。 |
| 安装来源绑定 | 同名导入目录可遮蔽原 .py，同时原载荷哈希保持不变 | 校验扁平包目录、文件类型及缓存布局；拒绝不在约定布局的目录、链接、扩展模块等。新解释器确认真实导入影子包后来源校验拒绝，移走本次合成影子目录后健康 Worker 恢复。 |

## 验证结果

四组稳定复现的基线结果：controller 6 failed / 2 passed；Task 接纳 1 failed / 1 passed；契约与安装布局 4 failed / 3 passed；FIFO 打开竞态 3 failed。修复后新增 20 个测试全部通过。每组原始失败和后续记录都保留；这些预期红测不属于最终候选 PASS。

| 项目 | 结果 | 命令耗时 | RSS 峰值 |
| --- | --- | --- | --- |
| 明确选择的源码链路 | 42 passed | 48.153 秒 | 33976 KiB |
| 完整源码 pytest | 279 passed，0 skipped；0 failed / 0 errors | 314.594 秒 | 119216 KiB |
| 源码外独立 wheel 安装链路 | 81 checks / 266 commands，PASS | 257.889 秒 | 54480 KiB |
| 全部 Python 编译、Linux shell 语法 | PASS | 原始记录保留 | 原始记录保留 |
| 独立构建、全新 runtime 安装及 pip check | PASS | 原始记录保留 | 原始记录保留 |

RSS 使用 Linux wait4 ru_maxrss，为回收子进程及其已等待后代的记录值，不代表同时运行的进程树内存总和。任何 skipped 都不计入 passed，原因保存在 pytest 输出及 JUnit XML。全量源码测试不等于 GitHub 全平台 CI；本轮未触发完整 CI 矩阵。

wheel SHA-256：`0033d3f4fcc1d77b312bae03dc0a85c0bce5e33cc943a32848ebf08d1f291eb9`。

独立复核从 Git 对象核对 83 个源码 blob、23 个载荷文件、29 个 wheel 成员，以及 wheel / 安装 RECORD 与真实 bytecode；36 份业务收据与来源身份一致。新增专项复核读取实际裸仓库的已冻结远端提交，将 Task / Result blobs、命令参数、stdout/stderr、持久收据和恢复后业务文件逐项对应。原有 7 个读取故障恢复案例、5 份未提交文件归档和 2 份 Git 自动维护 trace 也核对通过。

CLI wait 成功取到一个合法 Result 时可返回退出码 0，即使 Result.status 是 rejected 或 indeterminate。本轮分别断言退出码和业务状态；没有把返回成功当作业务成功。

## 环境及失败记录

本轮使用新建独立 checkout、build venv 和 runtime venv，保留既有环境。环境为云端 Linux x86_64 / overlay、Python 3.12.14、Git 2.51.1；不能代替 GX10 / aarch64 / ext4 实机。

GitHub 直连克隆先后遇到 HTTP 502 和代理 CONNECT 403，两次 exit 128 均保留。之后通过已授权 GitHub 接口读取提交元数据，以 --no-hardlinks 的独立本地 clone 导入已核对 blob。精确 tree 和完整 commit SHA 均与 GitHub 对象一致，工作树 clean，git fsck 通过。该过程是接口取证与本地对象校验，没有宣称直连 fresh clone 成功。

准备过程中另保留两条失败：首次提交重建使用不同的时区/末尾换行，完整 SHA 断言拒绝；根据已有 Git 对象的原格式修正后才得到精确候选。首次 checkout 身份检查发现索引已填充而工作树尚未物化；完成物化后重新核对 clean。这两条是验收准备失败，不计为产品缺陷或 PASS。最早两版 FIFO 探针分别存在 fixture 不完整和监督异常被 I/O 包装的问题，原脚本及失败日志单独保存；产品结论依据修正监督方式后的稳定基线复现。

独立审计首轮另发现计数脚本把保留的合成 dangling symlink 计入业务收据；按 lstat 类型区分后确认是 36 个普通收据及 1 个既有故障链接，并独立核对链接目标。该审计脚本失败与修正版本也保留，产品源码和实际收据没有因此改动。

所有保留的记录、原始日志、摘要、退出码、耗时与 RSS 均进入私有证据包，公开仓库仅存修复、测试和本摘要；不上传 SOP 历史或 GX10 原始证据，不添加许可证。

## 结论边界

- 来源布局检查是漂移检测：Python 导入已发生，不能阻止任意恶意导入副作用，也不构成本地任意写入攻击者的隔离边界；不声称认证任意 pyc 字节。
- O_NONBLOCK 解决这里复现的 FIFO open 阻塞，不承诺网络文件系统或普通文件 I/O 的硬实时截止。
- 故障发生时的短暂文件状态依据已执行注入程序的断言、记录及后续结果交叉验证；独立审计没有伪称重新观察已经恢复的历史现场。
- Windows 继续 DEFERRED / UNVERIFIED；未切换现役服务，未执行 S2 或 artifact-ledger A2。
- 前轮 pack 扫描失败和更早文件同步异常的根因仍未完全确认；本轮通过不关闭那些历史未决归因。
