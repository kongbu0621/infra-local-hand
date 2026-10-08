# 多命令属性修复同步与已有原件核对

日期：2026-10-08，Asia/Shanghai。本轮只同步已有修复、运行已有隔离测试和核对保留副本。
本地main从 `9346b6bf143c0db8a53fc8ec206bcd1342281c84` 快进至
`e2d27ca51317ccd449772d82a2366b2f3092711e`；未另改生产/测试源、配置、旧caller、
冻结副本或生成真实核心包。没有现场预检、VM观察、SSH、补采、清理或重试。

## 准确已有修复

修复仅对六个已存在的Exec属性保留多行及顺序；标量与未知键重复继续拒绝。
属性摘要、身份/别名、受保护路径、间接启动及domain检查仍消费全部内容，未丢掉前项。
同次格式失败记录具体子条件和有界行摘要，不增加查询。源码审查与原开发证据见
[修复记录](Q2_CORE_NAMES_CONTINUATION_REVIEW_20261008.md#systemctl-多命令属性解析修复)。
旧08b具体原响应缺失；这些证据不能还原它的唯一根因。

[准确首次CI 37717057010](https://github.com/kongbu0621/infra-local-hand/actions/runs/37717057010)
head_sha为上述修复，run_attempt=1，三个job及两平台源码/独立安装步骤均completed/success。
Linux日志 **6840 passed / 89 skipped**，独立安装 **PASS / 94 checks / 292 commands**。
完整CI元数据和已有Linux日志私有保留。未重跑CI或机械重复独立安装；这不验证未来新D。

本机运行既有show-format、Names、systemctl、templates和guest-completion五文件：首次
**283 passed / 13 skipped / 3 errors**。13项跳过均缺少本机v255格式库，分别12项字符串
格式和1项属性格式，不计PASS。三项错误来自沙箱禁止私有D-Bus绑定Unix socket；
沿普通身份在本机隔离环境仅复核这三项，**3 passed**，未访问真实manager、VM或现场。
首轮报错日志和精确复核均保留；没有为此改源码或把首次全组写成全绿。

## 原私有副本核验

仅对08b五件已有私有副本沿O_NOATIME/O_NOFOLLOW、owner/0600、单链接、固定上限、
held FD及前后元数据保护读取，总59489 B，逐件与原NC2私有索引一致。
marker/manifest与已有预检、receipt与已有execute一致；原v6/准确R/A/C/D及四代
嵌套resume保持，manifest摘要、事件和流摘要相互一致。

一次离线审查断言误用默认无LF的core canonical重算维护manifest摘要而失败；修正为
原维护canonical后核对通过。原件未修改，不把审查脚本编码错误描述为原件不一致。
私有附件 `NC2_08B_ORIGINALS_INDEX_REVIEW.json` 已准备供Owner审阅，事件
`NC2-08B-ORIGINALS-INDEX-REVIEW-20261008-01`；具体五pins未公开。

08b仍PRE_QUIESCENCE/GROWTH_SYSTEMCTL_FORMAT、动作空、无关机token、一次SSH、
remote_exit UNKNOWN；私有执行gate仍 `NC2_CONSUMED_FAILED_NC3_NOT_RUN`。
原核心caller未执行；本轮不产生新caller、执行包或窗口。

## 待决交付

[准确新A](../governance/Q2_CORE_EXEC_CONTINUATION_BASELINE.md)仅定义现有修复后的
五代绑定、一次08c维护和条件原核心，不另造协议框架或新增支线功能。
三文档、登记、审查及OPEN声明仅本地准备，发布及旧08b最小索引披露待Owner明确决定。
原NC批准的准确文档及来源字节、旧消费和全部费用保持，不将截图当作新的B/C。
