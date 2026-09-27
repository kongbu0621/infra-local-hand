# Q2 安装未来义务对账 Owner 决定

- Decision authority / speaker：Owner，本会话用户。
- Record event ID：`LH-Q2-INSTALLATION-RECONCILIATION-CLOSURE-20260927-01`，仓库登记标识，不冒充平台消息 ID。
- Decision submission time：`2026-09-27T18:02:37+08:00`，本会话提供的消息时间。
- Source：Owner 对紧接在前的准确方案批准请求的直接答复。
- Stable retained reference：本文件在独立 CLOSED 登记 C 中的决定副本；准确 C 由 Git history 定位。
- R：`10d2a5c827964989f41ca6e8eeac3d44de6d0f04`。
- A：`c65ff4e25ea6373aabf8db25d304ee7614b96eb5`。
- Scope：`LH-Q2-INSTALLATION-RESERVATION-RECONCILIATION-v1`。

## 准确决定及其请求上下文

紧接在前的助手请求引用了[已经提交的准确基线登记](https://github.com/kongbu0621/infra-local-hand/blob/73765c22ed9cdcdf22eb9fef27cdd8f69aaf9e59/docs/governance/Q2_INSTALLATION_RESERVATION_RECONCILIATION_BASELINE.md)，
该登记固定完整 R/A、三文档摘要及三个相互绑定的待决事项。与此次决定相关的
请求原文为：

> 方案明确了两份原件的有限采用、五项访问时间偏差，以及两项旧安装预留的未用余额处理。实际文件、总额度和唯一运行窗口保持不变。
>
> 因为涉及新增证据采用与计费规则，仓库 `AGENTS.md` 引用的 SOP 要求对准确方案批准。现在只需回复：
>
> **“按原 R，批准 A c65ff4e2 的对账方案，继续实施。”**

Owner 完整原文：

> 按原 R，批准 A c65ff4e2 的对账方案，继续实施

此决定明确批准上述准确 R/A 和 scope，关闭该有限范围 Gate。短 SHA 唯一指向
已经提交的完整 A；“原 R”由此前请求所链接登记与根 AGENTS.md 固定。它不授予
新的额外运行批次，不追认旧来源字节或旧 INCOMPLETE 为成功。

## 获批范围与保留限制

允许在独立 C 后按 A 的 P1–P6 实现、验证和交付专用对账合同、来源/计费适配、
追加记录与 driver。准确两份当前 raw 仅作前瞻来源；610 项准确当前基线仅作后续
保持性比较，五项 atime 偏差永久披露，不恢复时间、不弱化之后的保护性读取。
原十二个历史树与十五个旧文件仍依旧锚证明，原件及所有旧失败结果保留。

仅原 192 MiB/8192 inode 和第二独立 64 MiB/4096 inode 安装目标的未消费未来
余额可按准确目标逐维 `max(0,C−A)` 追加终止。实际对象全计，其他费用与承诺
不减少；恢复的同额声明与第一项去重。新增五文件和一目录的 state 子预算最多
1 MiB/16 inode，含实际块及部分材料，计入原总上限。

完整联合现场鉴证和 before/after 账单必须在首次新持久写入前完成，发行前重新
核验；每次现场探测都计入原唯一 300 秒窗口，准备总阶段仍为 140 秒。缺项、
来源/元数据漂移、实例或配置变化、容量不足、期限不足均停止并保留材料。
对账 seal 本身不代表发行或 Q2 接纳，不允许删除换身份或重开窗口。

仍服务于 startup A `47b351b2b943bf1d6f1c71cfeb031157a2eb70cc`、C
`d4a925c883672fadc7d1b10a8dfe58df18b922cd` 的唯一未发行批次。runtime commit
`b49d3df3d1e76813faf08e59ab4975e25279c2fc`、tree
`2d957ccf1d9cbdf5e538189c6b68d56f34590a42`、wheel SHA-256
`c077a8f8aa2f0c3147228602746fd459a6d13267df299a84835331ad35ef158b` 不变。
完整准入通过后才进入同一批次的原安装、装配、一次发行和独立停止/流/封存检查。
不包含额外批次、扩额、改 quota/账户/挂载/能力、依赖、Q3、H06–H13、production、
GX10、真实 NAS 或 E4–E6。

范围内继续实施，不再逐项请求批准。实质范围变化仍遵守固定 R 的变更规则。
本 C 仅登记决定及 CLOSED，未改 A 三文档或新增 source/test/prototype/运行配置。
实现 D 必须以此独立 C 为祖先，禁止把 C 与 D squash 为同一提交。
