# SC1 固定新代次实现与验证

范围 `LH-Q2-CORE-SERIAL-CONTINUATION-v1`，准确 A
`7869bbcaeb1dad3a1736131a3ff2e225ddf5e7cc`，独立 C
`91c706b52dbc70498d5d872f59874c002cef23db`。准确 Owner B 见
[决定记录](../governance/Q2_CORE_SERIAL_CONTINUATION_OWNER_DECISION.md)。A 三文档保持原字节。

维护固定为 `lhqjgrow-20261007a`，原 06a 消耗和失败不变。按已公开现场索引保护读取
旧五原件、校验内部关系，并核对旧四后续名缺席；新九名全部要求 create-only。
普通预检、消费前复核、核心源读取均绑定旧失败摘要。manifest/receipt v3、preflight v2
携带严格 resume；旧授权作为历史保留，新顶层授权绑定 SC 的 R/A/C/D。

核心仅接受新完整维护原件构建的 journal-transition v2。host 和独立 dispatcher
分别验证新旧代次、准确授权、原件摘要和 boot 关系；reconciliation/history v6 保留
两代完整承诺，capacity v5 要求每相关设备 2656 MiB / 756 inodes。维护门槛为
2592 MiB / 740 inodes；单次动作、期限、CPU/RSS、capture/stream 和镜像限额未改。
原 runtime/wheel/projection/loader、任务身份、四旧批、sudo/sshd 规则保持。

开发树受影响 core/journal 回归 **2179 passed / 35 skipped / 38.88s**。
跳过条件保持原 root/环境要求。新固定代次测试 84 项覆盖保护读取、旧原件缺失/
内容/模式/链接异常、旧后续名、错误旧 D/nonce/事件顺序/失败关系、跨代摘要和两侧
消费者、原件复核拒绝后零 marker/SSH、旧交接/计量重置及准确授权来源。
原完整合成贯通和真实 JournalDevice 构造器测试仍执行。
首轮 2177 passed / 35 skipped / 2 failed 为待更新发行摘要及合成夹具绑定顺序；
修正后上述完整相关组通过，未降低准入条件或删除检查。

本次审查登记 dispatcher SHA-256
`bfa38a11b5b277c41c3ef0091e86a9a01462bed748baf0321ce7679cd63047af`。
旧 dispatcher 不在发行集合。该登记不等于现场准入：准确候选独立安装、既有私料
离线核对、发布、准确 CI 和最终冻结仍须完成后才能开始 SC2。
SC2/SC3 当前 NOT_RUN；未生成真实核心包，也未消费新维护窗口。
原失败原件和私料留在本机，公开代码只使用已公开原件索引的固定 pins。
