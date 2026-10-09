# 一批完成宿主 FD 修复、维护及核心验证

**PROPOSED / Gate OPEN / NOT APPROVED**，`LH-Q2-CORE-HOST-FD-CONTINUATION-v1`，FD1–FD3。
依[需求](REQUIREMENTS.md)与[架构](ARCHITECTURE.md)。以下尚未实施或发行。

## FD1：闭合后完整实现与验证

1. 三文档固定为准确A，保留真实Owner B。独立C仅登记闭合及Owner批准的旧09b五件最小
   索引；不得把未来批准套用到之前工作。原三文档OPEN字节不改，D继承C且不squash。
2. 宿主接入固定 custodian 源成员；更新来源允许表、完整性和安装验证。55原件只通过
   fork继承交接，不重开。所有原recheck调用和不同inode保护接入；子进程失败不能退回
   较弱模式。现有普通FD guard保持，并对交接前后及收尾分别核算。
3. 完成原管理累计预算对新已知子进程的存活/退出CPU、RSS、进程数、真实wait和期限接线。
   child资源属于原额度，先做完整同窗预检+执行费用验证，不能测完后才加超限例外。
4. 完成单份历史manifest生成/重建及新版本；host、portable prior、approved-input、
   standalone dispatcher独立同步。新增准确旧09b失败分支，保持无guest报告/无完成
   transport/UNKNOWN。十一代55原件全保留，原所有失败语义和来源pin不修改。
5. 必须通过以下实质回归：
   - 在真实128上限中以完整下一代121初始占用，验证交接握手、父子实际峰值、pre双向
     管道、完整输出/备份/模拟VM身份、post、receipt及正常收尾；用合成peer代替SSH/VM。
   - 父副本关闭前child必须已经持有同一open-file description；交接后替换、删除、
     修改内容、硬链接、owner/mode/name漂移仍被原谓词拒绝；没有一次关闭全部再重开。
   - READY/CHECK缺项、错序、错nonce/D、截断、child死亡、IPC/FD分配失败、超时和计量
     缺失均停止；无重启child、重开证据、重试SSH、关机token越序或继续增长。
   - 真实Linux父子CPU/RSS/进程预算与退出计量包含双方，不把共享内存或存活CPU当零。
     失败收尾也不泄漏selector/管道、不丢证据、不伪造子进程退出。
   - 新marker完整resume和引用的双向重建；hash正确且全部55原件独立验证。错摘要、
     缺代次、旧格式伪装、新旧字段同时出现、错source hash或只改producer均拒绝。
   - 用实际guest生成的pre/post报告贯穿host、transition和独立核心验证；旧09b解析
     没有guest报告也能准确保留失败，不能因此降低新成功报告要求。
   - Windows/portable来源验证不导入Linux custodian；核心完整路径保持原保护与FD上限。
6. 只用既有私有副本检查准确来源和全部历史，不查现场。核对完整parent/child FD/RSS/
   CPU生命周期、全形状marker/receipt/argv/bundle/transition/approved-input/整包、十二
   代完整费用和原运行时成本。源码、IPC和结果宽度均纳入边界；任一不足继续离线处理。
7. 完成实现D后发布main，等准确D首次CI三项成功，做同D独立安装验收。冻结两份caller
   与不可变来源、nonce/clock/预算。旧所有caller留存不可运行。新owner协议和标记编码
   未完整验证时禁止FD2，不以普通guard回归代替此验收。

## FD2：唯一新维护09c

沿原固定来源执行本地预检与同窗execute。两次调用各最多一个custodian，费用合并；
预检缺额或交接失败就停止。execute在全部身份、预算、标记上限、来源与caller匹配后
才消费新标记并发固定pre SSH。保留原运行时准备、quiescence/process/writer与数据检查。

只有pre原报告完整验证且持久保存，才发一次正常关机token；确认原VM真实退出后，原
完整备份、一次journal镜像增长/比较、一次维护内原配置启动。固定post SSH验证新boot，
完成同样有界运行时准备、原保护后增长ext4并验证UUID/内容/容量；收齐原件和真实结束。
所有步骤同一900/780秒及原预算，custodian不能延长窗口。失败保留，不另发任何补查。

## FD3：原核心三个结果

独立验收FD2的全部实际成功原件、custody关系、顶层退出、新身份和运行时投影，满足条件
才发行原07a包；顺序运行H01正常任务及结果、Q4运行取消、H11同任务恢复，收集真实verdict。
FD2失败则FD3/H01/Q4/H11 NOT_RUN；核心失败也不追加重试。结果报告分别说明离线/CI、
安装、维护和各核心案例，不用代码修复或另一端任务说明替代现场成功。
