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

## 首次候选 CI 与测试隔离修复

候选 `d8bbad055d819cd5f40307e75c5c0917855c495f` 的首次CI `38138701783` attempt 1
保留为失败：Linux 7830 passed / 89 skipped / 48 failed；48项都在新增文件/管道测试的
资源准入处提前失败。单文件运行正常，但整个pytest进程此前累计的CPU/RSS被该单次
读取测试误当成自身用量。Windows2025 passed /1391 skipped，其独立安装10/10通过；
该候选本地独立安装94检查/292命令通过。主工作区第一次构建因用户未跟踪`.codex`
被洁净来源保护拒绝，文件保留，安装验收改在准确候选的独立checkout完成。

只为文件/管道单元测试提供明确的合成正值预算样本；真实Budget的累计CPU、高水位、
限额与生产代码保持原字节。独立子进程中的真实FD/AS/CPU/RSS测试和完整私有载体
仍运行原Budget。失败不取消、不重跑替换；新准确D另取自己的首次CI/独立安装结果。
HB2尚未发行，没有现场读取或审批拒绝。

## HB1 最终冻结与 HB2 实际返回

最终 D `240ee61c84531af843499b251d0e259736a66816` 下降自独立 C，准确首次 CI
`38139680995` attempt 1，3/3 success。Linux 7878 passed /89 skipped，另有真实root
隔离检查16 passed；Windows2025 passed /1391 skipped。两端独立安装分别94检查/
292命令和10检查/10命令通过；本地准确D的独立安装同为94/292 PASS。对单元测试宿主
人为注入超限的历史CPU/RSS后，新63项仍通过；生产Budget原字节未变。前一候选的
首次CI失败及其安装记录独立保留，没有取消或重跑替代。

[PR #20](https://github.com/kongbu0621/infra-local-hand/pull/20)正常merge commit
`9f2156d3d644869e8ea4561843037dcf138b9840`保留C→D次序，未squash。六份私有准备/
调用/保留辅助脚本、两个准确D源码副本、完整请求及36个输入已核对并冻结。最终私有
freeze 5303 B，SHA256 `bdd83c731ed558b2997aefbe3c16456fae2e42663011fe34739b2b4d6b46b5c9`。
私有完整载体5项隔离测试通过，实际FD峰值75；固定完整生命周期FD上界108，合成最坏
单记录95851 B，总捕获上界917504 B，均在原限额内。reader从父进程时钟原点计225秒
停止，父捕获在原240秒内留15秒收尾；CPU/AS分区及所有原限额不变。HB1 COMPLETE。

唯一事件`LH-Q2-CORE-HOST-REBOOT-READ-20261011-01` / `lhqhost-20261011a`随后执行一次。
新调用记录已创建；工具和父/子调用实际退出均为0，父捕获双EOF，唯一本机监听命令
实际退出0/双EOF。独立离线消费者通过，终态为`CONSUMED_FIXED_HOST_READ_COMPLETE`。
12个实际文件原件、实际工具完成返回、私有原件索引、独立结果及单独terminal保留；
pidfile.raw不存在，因为固定pidfile本身明确ABSENT。freeze及全部冻结辅助脚本未改。

这次读取的明确事实：

- 当前host boot与RP2实际window一致，与旧activation不同；同次读取前后boot和三个
  自身namespace保持一致。没有伪造旧boot或变换运行视图。
- 固定旧PID和pidfile均ABSENT，因此只查询一个PID槽；serial存在，只读metadata。
  原固定端口无监听，没有查其它PID、端口或读取其它程序cmdline。
- 六个镜像均通过当前类型、属主/写位和同次稳定性保护；工具身份通过。六个inode、
  UID/GID/mode/nlink与固定保留来源一致，但六个对象的设备号统一不同于历史设备号，
  因此六个历史device/inode二元组都不匹配。

后续分类只使用已捕获返回及已pin的启动来源，未补采。设备号变化的原因未被本次读取
证明；本次没有filesystem UUID或挂载来源观察。旧固定本机返回中的data_mount只是
布尔值，也不是filesystem UUID证据。不得由inode/权限相同推导内容相同、磁盘连续性
或允许自动替换设备号；候选system的旧内容摘要仍仅适用于PRELAUNCH范围。

读取成功不是VM、guest或核心通过：没有可采用的原VM运行实例，guest身份仍UNKNOWN，
旧镜像绑定不能直接使用。后续核心接续必须先解决当前宿主/镜像身份采用，再决定新的
原配置启动和guest验证；本批不授权这些动作。未发SSH/网络连接、VM启动/停止/重启、
guest命令、维护或核心包，未更改任何镜像/权限/配置，未删旧文件，未触发审批拒绝。

HB2已经终结，不重放、重试、补采、换wrapper或开启另一窗口。旧RP1 freeze、RP2终态
及其全部15个caller/dependency保持；十八份完整维护义务和25287 MiB/7492 inodes总
预约不退款。H01/Q4/H11仍NOT_RUN，NAS discovery/admission和外围继续屏蔽/暂停。
