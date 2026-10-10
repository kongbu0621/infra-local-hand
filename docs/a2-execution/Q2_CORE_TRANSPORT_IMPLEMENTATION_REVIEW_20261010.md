# TC1 传输失败来源接入与边界核验

依据已闭合的[准确 A/B/C](../governance/Q2_CORE_TRANSPORT_CONTINUATION_BASELINE.md)，
本实现从独立 C `2bac65db690759bfe89a03228dc3b5186056569d` 继续；三份准确 A 文档不变。
原 UC2 的四原件、八本地返回、freeze、终态和缺失 receipt 保持原事实。

## 实现

- 为 old10a 增加独立十五成员 USTAR 类型，限制196608 B；逐件最大65536 B，拒绝多件、
  缺件、链接、重复、非零尾部和摘要漂移。交叉验证原freeze、五caller、失败记录、terminal、
  preflight/execute/summary、manifest/nonce/clock、四条事件和完整diagnostic。
  不补造receipt，不将未知远端状态或缺失completion转换成成功。
- 新输入仅在原custodian完成READY/身份/用量核验及父FD交接后打开。既有bindings阶段
  从同一个持续持有FD复核，不修改55原件的custodian协议，不重开已交接原件。
- 生产者与独立dispatcher同步采用新失败来源投影、十四份义务和TC准确authority。
  新manifest/receipt v15、preflight/transition v14、reconciliation/capacity-obligations v18、
  host-capacity-condition v17。guest仅更新准确新session；原过程与身份保护保持。
- 新私有maintenance/core caller与独立维护验收器接入同一输入。新维护caller仅允许一次
  preflight和通过后的同窗execute，完整保留diagnostic；核心入口仍需成功维护原件与真实
  coordinator completion。旧调用器、freeze、terminal及所有历史来源摘要不改。

## 离线验证

真实保留归档153600 B、十五成员已由新解析器验证，其来源投影通过独立dispatcher。
新输入声明与逐文件索引只保存在私有目录。两侧原历史摘要常量组逐项核对未变。
新来源/拒绝/接线定向回归243 passed；实际custodian及延后归档读取生命周期44 passed，
包含原121/122布局及新122起始布局、fork/READY/子进程故障、归档漂移、pre/post真实管道、
输出持有、CPU/RSS核算与最终正常退出，原128 FD/256 MiB AS限制不变。

首轮新FD测试40 passed/4 failed：合成目录父级可组写，真实保护性读取拒绝。改用已保护的
测试父目录后44 passed；没有放宽生产规则。首轮宽回归3409 passed/48 skipped/36 failed，
包括本机umask使合成文件可组写、未更新的authority/版本/成本断言和发行摘要；失败日志保留。
用私有测试权限及修正夹具复核。此记录不以失败夹具结果替代最终检查。

最终按CI的022 umask复核：核心/维护3449 passed、48 skipped；固定来源/原窗口548 passed、
21 skipped；安装目录权限与新来源拒绝77 passed。第二轮的3446 passed/48 skipped/3 failed
也保留，其中两项遗漏十四份成本断言，一项安装目录测试依赖022 umask；生产保护不变。

保留来源的完整形状核算：维护十四份18144 MiB/5180 inodes/1680 CPU-s，加核心捕获为
18208 MiB/5196 inodes。交接前122 FD、保守峰值128，交接后父持续70、含原20余量90，
子进程最多64；核心准备115持续FD加原11余量为126。原8控制子进程、120 CPU-s、
512 MiB聚合RSS、900/780秒窗口均不变，没有退款。

维护marker形状约63639 B，成功receipt形状约44038 B，均低于65536 B；pre/post描述
约28470/48655 B，压缩bundle约33694/37114 B，展开约143770/165929 B，remote argv约
47228/51788 B，均在原限制内。上述是保留来源与显式合成成功形状，不是当前VM就绪或现场
成功证据；准确提交后的完整核验值、核心整包上界、CI和独立安装另存冻结记录。

**TC1 实现/验证进行中，TC2 NOT_ISSUED，TC3/H01/Q4/H11 NOT_RUN。**
尚未以本记录签发现场窗口。继续本批已批准的准确提交CI、独立安装和双caller冻结，全部
完成后执行唯一10b；失败即停止并保留，只有完整维护成功才继续原07a核心案例。

后续[准确D冻结与实际返回](Q2_CORE_TRANSPORT_FIELD_20261010.md)已完成：TC1通过，唯一10b
在宿主启动身份校验本地预检失败，SSH0、无marker、未进入execute；TC3案例仍NOT_RUN。
该后续记录给出准确D的最终字节数、首次CI、独立安装与终态，不改变本实现时点的历史记录。
