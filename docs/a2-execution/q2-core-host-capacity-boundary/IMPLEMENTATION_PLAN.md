# 核心单次验收：host 容量边界实施方案

- Authority：Owner；状态 **PROPOSED / Gate OPEN / NOT APPROVED**。
- Scope：`LH-Q2-CORE-HOST-CAPACITY-BOUNDARY-v1`，B1–B3；原 R 和具体差异见 [需求](REQUIREMENTS.md)。
- 准确三文档 A → Owner B → 独立 bookkeeping C → D；批准前仅文档、只读审查与既有代码验证。
- 沿用原 N1–N3 的批次和一次执行权，无新日期、marker、unit、安装目录、project ID 或任务种类。

## B1：收敛 host 条件及报告

1. 在既有 `q2_core_delivery_contract.py` 登记本准确 A/B/C 常量；
   `q2_core_delivery_freeze.py` 将本闭合链加入原全部闭合链核对，不修改旧权威文档或旧 C。
   正常准入和 release 还须绑定含该修订的准确 D；仅文档批准不允许打开 release allowlist。
2. 在既有 `q2_core_prior_attempt.py` / `q2_core_delivery_entry.py` 接入架构定义的固定双 core 容量条件。
   保留旧五原件读取、canonical 摘要和 writer/anchor 重验；一次有界 `fstatvfs` 的结果必须实际保存并消费。
   消除当前 `verify_prior_originals` 调用 floor 后丢弃结果的接线缺口；可调整私有 helper 返回接口，
   但不引入 caller 可替换预算、枚举任意目录或忽略未知值的开关。
3. 在原 pre-marker 校验链中要求真实容量条件通过；失败时不创建 marker，不发 carrier。
   原 admission/absences/ARG_MAX/package/credential/source/deadline 条件继续全部成立。
   不修改 `q2_core_delivery_bootstrap.py`、dispatcher、loader 或 guest schema 来绕开 host 缺口。
4. 同一 live 返回增加 `host_capacity_condition`，按架构 exact shape 校验并绑定原调用，
   始终披露历史 UNKNOWN、完整历史准入 false、排他预留 false、零释放；不能复用其它 caller 的成功观察。
   原 capture_accounting、receipt/capture manifest 和六文件写入、分配采样、fsync、回读规则保持。
   不写第七个文件，也不新增退出后的成功推导器。

必要回归只覆盖实际风险：

- 134217728 B/32 inode 恰好通过，任一少 1 拒绝；未知/负值/无效分配单元拒绝。
- held anchor/writer/设备或双钟变化、读取失败、晚返回仍拒绝且 marker/request 次数为 0。
- 旧五原件缺失/摘要或关系不符、guest 历史计费不完整，不受本修订影响。
- 容量说明不能由 caller 自报、不能丢弃，不能把历史 null 变 0、把 false 改 true 或无本 A/B/C 发行。
- 使用真实 package builder/parser 贯穿入口；身份与资源观察的替身明确标为 fixture，不冒充现场通过。
- 验证原六文件应用/分配限制与 ENOSPC/IO 失败路径；不要求失败时一定还能写出完整 receipt。

## B2：准确 D 的发行前验证

实施后先定向回归及接口交叉核查，再冻结准确 D，完成全源码、独立 installed verifier 和准确 SHA 的 CI。
所有新旧 release 条件齐全前 allowlist 保持空。原现场 wheel 不被测试 wheel 替换。
本地 Codex 在实际私有环境复用既有来源；不再要求重新搜索已找到的 44 份文件或重采 K4/R3。
实际执行必须从新的同一原 900 秒 caller 开始取得 held writer/anchor/原件；
两次独立 build/parse 与准确 D/release 静态核对后，在原 pre-marker 位置取得本次容量观察，
连同所有本地输出 absence 和其余 gate 全部通过后才可创建原新批次 marker。
结束的离线 caller 不可复用；不能创建 marker 后才补授权、容量或 source 校验。

## B3：完成原核心单次验收

由掌握实际管理入口的本地 Codex 执行既有一次 `lhqcore20261005a-carrier.service`。
仍先在该 carrier 内核对旧 scope，再安装/执行 H01；只有前案 semantic PASS 才继续 Q4 和 H11。
失败立即按原规则停止并保留，不追加现场轮次。成功报告必须分别列出 H01 结果、Q4 取消、H11 恢复、
新批次退出/证据情况、host 容量条件的有限含义，以及旧历史 UNKNOWN；不能用 CI 或包验证替代实机结果。
云端负责可离线完成的实现/审查，本地负责真实来源与单次执行；任何材料或实现失败都报告具体位置。
本步骤结束即报告实际核心结果，不自动开启生产部署或其它支线。
