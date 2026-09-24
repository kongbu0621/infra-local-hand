# 开发期失败与修正

本文件是开发过程摘要，不是各次完整 stdout/stderr 原件。
最终完整定向测试原件独立保存在 `unittest.log`，没有覆盖以下失败结论。

1. 实验接线测试中的 fake 方法误命名为 `run`，覆盖了 unittest.TestCase.run，
   在 setUp 前出现 `AttributeError: 'ExperimentWiringTests' object has no attribute 'calls'`。
   重命名为 `deliver_query` 后，15 项接线/输入测试通过；未借此更改产品行为。
2. CLI 平台替身测试在导入 shutil 前模拟 Windows，导致测试解释器寻找 `_winapi`。
   调整测试的导入顺序后，9 项通过。这不是一次真实 Windows 运行。
3. 首次整组集成运行报告 `Ran 194 tests in 3.024s`、`FAILED (errors=8)`。
   CLI 拒绝记录已统一使用 `failure_code`，测试 helper 仍取 `value["code"]`，
   产生 `KeyError: 'code'`（8 个子用例）。更新断言后单组 9 项及最终整组 194 项通过。
   该次交互输出有截断，故不声称已保存其完整日志。

独立复核还指出 manager cleanup 的 kill/pump 异常可能跳过 pipe close；
修正 finally 收尾并加入负例，27 项 guard 测试包含此回归。
最终归档运行包含所有修正；开发期部分测试通过不充当最终源码整体通过。
