# 原 guest 核验、原维护、原核心的一次接续

Authority：Owner；**PROPOSED / Gate OPEN / NOT APPROVED**。
Scope `LH-Q2-CORE-GUEST-RESUMPTION-v1` / GR1–GR4；本文件与[需求](REQUIREMENTS.md)、
[架构](ARCHITECTURE.md)组成唯一待确认方案。准备方案不发行新 caller 或现场请求。

1. 形成准确文档 commit A，保留相邻 Owner B 的原请求/答复及原固定 Q1 目的地/私有
   载荷边界。独立 C 仅登记 R/A/B 和 CLOSED 范围；新 D 下降自 C，正常 merge 不 squash。
   原两版 HR A 的六份文档、HR2 终态及全部冻结字节保持。不存在第二个额外审批层。
2. GR1 在现有模块内接入新版本；离线重新消费旧19件启动及失败9件原件/索引/终态，
   保留全部历史 UNKNOWN。采用 capture 已验证的完成记录修复，不扩大其动作/限额。
   生产者和独立消费者同时核对新批准、旧失败、新核验、19份义务及27503/8406总成本。
   维护仍为原未发行 `lhqjgrow-20261011c`，核心仍为原 `lhqcore-20261007a`。
3. 私有新准备根固定为本批 `lhqcore-guest-resumption-20261012`；新 guest 会话固定为
   `lhqguest-20261012a`。准备/guest 两池全量计费，不预先创建另一备用窗口。
   所有新核验、最终数据冻结、维护、核心和父调用器，在现场前一次完成源码冻结。
   源码/目的地/可信工具/安装关系/请求 nonce 固定，未来只填预声明的数据槽。
4. 验证实际完整 producer→独立消费者→approved-input→包解析→维护/core 入口链。
   必测旧失败被隐藏或改成成功、缺原件/EOF/实际完成、旧子进程退出码被补造、新旧
   nonce/request 混用、启动后身份漂移、仅 listener 被当 guest 就绪、第二次发行、
   旧 caller 重放、费用退款/重复第十九代、缺维护成功而放行原核心。
   真正文件/管道测试使用现有隔离办法；合成通过不能作为 H01/Q4/H11 现场 PASS。
5. 校验实际归档≤1 MiB、固定成员覆盖、持续持有FD≤256、全部来源大小和准备池、
   guest 流≤64 KiB/流、结果≤128 KiB、原 argv/CPU/AS/RSS/超时及19份维护总费用。
   正常 PR 发布准确 D，检查其首次 CI 和独立安装，再冻结全部 caller/来源/数据槽。
   有界性或完整性未通过不得发行；不自动增加容量、调整目标、补采或新增窗口。
6. GR2 只执行现有的同一 host/VM/镜像/信任检查及一次原六命令 SSH 核验，无新启动、
   无独立 probe。保存真实 caller/SSH child/外层工具返回和双 EOF，旧失败保持原样。
   只有实际完整核验通过才生成 activation/v4 并由两侧重建，冻结最终维护输入。
7. GR3 原11c一次 preflight，PASS才同窗execute；完整维护原件、两侧消费和真实
   coordinator/custodian完成全部通过，直接GR4原07a H01→Q4→H11。不逐小步请示。
   任一步失败、漂移或必要事实 UNKNOWN 即 STOP_AND_RETAIN，不重放、重连或改码续跑。
8. 只在现有核心结果入口写真实结果。最终交付以三案实际执行为准；文档、CI、安装、
   VM 启动及核验通过均不冒充核心完成。详细路径/输出保持私有。

当前已有离线检查：原19件启动通过原消费者；24个旧caller及17份受保护源码摘要未变；
基于固定原件/既有未来成功字段界限计算的95成员证明上界747520 B<1 MiB。
这些结果只支持本方案可审查，不是GR1实现/发行许可。GR1 NOT_STARTED，GR2/GR3
NOT_ISSUED，GR4/H01/Q4/H11 NOT_RUN。
