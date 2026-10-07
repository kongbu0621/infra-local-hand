# K1 最小核心接续实现与验证

范围 `LH-Q2-CORE-MINIMAL-CONTINUATION-v1`，准确 A
`5d6cefa602e9146f02887ebfaa4b0cad4e376ff2`，独立 C
`8a4c24cefe4abbab193577b2dff48fc49626cae4`；R、Owner B 见治理记录。
三份 A 文档保持原字节；本实现承接独立 C。

## 已实现差异

维护入口移除全宿主 PID/TID/FD/maps writer 扫描、八个观察点、root/TTY 认证及旧
writer 交接。保留目标 QEMU pidfd/start/argv、五镜像身份、guest 静止、正常关机与旧 VM
退出、正常 qemu-img 锁、独立完整备份、镜像/内容比较、一次原配置启动、ext4/内容/容量核验。
新 manifest/receipt v2 明示可信单管理员前提、host writer 未观察且未证明持续排他。
普通 preflight/v1 交接绑定准确 D/manifest/nonce/host boot/原双钟及累计 CPU、峰值 RSS。

维护固定八原件完整交叉核验后生成有界 journal-transition/v1；host BIND、独立 guest
及返回消费者绑定维护前后 boot。增加准确 05c 第四旧批次、四旧八槽固定顺序、07a 固定
身份和全部累计承诺；新 boot 只接受旧 scope 与 cgroup 缺席。历史 UNKNOWN 不改写。
原 loader、runtime/wheel/harness、sudo/sshd 解析和任务权限保持原样。

## 当前验证及限制

开发树相关核心/journal 回归：2037 passed、35 skipped，29.35s。
随后新增普通交接累计用量/错误输入测试所在协调器组：37 passed，0.09s。
这些结果是隔离测试，不是现场维护或 H01/Q4/H11 通过。
前序开发失败保留在本机 `/mnt/data1/tmp/minimal-*.log`；已修复旧三批夹具、身份推导、
删减时误删的固定输入摘要以及测试夹具错误，没有修改现场以迎合测试。

准确候选的静态私料审查、独立 installed、CI 与发行摘要登记仍待完成。
当前 dispatcher allowlist 保持空；K2/K3 均 NOT_RUN，未消费本次窗口。
旧窗口和所有历史证据继续保留。只在全部 K1 条件通过后开始 K2；失败即停止，
K3 不得自行重试或补采。真实维护成功原件出现前不得发行 K3 真实包。
