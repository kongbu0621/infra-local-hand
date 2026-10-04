# 核心 v2 本机复核与安装子进程收口

2026-10-04。承接云端 `bd4a106d19869aa845eec5eaf2f71f81e287eae9`。
本件是原 CLOSED D1–D4 内的局部交付，不是完整 D2、D4 或现场验收。
R、A `0bdb49cae5586be60a7ba31d4a8e8367854d1e8c`、B 和 C `7598886` 不变；
三份 A 原字节未改。冻结 runtime candidate、wheel、projection 未替换。

## 实际修复

- 云端提交的 [CI 37179791082](https://github.com/kongbu0621/infra-local-hand/actions/runs/37179791082)
  在 Ubuntu、Windows 均失败，不是成功。Ubuntu 的八项新 bootstrap 测试在普通 runner 对 `/`
  使用 `O_NOATIME` 时失败；现在只把合成根映射到本测试拥有的临时目录，真实 fd、inode、内容及
  NOFOLLOW/NOATIME flags 不变。没有改运行时 root/ownership/no-fallback 校验。
- Windows 的合成 RAM-loader 测试把历史 Linux 路径交给了 Windows `Path`；合成源码改用
  `PurePosixPath`。历史 Git 源码、loader 和原验证器未修改，没有新增 Windows 现场支持声明。
- 安装 callback 的每个 spawn/select/read/nonblocking/wait 边界增加原时限前后检查；晚返时保留
  已发生的 child、读数和 wait，不把它们升级为成功。安装工作不能借用原 45 秒 final reserve。
- 使用真实 `wait4` 保存 child wait status、user/system CPU 和 Linux 最大 RSS；真实退出和双 EOF
  缺一不可。非零退出、超流量、selector 创建失败和晚返均停止，无重试。
- 失败只在原 outer deadline 内 kill/reap/drain；leader 已退出但子进程仍持有 pipe 时不能跳过
  process-group stop。已 wait 且双 EOF 的进程组不再发送 kill。outer 已到期不增加一秒清理尾窗；
  wait/EOF 缺失明确保留为未知。关闭本地 pipe fd 不被当作 EOF 证据。

这些 child rusage 只是实测的安装组件统计，不是跨 unit 的完整资源峰值。
`usage()`、readiness 和 release allowlist 仍 fail closed。

## 本地既有原件复核

只读取已保留的固定原件，未连接 guest。四 carrier 原件通过原 held-reader 的 mode/owner、
O_NOATIME、长度、摘要和稳定性校验；新聚合器解析出 16 locator mapping、16 retained paths、4 domains。

固定历史 D `8fd84521cdd25b455ff148e0c0fed6b5d8e39fe1` 的 42 个 Git 工具与原 pins 相等。
新 RAM-loader 对原 48 blobs 运行原纯验证器，通过 12 棵历史树、7 行义务和 610 项 forward baseline
复核；新 adoption parser 也通过。原 manifest 为 34010 B，SHA-256
`f705d3c77885887c7b6f799f4721dfefd0e9c588dbd11085cc8456fe623c6d40`。
一次查找误把后续 review 文件定位到原 D，Git 明确报不存在；改从当前已提交 review 取得工具名和 pins，
再逐一从准确历史 D 读取源码。没有执行旧 entry 或继承旧 run permission。

这不是整个 approved-input 聚合构建，也不是当前 host/guest admission。
私有原件、路径及完整机器身份不进入公开仓库。

## 验证与未完成项

13 个核心模块：293 passed / 8 skipped；8 项需要 root protected fixture，本机普通用户未覆盖，
不得记为通过。此前云端 PID 视图失败项在本机通过，产品身份检查未放宽。
最后增加“已退出且双 EOF 不再 kill”收口后，四个直接相关模块：115 passed / 8 skipped。
首次新增外层超时负例缺少测试 `io` import，失败已保留并修正；不是现场失败。
完整 source suite 返回 **4204 passed / 99 skipped，431.47s**；报告保留在本机
`lh-core-v2-source.GRh1fG/results.xml`。使用普通本机用户及子进程局部 umask 022，没有 sudo 或系统配置变更。
该运行在最后“已 wait 且双 EOF 不再 kill”两行收口和对应断言之前启动/加载模块，故不写成最终 D 的
全量重跑；最终差异的四模块回归为上述 115/8。最后源码 D 为
`33de2ccd5575f73f7644905008b92011c2f8e7e0`，tree `773ccf5f5ab1b2e0afa0e794f7cca86337cb49d9`；
dispatcher 为 199375 B，SHA-256 `40933788491a247afe0be1d1e78d82d47afef518ddaa2854c78741d48b0a5880`。
bootstrap 保持 48828 B，未扩大 49152 B ceiling。
[准确 D 的 CI 37183191347](https://github.com/kongbu0621/infra-local-hand/actions/runs/37183191347)
提交本记录时仍在运行，不能引用旧 CI 当新 D 的 PASS。没有运行本机 installed release suite。

仍直接阻塞：current guest collector/policy、逐 pool 准入、安装内部所有 I/O deadline/执行身份与
shared-pool accounting、existing-account preparation、plan、H01/Q4/H11 真效果、phase facts 和全量 usage。
另有原协议缺少 host writer 传输字段的文档缺口，见云端 v2 review；不能用 guest identity 或摘要
推算替代。[独立 OPEN 最小方案](../governance/Q2_CORE_WRITER_TRANSPORT_BASELINE.md)已冻结准确 A，
尚未新增该协议 source/test 实现。该小范围修订须独立准确批准，其余原 CLOSED D 工作仍可继续。

本轮 marker/request/H01/Q4/H11 为 0；没有现场重装、配置变更、清理或重试。
真实业务任务未执行，退出/结果/证据未收回，package 未发行。namespace/watchdog 仍暂停，production
`E3_SUPERVISION_UNVERIFIED` 不变。
