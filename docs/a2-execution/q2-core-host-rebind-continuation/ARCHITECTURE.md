# 单次新基线采用与原核心连接

**PROPOSED / Gate OPEN / NOT APPROVED**；范围与[需求](REQUIREMENTS.md)一致。

## 身份语义和信任边界

不改 HB2 reader/consumer 的历史格式或 `release=False`。HB2 仅证明一次固定观察
完成。新采用是 Owner 对其准确来源中当前六对象的明确决定，不是跨 boot 连续证明。
没有历史 filesystem UUID，故不另开“找当前 UUID”的诊断批次；当前 UUID 不能补造
历史 UUID。旧候选摘要、旧 guest boot 和旧失败始终保持各自历史含义。

新证明使用独立版本 `local-hand-q2-vm-activation/v3`，至少绑定旧 activation 完整
来源、RP2 失败、HB2 原始请求/原件/完成/独立结果、准确 Owner B、固定角色路径和
新基线 metadata、一次启动的原件、新 guest 验证及各 caller 的真实完成。历史原件
可通过原固定归档引用并重新验证，不能只信上游生成的一份摘要或布尔 PASS。
当前采用策略为 `OWNER_ADOPTED_HB2_BASELINE`，明确
`historical_filesystem_continuity=UNKNOWN`、`historical_content_continuity=UNKNOWN`；
旧 PRELAUNCH_ONLY 摘要不升级为当前内容证明，`execution_permission` 不自动变 true。

准备时冻结所有程序、来源、目标和未来数据槽；启动/guest 返回只能填预定数据槽，
独立消费后冻结最终 v3 与维护输入。数据冻结不得替换 caller 或程序字节。若需改代码，
现场批次停止保留；不会“修一下 wrapper”接着跑。

## 一条接续链的责任

| 现有位置 | 最小必要变化 |
|---|---|
| `q2_host_reboot_consumer.consume` | 原版结果保持，离线核验完整 HB2 原件作为新采用的来源 |
| `q2_core_prior_attempt` 的启动/activation 构建与采用 | 新增严格 v3 消费；v1/v2 解析和旧 dev/inode 关系原样保留 |
| 私有 `start-once.py` 及固定 caller | 本地 Codex 适配本批一次启动与准确来源；不覆盖、调用或重放旧 caller |
| `q2_current_guest_verification` | 复用六命令和现有安装/quota 关系，无安装/模块加载/新功能 |
| `q2_core_delivery_dispatcher` | 独立实现 v3 及转移/费用校验，拒绝生成端遗漏来源或扩大权限 |
| `q2_journal_growth`、contract、approved-input、freeze | v3 通过后将新当前身份接到原严格校验及一次新维护，再接原07a |

不部署新的 scanner、observer 平台或 UUID 服务，不改产品功能。VM 启动器和私有载体
不在公开源码内，云端合成测试不能替代它们的本地验证与真实完成。

## 启动前后各检查什么

启动前在原正常用户视图内，host boot 和 pid/mnt/net namespace 必须等于 HB2。
六文件完整 metadata 与基线相等、互不别名，逐层父目录受保护，无跟随，打开句柄
与路径复核相等。保留原旧 PID/pidfile 缺失及原端口空闲的**临启动**固定检查；HB2
早先的 ABSENT 不代替它。不枚举其它 PID/端口，不停占用者，遇冲突即停。
工具保持 HB2/原可信来源身份。启动前记录与 launch 记录应绑定同一持有集。

一次原配置启动只改变新 pidfile/serial 输出槽，完整 argv 与原配置派生关系必须
独立重建。新 VM 的 PID/starttime/exe/argv/namespace、host boot、启动顶层完成、
双 EOF、监听与新 pidfile 必须一致。不能拿旧 PID、旧 starttime 或启动命令退出0
代替新 VM 身份。控制命令与等待有界，启动失败不自动二次尝试或清理输出。

启动后可写 system/quota/journal/evidence 的 size/time 可因合法 guest 写入改变，
但 dev/inode、类型、属主、权限、父目录和路径/句柄身份仍严格；original_system 和
只读 seed 不允许更改。不要错误地要求可写盘启动后仍等于启动前所有 metadata。
serial 沿用已验证的有界输出与监督，不引入无界追加文件。

guest 只用现有六检查核验 boot、kernel、准确模块包与完整性、模块对应、quota UUID/
fstype/options。保持原 SSH host-key 校验，不刷新信任。guest 前后绑定同一新 host/VM
和六镜像当前身份；实际完成、EOF、来源、nonce 和预算齐全才能形成 v3。

## 维护、核心和失败

`check_activation_host_boot`、`ImageSet`、`freeze_vm` 的严格等式及 recheck 继续
作用于已经批准并验证的新 v3 身份，不能用忽略 dev、只比 inode 或修改旧 activation
的方式通过。维护产生的下一 guest boot 仍通过完整 pre/post 证明接到原 H01/Q4/H11。

旧两归档保留，新增证明用单独有界 sidecar；明确成员数、引用覆盖、总序列化大小和
全部持续持有 FD，不把旧大归档多次嵌套复制。新 sidecar 单体仍不超过现有1 MiB边界；
超界只在 HR1 内压缩重复表示，原件覆盖与消费者验证不得削减。

除明确保留的历史文件系统/内容连续性 UNKNOWN 外，任一必要执行事实未知、漂移、
超限、截断或缺实际顶层完成，后续阶段均 NOT_RUN。保留新调用
已消费/未消费事实、旧18份和新第19份义务；任何失败不恢复已使用的窗口。
