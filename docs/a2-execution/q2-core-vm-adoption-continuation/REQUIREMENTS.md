# 接入已修复 VM，完成原核心任务

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-VM-ADOPTION-CONTINUATION-v1`，VA1–VA3；三文档为一个批次。
固定 R `10d2a5c827964989f41ca6e8eeac3d44de6d0f04`、直接来源完整性、Owner 权限、
无例外及 A→B→独立 C→D 规则保持。离线候选按 Owner 直接修复方向准备，不代表现场批准。

## 已有结果与唯一交付

输入基线 main `6eacc7e` 已记录原 Q1 VM 的修复副本成功启动、一次 SSH、准确本地
模块包安装及前后 quota 挂载验证。事件 `LH-Q1-QUOTA-REPAIR-ACTIVATION-20261009-03`
的 30 份不可变返回和索引已留存；活动 pidfile/console 不属于不可变索引。
原 system 和旧失败记录保留。此成功不是 journal 容量验收；H01/Q4/H11 尚未运行。

只接通维护入口、维护返回生成端和核心验证端：使用已核验的新 PID/start/argv、当前
host/guest boot、活动 system 副本，保留历史 Q1/HELLO 的旧 boot 和九代失败记录。
完成一次剩余 journal 256→512 MiB 维护；只有完整成功后运行原未发行
`lhqcore-20261007a` 的 H01 正常执行与结果、Q4 运行取消、H11 同任务恢复。
不增加探测 SSH、重新安装模块、额外启动 VM、扫描器或其它功能。

## 本批次与不变边界

- VA1：完成两侧实现、离线真实来源和包大小核对、发布 main、准确 D CI、独立安装
  验证及两个 caller 冻结。新 R/A/C/D 必须明确绑定；未批准时现场入口保持关闭。
- VA2：唯一新维护 `lhqjgrow-20261009a`。普通预检和同窗 execute 共用原点、nonce、
  manifest 和累计计量。最多两次固定 SSH（pre/post），一次经验证正常关机/退出，
  journal 完整备份、扩容、比较、一次维护内原配置启动和完整 post 验证。
  此一次维护内启动与已消费的修复启动区分，不复用任何旧 caller。
- VA3：仅 VA2 全部成功原件验证后，同一 D 发一次原核心批次；三个 case 顺序不变。
  VA2 不完整时 VA3 不可独立执行。批准后范围内无需逐子步骤重新批准。

九旧维护窗口 06a/07a/07b/08a/08b/08c/08d/08e/08f 均保持消费、失败和 UNKNOWN。
新增一代后的完整义务为 **12960 MiB / 3700 inodes / 1200 CPU-s**；加原核心捕获
64 MiB/16 inodes，宿主准入底线为 **13024 MiB / 3716 inodes**。不按小产物减账。

维护仍为 900/780 秒、CPU120 秒、RSS512 MiB、AS256 MiB、FD128、8 控制子进程，
VM4 vCPU/8192 MiB。备份320 MiB、journal目标576 MiB、capture8 MiB/32 inodes、
单流1 MiB；双源各98304 B、bundle49152/393216 B、短预检4096 B、marker和
transition65536 B。核心原900/800/750秒、32 MiB包、1 MiB approved-input 和其余
原额度保持。原DS声明19/7/7、Q1精确来源、域/cgroup、当前业务进程、writer、数据、
ext4/UUID/内容、正常关机和两侧身份保护不放宽；管理前提沿用原批准，未知或矛盾即停。

活动 system 的启动前 SHA 只证明获准候选，不要求正常启动和安装后内容仍等于该 SHA。
接入仍检查准确路径、设备/inode、权限、父目录、argv及运行身份；关机后稳定性保护保留。

## 验收与披露

成功标准是 VA2 完整 VERIFIED 及原 live finalizer 的三个实际 verdict。离线测试、
启动成功或 CI 通过均不得写成核心 PASS。任何失败停止并保留，不重试、不补采、
不清理、不回滚、不另开窗口；不停止未知服务，不新增核心 H11 以外的恢复操作。

请求批准本三文档、实现和必要脱敏记录发布到既有 main，以及仅公开旧08f五件原件的
basename/bytes/SHA-256 最小索引（准确旧D `db6e7165322da3072ca1fd88a36401e18ebd4a86`）。
发布前须与原私有记录及保留副本一致核对。30份启动/安装原件、机器路径、PID/boot、
原始流、新维护原件及新索引保持私有。不得把其它已消费观察或启动授权重新使用。
