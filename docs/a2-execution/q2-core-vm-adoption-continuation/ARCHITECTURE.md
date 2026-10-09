# 已有证据到维护及核心的身份接线

**PROPOSED / Gate OPEN / NOT APPROVED**。Scope `LH-Q2-CORE-VM-ADOPTION-CONTINUATION-v1`。
依[需求](REQUIREMENTS.md)，不改变 R 或原保护语义。

1. 将已索引的30份不可变返回与原索引封装为一个私有、只读 tar 输入。固定31个普通
   成员，不解压落地，拒绝缺项、重复、额外成员及链接；每件 bytes/SHA与原索引匹配。
   归档上限512 KiB，原件总量256 KiB、索引64 KiB，不占用30个长期FD。不得采集新现场数据。
2. 核对 Owner 授权、helper/方案冻结、一次启动/SSH/安装、完整命令返回、安装校验、
   quota前后一致、PID/start/raw cmdline及当前绑定。转换启动记录的 JSON argv摘要为
   原维护使用的 NUL argv摘要。产出≤4096 B身份投影，明确 `execution_permission=false`。
3. 保留历史 Q1/HELLO boot；当前 guest boot只来自已验证激活返回。固定旧 start脚本
   的原参数，仅用获准 system路径、pidfile、serial重建当前argv。维护重启仍仅替换
   本次新pidfile和null串口。活动system允许位于已核验的外部父目录，其余四盘保持原根。
   同FD/路径/父目录/设备/inode/权限复核保持；正常运行写入与关机后不可变检查分开。
4. 当前维护源绑定携带激活投影和归档pin。完整维护成功后，host验证原件，再向核心
   投影传递历史boot、维护前当前boot、维护后新boot及对应VM身份。独立dispatcher
   自行验证三者关系、九代历史及成功证据；不把旧HELLO当作当前boot，也不倒填旧失败PID。
5. 追加旧08f第九profile，按原manifest/receipt v10、guest/input v3及DS五字段语义
   验证五原件；历史完整resume保持。新09a manifest/receipt v11、preflight v10、
   transition v10，reconciliation/history v14、host-capacity v13。
6. 旧08f marker为64566 B，不能直接叠加新身份和第九代历史。新marker仅将顶层重复
   `resume`替换为`resume_sha256`，摘要指向完整严格验证的历史；manifest、inputs、
   receipt、transition继续保存完整历史，不增大65536 B上限，不改变旧schema或旧原件。

只有新准确 A、真实 B、独立 C、继承C的D、来源/CI/独立安装/双方冻结全部完成，才允许
现场入口。候选中缺失的批准以None和关闭的发行列表表示，不借用旧DS授权，不伪造commit。
VA2完整成功之前不得生成可发行真实核心包；失败时保留全部原件和原Unknown，不续发。
