# 保留旧失败、复用成功启动的接续边界

Authority：Owner；**PROPOSED / Gate OPEN / NOT APPROVED**。
对应[需求](REQUIREMENTS.md)的 GR1–GR4；只修改现有核心接续链，不新增产品接口。

## 原始证据与身份

旧 HR1 freeze 固定 SHA-256
`0d5bb5140b7687dd77714a0ce1f5f30f956e431aadce702e9bc1ab6ba2305d98`；旧独立失败终态
`b602284213c57f1e3a140dff0cfb3b60661d79ba4eadb83ac866722a8182141b`；失败 guest 索引
`7ba15c2645a8ed6d9991189f42a950a086f435815d740ff4314678f86defdc5e`。索引内9件原件须
全部重新验证；19件成功启动原件按原消费者重建。24个旧私有程序和17份受保护来源
保持旧摘要，旧终态继续阻止旧入口。缺失的旧 SSH 子进程退出码不能由新结果补造。

新入口消费旧终态作为明确已失败的历史输入，不删除、覆盖或绕开它。新入口有本批
独立的 create-only 消耗记录和终态；同一入口的再次调用在任何现场动作前拒绝。
成功启动只证明其当时 host/VM 事实，不能证明当前 guest SSH 就绪。

核验仍使用原 SSH prefix、账户、key 和 known_hosts。固定远端来源为现有
`q2_current_guest_verification.py`，6674 B，SHA-256
`fe7591911150090d33db9f2e007da8b3e5aae404d795462161e2435c08b524db`；沿用原六命令、
安装包/quota 目标及严格报告消费，仅新请求 nonce 与新来源绑定在发行前冻结。
无安装、模块加载、服务修改、新诊断命令或等待轮询。使用已修复的 capture 在拒绝
命令前保存实际 child completion、已有流及 EOF；失败仍拒绝，不能因输出存在而放行。

沿用当前 host boot/namespace 及原启动的 PID/starttime/exe/argv；不得只匹配 PID。
六镜像的路径、dev/inode、类型、UID/GID/mode/nlink、父目录和持有句柄保持原严格
规则；可写盘合法 size/time 变化沿用现有策略，原 system 和只读 seed 仍不可变化。
当前 host/VM/对象前后检查不一致即停，不把新观察结果替换为另一个基线。

## 一条数据流

现有 `q2_host_rebind` 增加明确版本的接续证明：activation/v4、host-rebind-source/v2，
保留旧 v1/v2/v3 含义。证据包含完整旧基线、旧 HR1 freeze、原19件启动原件、失败9件
原件/索引/终态、新准确 Owner B/独立 C、新 freeze、新核验原件和实际顶层完成。
新请求不得冒充旧 guest request，新成功不得替换旧失败。历史连续性仍为 UNKNOWN。

`q2_core_prior_attempt`、contract、approved-input、freeze、`q2_journal_growth` 接受
本批新证据版本并核对费用；`q2_core_delivery_dispatcher` 独立重建相同来源、转移和
费用关系。准确发行 pin 只有在完整验证/发布/冻结后更新，旧 pin 不产生新现场权限。
私有接续 caller 使用新目录，引用固定旧原件，预先冻结核验→维护→原核心所有源码。
GR2 后只填写预定数据槽，完整成功才冻结维护输入；不能现场替换程序继续。

旧归档仍是独立固定输入，新证明保留一个持有 FD、单体不超过1 MiB；不重复嵌套旧
大归档。准备检查基于现有原件大小和原成功 guest 字段上界，拟定95个存储成员的
USTAR 上界747520 B；这是离线可行性核算，未写执行归档，也未证明未来实际载体。
GR1 须验证实际完整成员/引用/序列化、生命周期、内存、FD、CPU 和准备池成本。

## 维护与失败责任

原未发行 11c 保持唯一会话和十九份义务；只更新其必要来源/批准/版本绑定，不重放
旧被冻结 caller。维护的正常关机、journal目标、重启、完整 post 和实际协调完成保持。
原 H11 只恢复查询同一任务，不重新执行。新核验失败或维护失败均终止本批并留存；
没有隐含的第二连接、修复重启或其它恢复路线。
