# MentorX 模块二 AI 测试

该目录与离线 `tests/` 隔离。这里只收集真实模型应用测试，不复用
`tests/conftest.py` 中的网络拦截和 AI stub。

## 运行

先在项目根目录的 `.env` 中配置 `XFYUN_LLM_API_KEY`，再执行：

```powershell
python -m pytest ai_tests -m ai --run-ai -v
```

不传 `--run-ai` 时测试会明确跳过。缺少凭据时，即使传入开关也会明确跳过，
不会把认证或配置错误算作模型回答失败。单独运行甲组：

```powershell
python -m pytest ai_tests/group_a -m ai --run-ai -v
```

运行证据由各组分别写入自己的 `artifacts/<run_id>/`，不得记录认证头或真实密钥。
