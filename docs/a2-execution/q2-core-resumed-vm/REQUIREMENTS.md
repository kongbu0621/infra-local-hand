# 当前 VM 的原核心接续

2026-10-10；Authority：Owner；**PROPOSED / Gate OPEN / NOT APPROVED**。
范围 `LH-Q2-CORE-RESUMED-VM-v1`，RC1–RC4；规则 R
`10d2a5c827964989f41ca6e8eeac3d44de6d0f04` 及其直接来源、完整性、mandate、
Owner authority、无例外和变更控制沿用根 AGENTS.md。本三文档仅准备一个完整核心批次。

## 目标与事实

唯一交付：原 H01 正常执行及结果收回 → Q4 运行中取消 → H11 同一任务恢复查询。
NAS、插件/连接器扩展、扫描器、独立诊断平台、无关重构和其它验收支线暂停。
鉴权、任务/进程身份、数据保护、资源上限、取消/恢复和结果完整性属于核心保障。

基线 `b0fffefd95335fd8835f0ac5a6b01c3d2ca51654` 保留以下事实：TC1 已完成；
唯一 10b 在本地预检因 host boot 不符停止，SSH/marker/execute 均为零；不能重放。
随后获准的 Q1 原配置启动已完成，宿主 PID/start/argv/exe/namespace 与固定监听通过，
SSH 为零。新 guest boot 和 guest SSH 就绪仍 UNKNOWN。旧 activation/v1 同时绑定
旧安装和旧 guest 身份，不能修改它的 boot/PID，或用宿主启动成功代替 guest 证明。
十二代维护已消费；09c、10b 为已调用但未消费维护的预检；十四份完整维护义务保留。

## 一次确认覆盖的整批动作

1. **RC1：离线实现和核验。** 分开历史安装证明与当前启动证明，接齐维护 producer、
   独立核心 consumer 和私有调用器；保留 10b 的六份本地返回、freeze、失败和终态。
   完成真实保留来源核验、完整资源/大小检查、准确 D 首次 CI、独立安装与调用器冻结。
2. **RC2：一次当前 guest 核验。** 在已启动的同一 Q1 VM、原固定 SSH 端点/账户/密钥上
   发起一次只读核验，确认 guest boot、准确已安装包/版本/完整性、运行内核与模块关系、
   原 quota 挂载。前后核对固定宿主/VM 身份；不启动 VM、不安装包、不加载模块、
   不改配置、不停服务、不探测其它端点。失败即停，无重连或补采。
3. **RC3：一次原维护。** 仅 RC2 完整通过且最终输入冻结后，调用唯一新
   `lhqjgrow-20261010c`，一次 preflight，通过后同窗一次 execute。至多两次固定 SSH、
   一次经核验的正常关机、原 journal 增长、一次原配置维护重启。
4. **RC4：原核心验收。** 仅完整成功维护原件与实际 coordinator completion 独立通过后，
   发行原未执行的 `lhqcore-20261007a`，依次完成 H01→Q4→H11 和结果收回。

批内不逐项重复审批。任何未知、矛盾或失败都停止并保留；不重放旧调用器，不重试、
清理、回滚、追加观察、额外恢复或增加窗口。H11 仅指原任务的恢复案例。
这不是既有批准的自动延期，亦不把历史失败改成成功；RC1–RC4 须有针对准确 A 的 B/C。

## 不变条件和有界增量

沿用已修复 system、原数据盘、既有安装与 SSH 信任；保留原 system、旧日志和全部原件。
declared 19/7/7、准确 Q1、system/user 角色、domain/cgroup、当前进程/写入者和数据保护，
trusted-single-admin、declared-startup 前提均保持。原 55 件 custodian 的连续持有不变。

维护原 900/780 秒、每窗累计 CPU 120 秒/RSS 512 MiB、每进程 AS 256 MiB/FD 128、
最多八个控制子进程、VM 4 vCPU/8192 MiB、两 boot 各 12 个准备命令/60 秒不变。
RC2 单独上限 120 秒、host/guest 各累计 CPU 120 秒、RSS 512 MiB、每进程 AS 256 MiB/
FD 128、最多八个控制子进程；两条输出各至多 65536 B，宿主完整输出预留 1 MiB/32 inodes。
使用固定命令和内存传递，不在 guest 落地新脚本或创建工作目录；系统 SSH 日志按原配置记录。

十五份维护义务为 19440 MiB/5550 inodes/1800 CPU-s；加原核心捕获为
19504 MiB/5566 inodes，再加 RC2 宿主输出为 **19505 MiB/5598 inodes**。
RC2 的 host/guest CPU 分别另计，所有历史成本及此前启动/读取义务保留，不退款或跨池挪用。
义务数量不代表已消费次数。原源码、包、argv、报告和证据上限全部保持。

只批准本三文档、必要实现和脱敏结果发布 main。原件、逐文件索引、归档、调用器、
机器标识和私有路径继续私有。完成标准是三个核心案例的真实结果；源码/CI/安装或
单独维护通过均不替代。当前 RC1 NOT_STARTED，RC2/RC3 NOT_ISSUED，RC4/H01/Q4/H11 NOT_RUN。
