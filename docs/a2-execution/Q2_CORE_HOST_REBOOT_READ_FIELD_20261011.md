# 宿主重启后的固定本机读取

2026-10-11；`LH-Q2-CORE-HOST-REBOOT-READ-v1` / HB1–HB2。
[批准基线](../governance/Q2_CORE_HOST_REBOOT_READ_BASELINE.md)与
[Owner B](../governance/Q2_CORE_HOST_REBOOT_READ_OWNER_DECISION.md)保持准确 R/A。
独立 C `62d485c499d02744fbf83a8653c1aa7f80be0584` 只登记批准，D 从 C 继续。
A 的三个文档保留原字节，历史 OPEN 标签不覆盖新的准确批准。

## HB1 实现与已完成的离线核验

新增 E3 固定本机读取辅助代码及独立离线消费者，产品 CLI/MCP 没有新入口。
只从冻结请求取固定目标：boot/self namespaces、pidfile/serial、最多两个 PID、六个
镜像元数据及固定工具，一次原端口本机监听查询。进程先 stat/exe，固定 QEMU 才读
cmdline/namespaces。镜像不读内容；PID 缺失、复用、监听占用、对象身份不符分别记录。
父子管道保留实际退出/双 EOF，独立消费者验证完整原件、请求/nonce、来源和字段关系。
消费者输出始终 release=false、core=NOT_RUN，不创建 activation 或改 dispatcher 发行 pin。

只读源核验重建两份现有归档，与 RP1 activation 相等；原启动 argv 的 NUL 字节摘要、
六个镜像 device/inode、10 个实际 RP2 本地返回及15个旧caller/dependency摘要全部一致。
新请求绑定36个现有输入、1584885 B；保留源检查同时持有36个文件和10个目录。
没有复制或更改旧归档/冻结/终态，没有现场观察。唯一新准备池按批准位置创建。

本地新读取器测试63项通过，使用真实临时文件、管道及真实FD256/AS512 MiB子进程。
覆盖同/异boot、namespace漂移、PID缺失/复用/去重、非QEMU不读cmdline、坏pidfile/
symlink、六镜像身份与保护、监听空/占用、非零退出、双EOF缺失、超限、来源/nonce/
费用替换、保留失败及重放拒绝。加既有source capture和NAS suppression回归为
159 passed / 1 skipped。测试只使用隔离对象，不是现场读取或核心PASS。

总预算仍25287 MiB/7492 inodes、十八份完整维护义务；新准备与捕获各2 MiB/64 inodes。
父捕获/reader/唯一控制子进程CPU分区30/180/30秒，总240秒；AS分区256/512/256 MiB，
同时在地址空间上限定聚合RSS上界1 GiB，并保留实际getrusage高水位/CPU而不重置。
每进程FD256、同次wall240秒、双流各64 KiB、记录128 KiB、总捕获2 MiB不变。
完整私有调用器、实际字段的最终序列化/FD/分配核验、正常PR发布、准确D首次CI、
独立安装及最终冻结仍在HB1内完成；完成前不调用HB2。

当前HB1 VERIFYING、HB2 NOT_ISSUED。RP2继续INVOKED_FAILED_UNCONSUMED，旧终态和
全部caller保持；H01/Q4/H11 NOT_RUN。NAS和外围暂停。本批完成或失败都不重放、补采、
更换wrapper或修复现场；读取事实不预先授权启动、guest核验、维护或07a。
