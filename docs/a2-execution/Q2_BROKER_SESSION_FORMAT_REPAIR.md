# Q2 broker session 格式修复

2026-10-01 的限定正常链回执已确认：运行登记文件修复通过，内存上限修复保持有效。
controller 收到 ordinary 的首包时，SCM_CREDENTIALS 的 PID、UID、GID 与预期一致，
控制消息数量为一，没有截断或额外描述符。随后 controller 报 `IDENTITY`；resident
后续收到零字节、零凭据后报告的 `BRIDGE_CREDENTIALS` 是连接关闭后的结果。

对私有现场 preparation 与 SQLite 原事件进行只读核对，并调用原装配器离线复现，
失败定位于 `q2_chain.build_grant` 对 broker session 的格式检查。原 Broker 使用
`uuid.uuid4().hex`，原 budget 合同也要求精确32位小写十六进制；管理员单阶段及三阶段
装配器却使用了 bridge transport nonce 的64位格式。

修复只把两处管理员装配器的 broker session 格式改为精确32位。继续要求传入 session
与原 preparation 严格相等，继续保留 generation、budget、allocation 绑定；bridge
transport nonce 仍精确64位，PID/UID/GID、截断检查与所有停止条件不变。

回归包括真实 Broker 生成 session、SQLite 原预算/事件、Phase.snapshot 到两个 grant
构造器的连接；拒绝不同32位 session、64位 transport nonce、非十六进制及错误长度。
119项相关装配、正常链、bridge、binding、resident和budget检查通过。离线验证不表示
新的现场运行或Q2/Q3/生产验收通过。原始机器身份、session值及现场文件不入公开仓库。

现场应用需明确的新候选来源与构建回执，不得编辑旧安装元数据冒充原版本。计划复用
既有Python和工具，以并列的新代码目录保留旧安装及全部失败现场；不重建环境、不自动重试。
