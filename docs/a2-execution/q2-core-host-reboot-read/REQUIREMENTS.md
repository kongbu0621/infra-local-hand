# 宿主重启后的固定本机身份读取

2026-10-11；Authority：Owner；PROPOSED / Gate OPEN / NOT APPROVED。
Scope `LH-Q2-CORE-HOST-REBOOT-READ-v1`，HB1–HB2。R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`及其直接来源/完整性、Owner mandate、
Owner-only closure、无例外及变更控制保持，见根AGENTS.md。

## 原核心阻塞与唯一目标

原核心仍是未发行07a的H01执行/结果 → Q4运行中取消 → H11同任务恢复查询。
RP1已完成；唯一11b预检因GROWTH_ACTIVATION_HOST_BOOT退出3，没有SSH、marker或
execute；其不可重放终态与原冻结保持。Owner随后确认“重启过宿主机”。旧activation
由原归档重建无误，但它绑定重启前的实例，不能直接改boot/PID作为新实例证明。

现有返回不足以判断当前固定VM是否已启动、旧pidfile是否仍在、固定端口是否占用及
原镜像对象身份是否保持。HB2只补足决定下一段核心接续所需的这些固定本机事实；不
借此部署观察平台、扫描环境或扩展产品。NAS发现与新作业入口保持关闭，外围继续暂停。

## 待批准范围

1. HB1：普通修复发布完成后，为这个准确scope接入固定来源、一次性本机reader、
   私有输出及独立离线结果核验。测试、正常PR merge、准确D首次CI/独立安装、限额与
   输入/调用器冻结完成后才允许HB2。旧freeze/caller/terminal保持原字节。
2. HB2：新事件`LH-Q2-CORE-HOST-REBOOT-READ-20261011-01`，会话`lhqhost-20261011a`，
   唯一一次本机读取，执行环境为当前工作宿主的正常用户视图。读取固定host boot及
   命名空间、原pidfile/serial条目和最多两个来源绑定PID、原六个镜像对象metadata、固定QEMU/ss
   可执行文件身份，并对原SSH转发端口执行一次固定本机监听查询。

不发SSH/网络请求、不向任何远端发送源码/路径/机器资料，不启动、停止或重启VM，
不安装、改变配置、写镜像、删pidfile、修复权限、重放11b或发行核心包。除新私有准备/
输出目录外不写现场状态。读取成功也不授予采用新身份、启动、维护或核心执行权限。
这些后续动作须依据实际返回形成准确方案；此时不预批未知的VM恢复分支。

## 接受与失败条件

来源、工具、路径和预算均通过、固定对象逐项有明确结果、EOF和实际caller完成完整，
才可报告FIXED_HOST_READ_COMPLETE。已消失的旧PID/pidfile按明确ABSENT事实表示，
不伪造成读取故障或运行实例；PID复用、监听占用、对象不符只作为当前事实，不授权
停止其它进程。未知/超限/来源矛盾则INCOMPLETE并停止。完成与否都不得重放或补采。

原十八份完整维护义务及旧费用25283 MiB/7364 inodes保留，无退款；本批新增source/
caller准备池2 MiB/64 inodes及本机捕获池2 MiB/64 inodes，总计25287 MiB/7492 inodes。
这不是新维护代数。两个池各CPU/wall240秒、聚合RSS1024 MiB、每进程AS512 MiB/FD256；
读取仅一个控制命令，双流各最多64 KiB，单记录最多128 KiB，总输出不超过2 MiB。
这是新有界读取的待批费用；未获批准前不创建执行准备池或reader。

必要文档/实现/脱敏结果经正常PR发布，原始返回、路径、PID、boot、索引和调用器私有。
HB1 NOT_STARTED，HB2 NOT_ISSUED，RP2终态及H01/Q4/H11 NOT_RUN保持。
