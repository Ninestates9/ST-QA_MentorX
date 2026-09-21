# 甲组：问答与出题

独占脚本：`test_chat_generation.py`。

| 测试函数 | case_id | 内容 |
| --- | --- | --- |
| `test_ai_aichat_01` | AI-R01 | K07 真实课件问答基线 |
| `test_ai_aichat_02` | AI-R02 | 同义改写配对一致性 |
| `test_ai_aichat_03` | AI-R03 | TFLite 错别字与空格噪声 |
| `test_ai_generate_tasks_01` | AI-R04 | GPIO 四类题型生成 |
| `test_ai_aichat_04` | AI-S04 | 服务器凭据能力边界 |

运行：

```powershell
python -m pytest ai_tests/group_a -m ai --run-ai -v
```

脚本调用真实 `ai_model.py` 和真实 `X1_http.get_answer`。数据库由本组 Fake Cursor
替代，Embedding/FAISS 初始化也被隔离；若意外调用 `similarity_search`，测试立即报错。
每次结果写入本组 `artifacts/<run_id>/results.jsonl`。记录完整 prompt 和响应，但不记录
请求头或 API Key。

自动规则只能确认关键字段、顺序、题型结构和可疑凭据声明。否定、反讽、题意可解性、
参考答案正确性及答案泄露仍需人工复核，所以自动规则合格的语义样本记录为 `REVIEW`，
而不是最终 `PASS`。

每次加载快照都会校验实际 DOCX 文件 SHA-256 和 `test_context` 的片段 SHA-256，任一不一致都会在模型调用前停止，要求重新审核数据。Layers/Core 的解释按各 API 名称关联到后续局部描述，不跨越下一 API 名称或句号、分号寻找相反含义，避免把相邻的正确解释判成颠倒；复杂否定和语义关系仍需人工审核。

已知限制：当前 `X1_http.get_answer` 只返回 `message.content`，无法记录服务响应中的模型
标识；temperature 和 seed 未由客户端控制。课件 DOCX 的正文提取结果存在乱码，数据快照
保留原始提取文本与文件哈希，同时使用测试计划中已审核的规范化片段作为本轮输入。
