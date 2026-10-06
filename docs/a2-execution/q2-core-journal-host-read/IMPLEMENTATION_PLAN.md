# Journal 维护宿主读取修订实施计划

状态 **PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-JOURNAL-HOST-READ-v1`，仅 R1–R3。
依[需求](REQUIREMENTS.md)和[架构](ARCHITECTURE.md)，保留原 journal A、C 和所有历史失败。

## 准确批准顺序

先提交三文档形成准确 A，再登记 SHA、tree 和三文档 digest。没有 Owner B 前只允许文档、
既有代码的只读检查及隔离验证；不得实现新 root observer、新读取路径或建立替代现场窗口。
Owner 必须明确接受固定内核普通读取、只读 root observer 的新增信任/管理副作用和一次替代窗口。
随后独立 bookkeeping-only CLOSED C；实现不得与 C squash。

## R1 窄实现

仅接通已有 host 内核资格读取组件、固定只读 writer 子进程、计数/预算/证据及一次替代窗口规则。
不修改生产、核心业务 harness、sudoers、系统服务、权限或虚拟机配置。
两个原维护实现文件上限仍各 65536 B；新增 source manifest 成员只是既有内核读取模块。
不能把实现膨胀或权限不可用解释为原批准可以自动扩大。

## R2 隔离验证和冻结

继续现有七文件窄测试及通常 CI，新增以下必要验证；不借用原 VM 或原镜像作合成测试：

- 真实普通账号固定内核读取：通过严格资格或如实 BLOCKED；证据文件仍拒绝弱读。
- 非 procfs、子挂载、路径/对象替换、未知 ABI、缺失 boot、错误/未来起点、host 重启均拒绝。
- root payload 篡改、非固定目标/schema/代码/期限、额外字段、错误 UID、未知 proc 可见性均拒绝。
- helper 不包含任意文件内容读取、写入、信号、网络或动态 import 用户源码；原 scanner 的完整性条件不削弱。
- mock/合成跨 UID 不可读、PID/FD drift、额外 writer、sudo 失败、长度/时间/预算上限及原八个检查点次数。
- 保留原生 pidfd 与合成 qcow2/ext4 实测；保留每个维护步骤失败停止及源文件上限检查。
- 无关全量测试不重复运行；各真实与 mock 结果分别记录，SKIP 不能升级为 PASS。

固定干净 D，审阅完整 root payload/静态 argv、现有解释器与 sudo 文件身份、所有原输入 pins。
只在新 D 的相关 CI 成功后进入 R3；诊断提交的本地 313 PASS 或原 D CI 不替代新 D 验证。
现有 sudo 实际准入只在下面第一次固定只读观察验证，不增加一条现场 sudo 探测。

## R3 一次替代预检和条件维护

以原 session 开始一次新 900s 窗口；先固定内核读取、原输入/VM/工具/容量检查和一次 root writer 观察。
完整 manifest 在同一窗口复核后才可执行，任何原目标输出存在都拒绝。
这不是重放旧业务或已消费维护。marker 前失败保留失败窗口且停止，不能自动再开预检。

仅全部门通过后沿用原单次 J3：一个 marker、两个固定 SSH、正常关机、完整离线备份、
一次镜像增长、一次启动、一次 ext4 增长及前后内容/容量回收；其它原 A 条件全部保持。
不强杀 mutator、不清理、不退款、不补采、不回滚、不启动第二实例。

交付真实状态、root 调用次数/计量、marker/SSH/修改计数、旧失败与新窗口关系、准确 D 和 receipt。
现场失败就列出首个失败及已修改对象，不用下一批名字继续。
H01/Q4/H11 始终为零，后续核心验收需原规则下的独立准确授权；支线及生产 E3 限制不变。
