# 已修复 VM 接入：准确冻结与一次维护返回

VA1 已完成；唯一 VA2 `lhqjgrow-20261009a` 已消费并失败。
VA3 和原 `lhqcore-20261007a` 的 H01/Q4/H11 均 **NOT_RUN**。

## 准确实现与执行前验证

- A `13cd2d3e7ac9a307a7c960f713524fefa2959a95` 的三文档保持原字节。
- 独立 C `31b8e21116edd3678d738c1b9525edb6b3da8ae8` 只登记真实 Owner B 和范围。
- 直接子 D `54d32df2f82fe863e1535ddb8134617c2654e33d`，tree
  `9fc02731ca188292f7e7a170e632ca1c6ba871b7`，已发布 main。
- D 的[首次 CI 37917868612](https://github.com/kongbu0621/infra-local-hand/actions/runs/37917868612)
  attempt 1，三个 job 全部成功；Linux 7228 passed / 89 skipped。
- 本地相关回归 2979 passed / 35 skipped；准确 D 独立 wheel 安装验收
  94 checks / 292 commands 全部 PASS，未改动现场安装。

完整核对固定 Q1 来源、四次核心旧原件、九代维护45件原件及30份启动/安装返回。
activation archive 通过准确索引与语义核验，接入历史、当前与维护后 boot 的独立关系。
两调用器及其依赖、来源和额度在 VA2 前冻结。调用器的合成检查覆盖预检失败、
执行失败、成功交接和重复调用拒绝；诊断完整进入结果与摘要。

真实保留输入的 marker 静态上界 59580 B，compressed/expanded bundle
40205/136608 B；准确 D 静态成员 17358216 B，核心包上界19455383 B。
完整核心输入393802 B、transition16092 B、短预检709 B，均低于原上限。
后面三个大小使用明确标注的合成维护成功投影，未生成真实核心包，不代表现场成功。
十代维护加原核心捕获的13024 MiB/3716 inodes准入底线及其余额度保持。

## 唯一 VA2 返回

本地预检通过，随后在同一窗口使用冻结 manifest/nonce/双时钟执行。消费标记已创建，
一次 pre SSH 后停止：宿主 `STOP_AND_RETAIN / GROWTH_REPORT_MISSING`。
已捕获 guest v3 返回为 `INCOMPLETE / PRE_QUIESCENCE / GROWTH_GUEST_IO_OR_RUNTIME`，
`actions_started=[]`。诊断上下文指向用户级 systemd 管理器的 show 校验，`errno=2`
（ENOENT）。原件没有指出具体缺失路径，也不能区分查询准备、执行或重校验中的失败点；
不据此声称某个运行目录或 bus 已被现场确认缺失。

没有发送 poweroff token；没有备份、镜像/文件系统扩容或维护内 VM 重启，没有发出
核心包。SSH 子进程已返回，但 receipt 的 `remote_exit=UNKNOWN` 保持原样，不能将
本地子进程退出等同于独立证明远端闭合。

本次五件原件已保护读取，与 caller 返回、原 manifest 及流摘要一致核对，创建独立
私有保留副本及索引。原执行前冻结不变；私有 gate 已登记
`VA2_CONSUMED_FAILED_STOP_AND_RETAIN`，VA3 不可独立执行。
新09a原件/索引、机器身份及原始流保持私有。

## 后续边界

本批已完成源码接线、发布、验证和一次获准维护尝试，未完成 journal 容量验收及核心
三个 case。十代窗口全部保持消费，旧失败和 UNKNOWN 不改。没有重试、补采、清理、
恢复或新窗口；不跳过用户域、进程或 writer 保护。通过源码或 CI 不能恢复本次消费，
也不构成核心 PASS。现有返回只能支持上述定位范围，任何更深现场动作不在本次失败后
继续执行。
