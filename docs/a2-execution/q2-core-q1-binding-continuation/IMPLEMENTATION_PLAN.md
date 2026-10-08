# 补齐一条来源关联，完成原核心接续

Authority：Owner。**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-Q1-BINDING-CONTINUATION-v1`，QI1–QI3。
输入提交 `5d8e5db79ebd137716145a60e71e85fe0252fe1d`；依本目录
[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)。本提案不执行程序或现场动作。

## QI1：一次完成两侧接线及验证

1. 三文档形成准确 A，Owner 对来源采用边界、QI1–QI3 和限定披露作出决定 B；
   独立 C 登记准确 R/A/B，随后 D 才实现。范围内不逐子步骤重复审批。
2. 本地复用已经找到的 C10 原件、单单元查询原响应/执行记录/原私有索引、已生成的
   声明候选和 08d 五件原件。按架构固定输入 pin，核对已存在的索引和载体关系；
   不重找归档，不访问 guest，也不把候选自身重新散列当作来源证明。云端不填造
   私有名字、路径或摘要。本步骤只读既有私料；未能固定准确来源即停止发布可执行候选。
3. 仅在 `q2_journal_growth.py` 的 `freeze_growth_inputs` 及相邻纯变换接入固定
   Q1 来源：先重现旧清单，再验证 C10 与当前捕获的关联，派生一个精确服务及父域，
   一并写入 inventory/source binding。既有受保护 reader 扩展到这组固定输入，
   在冻结、预检及消费前复核同 FD、元数据和字节。原 GuestInventory 直接引用、
   quiet、domain/cgroup、启动边、writer 和数据检查保持，不添加现场查询或通用解析平台。
4. `q2_core_prior_attempt.py` 保留六旧 profile，新增准确 GS/08d 第七 profile，
   按旧 manifest/receipt v8、guest v2、原 guest assurance、六代嵌套 resume 和
   原 R/A/C/D 验证其失败。不能沿旧 v1 分支误读 08d，不能补造远端退出或原件。
   维护 manifest/receipt v9、preflight v8、transition v8 以及新 session 同步更新；
   guest descriptor/report 保持 v2。来源绑定与准确 inventory 贯穿消费前和核心发行核对。
5. `q2_core_delivery_contract.py`、freezer、approved-input、package/entry、独立
   dispatcher/bootstrap 和返回消费者同步接入七旧历史、八代费用、新 R/A/C/D 与
   transition。reconciliation/history v12、host-capacity v11；dispatcher 摘要按
   实际源码固定。runtime/wheel/loader、安装、SSH 身份和 H01/Q4/H11 任务语义保持。
   旧 35 件、28 个缺席名、新九名及跨集合 inode 去重/原检查均保留。
6. 完成下列针对性验证和真实保留输入的离线核对，再发布准确 D、核对 D 自身 CI 及
   既有独立安装验证。先验证两侧完整接线、原大小及资源上限，再冻结同一 D 的维护
   caller 和条件核心 caller；此时仍不发行真实核心包，不重装现场。

| 风险 | 必须得到的结果 |
| --- | --- |
| 来源错配 | C10/当前响应 pin、runtime/manifest 配对、票据规范编码、七项身份、同配置父域/source/boot 任一漂移、重复或歧义都拒绝 |
| 多加或少加声明 | 真实旧 18/6/6 只增为 19/7/7；服务 cgroup 非 null；同名/同路径冲突、额外增量、删除旧行、改保护根均拒绝 |
| 借声明跳过检查 | 准确静止服务走原验证；同前缀另一服务仍拒绝；活跃、有启动边、域/cgroup 不满足、writer/持久证据异常仍拒绝 |
| 历史混用 | 08d 保持失败、空动作及 UNKNOWN；35 原件、嵌套历史或费用改动即使重算摘要也拒绝；旧 caller 不可重放 |
| 只修维护未接核心 | 完整合成维护成功能构造并独立验证原 H01/Q4/H11 输入；来源/清单/boot/authority 漂移或维护不完整时不发行核心包 |
| 大小及平台兼容 | 实际私料及最大计量/20 位钟下短预检≤4096 B、transition≤65536 B、输入≤1 MiB、包≤32 MiB、两源各≤98304 B、bundle≤49152/393216 B；纯投影验证不导入 Linux runtime |

上述测试使用合成或现有保留载体；不为写测试而重新访问机器。可以复用未改部分的
既有证据，避免机械重跑无关历史。新候选的首次失败及环境跳过如实保留。

## QI2：一次 08e 维护

执行者确认既有 host/guest 管理前提仍成立后，复用原环境执行
`lhqjgrow-20261008e`。普通预检成功后，在同原点、nonce、manifest 及累计计量下
execute。原静止/关机、旧 pidfd 退出、完整备份、journal 256→512 MiB、比较、
一次原配置启动、ext4/UUID/内容和五池容量全部验证后才可 VERIFIED。
新窗口开始即消费；原 900/780 秒及最多两次固定 SSH 等限制保持。
失败 STOP_AND_RETAIN，保留 UNKNOWN，不重试、补采、清理、恢复、回滚或另开窗口。

## QI3：同一 D 接原核心批

QI2 完整成功后，host 保护读取并验证新八件成功原件和七旧历史，构造严格
transition，发行原未发出的 `lhqcore-20261007a`。独立 guest 核对投影、来源、
boot 与准入后，原 live finalizer 执行 H01 正常任务和结果 → Q4 运行取消 →
H11 同任务恢复查询。原独立 900/800/750 秒及全部单次边界保持；对象已有即停止。
交付实际三个 case verdict；维护不完整则 QI3 NOT_RUN，不能以 CI 或静态解析代替。
本次批准不自动产生下一窗口，不交付其它产品功能。
