# 一次新维护与原核心的接线

**PROPOSED / Gate OPEN / NOT APPROVED**，`LH-Q2-CORE-USAGE-CONTINUATION-v1`。
依[需求](REQUIREMENTS.md)。保持现有组件职责和普通退出计量修复，不引入新服务或后台进程。

## 旧本地失败作为独立保留来源

旧09c只有本地预检返回，不加入十一代已消费维护的五文件集合。用一个固定、私有只读
归档保留六份原返回、原 `freeze-complete.json`、`execution-result.json` 与失败终态
`release-gate.json`，共九件，归档≤131072 B。原文件继续原地保留。
六文件最小索引先与原 execution-result 的 bytes/SHA 和真实原件核对，再随获准记录发布；
其余归档内容与索引保持私有。

准入严格验证：原 D=5db76ed，原 A/C/范围、freeze 摘要与五份冻结脚本摘要、六返回
原始字节及其索引、预检状态/退出/原因/空诊断、SSH0/marker false、execute0、核心未
发行和失败终态一致。旧调用器不被导入执行，不把旧 CI 或旧最后有效用量当成新窗口证据。
独立验收者核对相同保留来源与归档固定身份，不以自报终态或摘要代替原件。

归档使用已有受保护输入读取规则，父进程持续持有一个 FD；解析有界且禁止链接、重复
成员、额外成员及超界内容。不重新打开已交给 custodian 的55件旧维护原件。
原55件仍由同一已批准 custodian 持有；九件本地返回不改变其固定55件协议。

## 输入、结果和独立消费者

维护来源固定新 UC A/C/准确 D、新 session10a、完整十一代维护 history，以及独立的
旧09c本地失败来源摘要。保留原无损 resume 引用与全部历史原文。
manifest、receipt、preflight、transition、reconciliation、host-capacity 和 approved-input
只为新 UC 的来源/成本与本地失败保留做精确版本演进；旧版本的解析与事实保持不变，
不把旧09c当作新的已消费维护成功 profile。

具体采用 manifest/receipt v14、preflight v13、transition v13、reconciliation 与
historical-capacity-obligations v17、host-capacity-condition v16；guest input/report 仍为
v4。resume 在完整十一代 `previous_maintenance` 外加入独立 `previous_local_preflight`
固定记录，包含旧 scope/session/D、六返回索引及原终态，不包含机器元数据或原文。
短 preflight 仍只引用完整 resume 的 SHA-256。私有归档的固定来源摘要进入完整输入绑定，
受原 source-binding 摘要和不可变 caller freeze 约束，不接受执行时任意更换。

维护 producer、portable prior/approved-input consumer、独立 dispatcher 必须同步：
拒绝缺少旧本地失败保留、错来源/成本/归档、混用新旧版本、只有 receipt 没有顶层完成、
custodian 收尾不完整及伪造的自报成功。私有两个调用器冻结完整新 D/来源；旧调用器不改。
每个错误的已有 diagnostic 在原始返回及摘要中保持完整，失败时不另采证据。

UC2 仍由原 preflight→同窗 execute 控制流执行，维护正常结束后原独立验证器检查完整
五原件及实际 coordinator completion，再允许 UC3 生成原核心包。业务流程不改变。

## 有界生命周期与兼容

增加一份私有归档最多多持有一个父 FD。根据现有布局，维护交接前122、交接及临时读取
保守上界128、交接后含原20余量89；custodian仍≤64。核心准备原124上界加一为125。
这些是静态设计上界，必须在 UC1 用真实128限额验证完整启动/输出/退出生命周期；失败
则在原上限内修正，不用现场试错。不提高128，不增加另一个 helper，不释放旧证据身份。

重新核算所有准确来源和完整返回形状：host/guest≤98304 B，custodian≤16384 B，
marker/receipt/描述/transition≤65536 B，压缩 bundle≤49152 B，展开≤393216 B，
argv≤65536 B，短 preflight≤4096 B，approved-input≤1048576 B，核心包≤33550320 B。
若源码体积需要调整，只在现有来源模块间等价整理；全部 consumer 的来源集合和摘要同步，
不得省略检查、历史或诊断字段。准确新形状验收之前不冻结、不发行。

原单窗限额和十三代加核心成本底线按需求接入全部生成/消费端。旧失败不退款，费用不跨
窗口伪合并成一次成功。未知仍停止；无重试、补采、清理、恢复或其它回退路径。

## 仍待验证的风险

原现场具体原因未知，新普通退出修复可能没有覆盖它；新 preflight 如再失败必须保留
具体诊断并停止。新增一个输入 FD 的最坏峰值达到128，必须在 UC1 证明余量布局真实可行。
只有这些离线前置通过以及新现场完整成功，才可能取得原核心验收结果。
