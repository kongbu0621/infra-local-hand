# Q1 固定对象与监督判定核心：验证记录

源码检查点：`ec2fac0f41c4430f7b18d9b9ce99f32b2e65c6df`，
tree `411e2acee38af102851e2eee9e09e9d17d1b7c04`，
父提交 `2d1a800572d933f684d04401dfcbd7672671300f`。
本记录提交在源码检查点之后，不把报告提交算成被测源码。

范围仍为 `LH-E3-QUOTA-HARNESS-v1`，批准 A 为
`415327ebdcc251bb055da9931a7a88990f750b7a`，独立 C 为
`5a4ea852091db06549a876e42bbd5f95d5869d3b`。三份权威文档摘要与 A 一致，未改写批准边界。

## 本次变化及结果

已完成 **Q1 内部固定对象数据校验和有限结果采集/退出判定核心**，没有完成实际 observer 服务。
新代码位于 `tools/admin/local_hand_quota_observer/admission.py` 和 `supervision.py`。
前一轮 C 原语和 test-only syscall shim 字节未改；默认 wheel/Plugin 和生产 job 路径未改。

- 对固定管理 manifest 的精确摘要、版本、字段、整数/路径、slot/generation、根身份、FS/project/额度
  进行有界校验；不可变映射拒绝别名、根重叠和冲突，共享计费域只计一次。
- 固定原 manifest/slot、request、allocation、execution/phase 和 unit/cgroup，截止时间取原阶段与
  最多 30 秒管理上限的较小值。内部绑定本身不授予资源或代替持久准入。
- 一次读取至多 4096 bytes，原始前缀至多 4095 bytes；只读取非阻塞 pipe，不打开目标根/结果文件。
  没有等待循环或新工作启动路径。超量、部分/额外回包、管道/时钟错误保持 UNKNOWN。
- 同时需要完整 EOF、成功退出、逐项匹配的原语事实，以及独立提供的原 boot/unit/InvocationID/cgroup
  和启动交付/排队/围栏/递归进程树/采集器终止事实。停止事实与成功事实分别记录。
- 响应丢失的恢复不能重新生成成功；缺少原 InvocationID 不能用当前同名 unit 认领停止证明。
  `admission_proven`、`real_e3_accepted`、`production_supported` 始终 false。

## 验证与证据分类

最终命令：

```sh
python3 -m unittest discover -s tests -p 'test_e3_quota_*.py' -v
```

结果：**25 项测试方法通过、0 跳过、退出码 0**，包括 10 项 native ABI 测试及 15 项新增组件测试。
此前 14 项组件测试的初次通过日志也保留；最终结果来自增加跨组件和管道/时钟负例后的新运行。

| 证据 | 实际证明范围 |
| --- | --- |
| 固定 manifest / JSON / 身份漂移 / 调用顺序负例 | LOGIC_ONLY 配置与协议判定；拒绝错代次、错根、错 FS/project/额度/ABI、重复字段和虚假支持声明 |
| 排队启动、未退出进程树、采集器、错 boot/InvocationID、恢复和超时 | LOGIC_ONLY manager 事实；证明判定拒绝不完整证据，不证明 OS 已实施约束 |
| 真实匿名 pipe 保持 writer、分片、EOF、阻塞 FD/普通文件/FD 更换负例 | 本地真实有限管道读取；持有 writer 不导致等待 EOF，不能替代 GX10 或阻塞存储测试 |
| native emitter → monitor 联合验证 | 已编译 C 的 ext4/XFS/成功非零 errno/EPERM/close 失败回包与新核心一致；quota syscall 使用独立 shim，仍为 LOGIC_ONLY |
| 未链接 shim 的 native 负例 | 无 FD、额外参数、输出失败；没有触发真实 quota syscall |

真实 quota syscall **0**；systemd 启动 **0**。没有改账户、挂载、配额、权限或服务。
没有执行完整源码/安装/CI 验证，本报告不借用旧候选的全量结果。
原始 syscall 失败信息保留在接收的字节中，不用通用失败码覆盖证据。

## 私有证据包

文件：`infra-local-hand-e3-quota-monitor-ec2fac0-evidence-20260923.zip`

- ZIP SHA-256：`6868d28de89c88fa4c674c2cb2aef139b431d371a89abb06c76848baa08ae5a6`
- 大小：5,487 bytes；成员：11，含 `MANIFEST.json`。
- MANIFEST SHA-256：`d8ca2a9e2c401c2366deecaf448d3f6e8e2617c85cfe0b4cb7608bdc8b17e005`
- 已核验 CRC、成员唯一性、准确成员集和逐成员字节数/SHA-256；外置 seal 独立保存。
- 内容为准确源码/基线身份、源文件摘要、环境/编译器信息与两轮命令 stdout/stderr/退出码。
  Git 源码不重复打包；没有主机实测或完整编译依赖封存的新增声明。

## 尚未完成与下一步

manifest 摘要匹配不是来源认证或 OS 准入；当前代码没有保护配置读取、真实 FS UUID/准确 ext4 类型/
namespace 校验，也没有固定根打开器。内部 `UnitObservation` 只能由将来的受信 manager adapter 提供，
不能取自客户端或 query 回包。`Decision` 是历史观察结果，不能据此释放 UNKNOWN 占用或启动作业。

下一步仍是 Q1 的可审阅受监督装配：在 query unit 内打开固定根并交付 FD 3，绑定受保护安装/配置，
实施最小管理能力和 syscall 限制，接上实际 systemd/cgroup 观察、原启动意图及未知状态保留。
listener 不得先打开可能阻塞的目标根；不得假设 systemd-run 会替代任意 FD 交付机制。
完整 peer 鉴权/持久防重/普通 bootstrap 消费仍属 Q2，真实三单元正常链属 Q3，故障链属 Q4。

Q1 实机验证和整体 E3 仍 **BLOCKED**，准确主机输入仍 **NOT_PREPARED**。
现有盘点已结束；待具体代码与装配影响清单齐备，再交接专用测试环境，不重复当前 GX10 库存查询。
本次不授权或执行 GX10 安装/切换、真实 NAS、E4–E6，也不改变生产资格封堵。
