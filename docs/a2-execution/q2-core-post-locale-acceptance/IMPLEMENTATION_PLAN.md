# locale 修复后单次核心验收实施方案

Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-POST-LOCALE-ACCEPTANCE-v1`，仅 L1–L3；遵守[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)。
先三文档准确 A → Owner 逐字 B → 独立 bookkeeping-only CLOSED C → 实现 D；不 squash C/D，批准前不写新源码、测试、fixture 或执行 scaffold。

## L1 接齐一次核心验收的必要增量

1. 使用固定 Git 历史审查三旧 pre-business 路径，核对十五核心原件和四诊断原件的本地读取/关联条件。
   不扫描其它历史资料，不要求 Owner 重找已有材料，不重新取得配置、重放私有文法解析或连接现场。
2. 在 `q2_core_delivery_contract.py`、freezer、package 独立解析、entry 和 field 中接需求新身份、新 R/A/B/C 与已批准 locale 链；保留所有历史批准。
   loader 不变，bootstrap 仅等长身份替换；先核算 field 尺寸，超 cap 即停，不删校验或增额。
3. `q2_core_prior_attempt.py` 与 `q2_core_approved_inputs.py` 接三固定 profile、诊断 metadata-only 保留，落实 reconciliation/v4、obligations/v4。
   独立 guest 消费者同步严格规则；诊断原文不进入 approved-input/包。原 approved-input 1 MiB、总 input 32 MiB 保持。
4. dispatcher 接固定六 SHOW 槽、三个同时 held observer、三承诺逐设备累加与条件 4 GiB/512 核心上界；helper usage 归 carrier、quota native count 不变。
   `_admit_sshd_source` 及既有纯依赖与 d0c8749 逐字保持；sudo、五有效 sshd 谓词、key/rc、原安装与三 case 逻辑不扩张。
5. entry/finalizer 与独立 host consumer 接 260 MiB/72 五行容量及诊断摘要绑定；六文件/82输出和 UNKNOWN/不退款不变。
   缺当前来源或返回证据时如实拒绝；release allowlist 在 L2 完成前保持空。

## L2 准确版本和完整私料验证

定向回归覆盖本次增量：

- 三原件 profile 各自成功及串用错误；缺件、错误 hash/长度、额外 frame、旧 truth/包/manifest 篡改均拒绝。
- 三旧任一 A/B active、populated、boot/Invocation/父链/inode 漂移、缺属性/超时即停止；失败槽不得重入；不漏第三旧，不把三个记录复制成通过。
- 三旧全额承诺与更早 guest 义务；诊断固定四 hash/receipt 绑定、不含配置原文；保留 4 MiB/8，未监督/usage UNKNOWN 不改成功或 0。
- 五行容量不足、遗漏诊断、旧低阈值、时钟/设备/摘要不符拒绝；没有排他预留和整机峰值误报。
- 新旧全部身份/21 projects/派生 unit 不冲突；对象存在时停止不换名；六 SHOW 有界且不增加 carrier 次数。
- 原 host builder/parser→HELLO/BIND→guest parser→marker 回构和 result/finalizer；保留此前 writer、basename、sudo 来源/TAB、locale 严格边界与五有效谓词回归。
- 合成 H01/Q4/H11 验证原语义；不把测试替身当作现场。证明文法纯函数/依赖未改变，不重复已保存快照的 G3。

冻结干净准确 D 后完成定向、完整 source、独立 installed verifier、准确 SHA 的 CI；如实保留失败和 skip，不替换原现场 wheel。
本地复用原私料、十五核心/四诊断原件及原 source-aware horizon/locator/policy，完成两套独立内存构包/解析。
确认诊断 raw 未入包、全部 source 和批准链准确、field/输入/输出/资源界限成立；记录包/manifest 摘要及长度，不声称已取得 guest 当前状态。
前期只读构包 caller 结束后不可复用其 writer/window。不得执行旧捕获器/历史解析器、创建 marker 或试连以“预验”。

上述全部通过后，单独提交仅准确已审 dispatcher digest 的发行登记，不同时改变 field bytes。
最终发行 D 的完整 source、installed、CI 和真实私料双构包仍需按原规则验证；失败关闭发行、不进入 L3。
源版本、输入关系、预算或必需语义出现范围外变化，按 R 停止受影响范围，不临场修改合同或放宽校验。

## L3 条件单次现场和交付

只有准确 B/C、L1/L2 全部通过，才由本地执行者使用原管理入口开始正式 caller 的原 900s 双钟窗口。
同一窗口重验 held anchor/writer/管理源、十九原件、两套构包、260 MiB/72 和六名 absence；版本、来源或保护不一致时 marker/request 均不得创建。
窗口不能刷新；marker 创建即消费，即使随后没有连接。至多一次 O_EXCL marker、一次固定 05c carrier，不独立 probe、不追加诊断连接。
唯一 carrier 执行原当前策略/身份检查、三旧静止与容量/对象准入后，才 create-only 安装，按 H01→Q4→H11 顺序进行。
H11 用自身原 ledger/unit，不启动第二份业务或改 deadline；原执行输出、退出、完整证据、用量与 live finalizer 必须全部验证。

交付准确 D/tree/包摘要、marker/request 是否消费、三个 verdict 或 NOT_RUN、真实任务与结果回收真值、旧 UNKNOWN、资源与停止原因。
传输失败证据回收不等于业务结果回收；原 live finalizer 未完成或证据不足不得记 PASS。
失败、断连、UNKNOWN 即结束本范围，保留六文件已取得子集及所有旧对象；不重试、不重连、不补采、不清理、不退款。
成功也仅关闭本次隔离验收，不启用生产 E3、不扩展 E4–E6/NAS，不恢复 namespace/watchdog 支线。

本轮准备只交付提案 A 和 OPEN 登记。准确 Owner 决定前，没有新的现场请求额度，也没有本范围实现 D 或可发行包。
