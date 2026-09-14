# MentorX 后端

本目录是 MentorX 教学辅助系统的后端。项目基于 Flask 提供 HTTP API，包含用户与课程管理、练习生成和批改、AI 问答、手写 OCR、教学建议、PPT 生成及系统统计等功能。

## 1. 运行环境

### Python 环境

- 推荐：Python 3.10 或 3.11（64 位）
- 最低版本：Python 3.10
- 不建议低于 3.10：源码使用了 `str | None` 等 Python 3.10 引入的类型注解语法
- 操作系统：Windows、Linux 或 macOS；本项目当前目录结构已在 Windows 下使用

建议使用独立虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux/macOS 的激活命令为：

```bash
source .venv/bin/activate
```

首次安装 `sentence-transformers` 时还会间接安装 PyTorch，下载量较大，请保证磁盘空间和网络可用。

### 外部基础设施

启动完整后端前需要准备以下服务：

| 服务 | 建议版本 | 当前代码使用的地址 | 用途 |
| --- | --- | --- | --- |
| MySQL | 8.0+ | `127.0.0.1:3306` | 用户、课程、章节、练习和统计数据 |
| Redis | 6.0+ 或 7.0+ | `localhost:6379`，DB 0 | API 调用次数计数及定时同步 |

当前 MySQL 配置位于 `database_utils.py`：用户名为 `root`、数据库名为 `mentorx`。密码也直接写在该文件中。**当前仓库没有数据库建表或初始化 SQL**，因此必须另行取得并导入与源码查询相匹配的 `mentorx` 数据库结构和初始数据，否则服务无法正常启动。

Redis 启动示例：

```powershell
redis-server
```

启动前可检查服务是否可访问：

```powershell
mysql -h 127.0.0.1 -P 3306 -u root -p
redis-cli -h localhost -p 6379 ping
```

Redis 正常时第二条命令应返回 `PONG`。

### 外部网络与账号

部分功能依赖公网服务：

- 讯飞星火大模型：`https://spark-api-open.xf-yun.com`
- 讯飞手写 OCR：`http://webapi.xfyun.cn`
- Docmee AI PPT：`https://docmee.cn`
- Hugging Face：首次加载嵌入模型时下载 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

相应凭据目前分别硬编码在 `X1_http.py`、`ocr.py` 和 `aiPPT.py` 中。课程实验中不应提交或公开真实凭据；建议后续改为从环境变量读取，并立即轮换已经暴露过的密钥。网络不可用或凭据失效时，AI 问答、OCR、PPT 生成等接口会失败，但可通过 Mock 隔离这些外部服务进行单元测试。

## 2. 目录与模块

```text
main.py                    Flask 应用入口及 API 路由
database_utils.py          MySQL/Redis 数据访问逻辑
sync_utils.py              Redis 统计定时同步到 MySQL
ai_model.py                AI 问答、出题、批改和教学建议
X1_http.py                 讯飞星火 HTTP 调用
ocr.py                     讯飞手写 OCR 调用
aiPPT.py                   AI PPT 业务流程
aiPPT_api.py               Docmee API 封装
aiPPT_http_utils.py        PPT HTTP/SSE 工具
db.py                      从 knowledge 文档构建 FAISS 向量库
download_model.py          下载嵌入模型的辅助脚本
knowledge/                 知识库原始 DOCX 文件
images/                    从 DOCX 提取出的图片
multi_doc_vector_db/       已生成的 FAISS 向量索引
ocr_img/                   OCR 上传图片的临时保存目录
aiPPT/                     生成 PPT 时使用的中间文件与输出目录
```

## 3. 安装与初始化

### 安装 Python 依赖

```powershell
python -m pip install -r requirements.txt
```

### 准备 MySQL

1. 启动 MySQL。
2. 创建或导入名为 `mentorx` 的数据库。
3. 确认数据库至少包含源码引用的表：`user`、`course`、`course_student`、`chapter`、`exercise`、`practice_history`、`communicate_history`、`system_stats`。
4. 根据本机环境调整 `database_utils.py` 中的连接参数。

注意：只有表名不足以可靠重建表结构，字段定义、主外键、默认值和初始数据应以原项目 SQL 为准。

### 准备向量库

仓库已经包含 `multi_doc_vector_db/index.faiss` 和 `index.pkl`。如果修改了 `knowledge/` 中的 DOCX 文件，可重新生成索引：

```powershell
python db.py
```

该命令会读取 `knowledge/`、向 `images/` 提取图片，并覆盖/更新本地向量库内容。首次执行会从 Hugging Face 下载嵌入模型。

## 4. 启动后端

确保 MySQL、Redis 和向量模型均可用后，在项目目录执行：

```powershell
python main.py
```

服务默认监听：

- 地址：`0.0.0.0`
- 端口：`5000`
- 本机访问：`http://127.0.0.1:5000`
- Flask 调试模式：开启

可使用无需登录的课程列表接口做基本连通性检查：

```powershell
curl http://127.0.0.1:5000/api/getCourseList
```

多数写接口接收 `application/x-www-form-urlencoded` 表单数据，而不是 JSON。带有 `@jwt_required()` 的接口需要先调用 `/api/signIn`，再在请求头中携带：

```text
Authorization: Bearer <登录接口返回的 jwt>
```

## 5. 测试与质量保证

依赖文件已经包含 `pytest` 和 `pytest-cov`。后续测试文件建议放在 `tests/` 目录，执行：

```powershell
pytest -v
pytest --cov=. --cov-report=term-missing
```

建议按以下层次开展课程实验：

1. 对纯数据转换和参数分支编写单元测试。
2. Mock MySQL、Redis、讯飞和 Docmee 请求，测试异常与降级路径。
3. 使用 Flask test client 测试路由、JWT 鉴权、状态码和响应结构。
4. 在独立测试数据库中进行集成测试，不要直接使用开发或生产数据。

## 6. 当前已知的部署与安全注意事项

- 项目缺少数据库 schema/初始化脚本，无法仅凭当前目录从零构建数据库。
- JWT 密钥、MySQL 密码和外部 API 凭据被硬编码在源码中，需要改为环境变量并轮换凭据。
- Flask 以 `debug=True` 启动，只适合本地开发与测试，不应直接用于生产部署。
- CORS 当前允许所有来源，生产环境应限制允许的前端域名。
- `ai_model.py` 在导入阶段加载本地 FAISS 索引和嵌入模型；索引缺失、版本不兼容或模型下载失败都会导致应用启动失败。
- `aiPPT_http_utils.py` 对 HTTPS 请求设置了 `verify=False`，会跳过证书校验，存在中间人攻击风险。
- `ocr_img/` 与 `aiPPT/` 必须存在且对运行用户可写。

## 7. 依赖说明

`requirements.txt` 使用固定版本，以便课程测试环境可复现。其中 `opencv-python-headless` 适用于不需要桌面窗口的后端；如果后续确实需要 `cv2.imshow` 等 GUI 功能，可将其替换为相同版本的 `opencv-python`。
