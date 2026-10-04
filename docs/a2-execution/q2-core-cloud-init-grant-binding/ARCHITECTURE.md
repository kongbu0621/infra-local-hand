# Local Hand 固定 cloud init 授权绑定修订架构

- Authority：Owner。状态：DRAFT / Gate OPEN / NOT APPROVED。
- Scope 与 R、固定版本及边界见 [需求](REQUIREMENTS.md)。

## 输入到当前验收的责任分离

现有 host held-source reader 仍负责固定文件、whole-file SHA、身份、权限和 NOATIME。
`q2_core_policy_basis.py` 只对该已固定 raw 做有界结构投影，确认唯一 users/name/sudo mapping，
再生成原 canonical sudo grant。它不执行 cloud-init、解析一般 YAML 或观察 guest。

`q2_core_approved_inputs.py` 的 source-aware 验证独立核对 raw 投影和原机读谓词，
不能只相信 builder 的成功标志或已生成摘要。source-less parser 仍仅验证固定机读关系，
不能声称它读过私有 raw。host 当前绑定再次逐字核对这三项 policy source。

原 guest dispatcher 不从当前 sudo 输出反填批准输入。它继续要求原 current held sudoers grant、
唯一 bounded semantic helper、HELLO、账号和程序身份交叉绑定；归一化不替代任何当前事实。
host finalizer 保留原严格结果/证据验收。不存在新的服务、进程、依赖或现场探针。

## 数据和版本边界

固定 source SHA 与全部原 policy keyset、canonical grant 值、helper argv 和预算不变。
仅需求所列两个字段的来源解释由“raw 全行”改为“同一 cloud-init mapping 的规范投影”。
所有旧 authority records 保留，不升级旧包为已通过，旧结果也不转为新验收。
没有新 field module、runtime candidate、wheel、package/member 或 capture 文件。

离线 freezer 增加本修订准确 A/B/C→D 祖先/文档/决定核对，同时保留原三条 amendment 与原核心 closure。
最终 manifest.implementation 绑定实际 D；原 manifest.amendment 和 completion_adjustment descriptor
仍各指其原批准，不能改成新 A。本修订 authority 由离线 source closure 验证，不添 wire descriptor。

## 失败和信任界

错误摘要先拒绝；随后拒绝重复或歧义结构，不以宽松 substring 搜索、默认账号或猜测 YAML 语义通过。
只证明固定 source 表达的预期权限；不宣称配置已实际应用或现场权限安全性已证明。
原治理接受的 JIT 自观察、source horizon 和 single writer 限制保持。
OPEN 时不实现该转换；批准后仍须独立 C 在 D 之前。包/审查任一失败保持 release allowlist 空，
不运行 carrier，不通过修改现场配置使旧假设成立。
