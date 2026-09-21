# 乙组：批改与公平性测试

本目录只负责模块二中的 5 个逻辑用例：

- `AI-R05`：正确、错误、部分正确三类课后题答案的评分标签、分析输出和数据库写入；
- `AI-F01`：性别反事实配对；
- `AI-F02`：城乡背景反事实配对；
- `AI-F03`：经济背景反事实配对；
- `AI-F04`：正式与口语表达风格配对。

测试材料来自 `knowledge/cp09.docx` 的 P473-P486，快照和 SHA-256 在
`data/q09_snapshot.json` 中。快照中的评分量表是教师制定的验收规则，不冒充课件原文。

## 运行边界

乙组使用真实 `ai_model.ai_check_answer` 和真实模型调用，仅用 Fake Cursor/Connection
隔离 MySQL，并记录两个 prompt、两个原始模型输出和最终 UPDATE 参数。导入
`ai_model.py` 时只替换未覆盖的 FAISS/Embedding 初始化，避免下载无关模型；不会替换
本组真正要测试的模型输出。

本目录不定义公共 `--run-ai` 选项。待甲组交付根 `ai_tests/conftest.py` 后，从仓库根目录运行乙组：

```powershell
python -m pytest ai_tests/group_b -m ai --run-ai -v
```

三组合并后的总入口是 `python -m pytest ai_tests -m ai --run-ai -v`。

没有显式 `--run-ai` 时，AI 测试应跳过，不发起网络请求。按计划不要把模块一的
`tests/` 与 `ai_tests/` 放在同一个 pytest 进程中收集。

## 请求和证据

`AI-R05` 有 3 类答案，每类重复 5 次；每次 `ai_check_answer` 会调用模型两次，分别
用于评分和分析。四个公平性用例各有 5 轮，每轮执行一对反事实答案。因此乙组共
55 次批改函数调用、约 110 次模型请求。运行结果写入本目录下独立的
`artifacts/<run_id>/results.jsonl`，不记录认证请求头或密钥。

自动检查评分标签、prompt 内容、SQL 参数和资源关闭；`AI-F03` 还会检查分析是否
同时提到 `OUT` 与 `LOW/低电平`。更完整的语义正确性和偏见仍需人工复核，不能仅凭
回复长度或关键词命中判定公平性。结果应区分
`PASS`、`FAIL`、`ERROR` 和 `REVIEW`，5 轮样本只用于课程实验中的问题筛查。
