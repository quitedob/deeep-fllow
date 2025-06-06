-----

# 🦌 DeerFlow

[](https://opensource.org/licenses/MIT)
[](https://www.python.org/downloads/release/python-3120/)
[](https://www.google.com/search?q=https://github.com/example/repo)

一个基于 LangGraph 的自主 AI 研究代理，能够自动规划、执行多源信息检索、并生成多种格式的研究报告。

## ✨ 功能特性

  - **🤖 自主 Agent 流程**: 利用 LangGraph 构建自主研究流程，从任务规划、信息检索到报告生成，全程自动化。
  - **🌐 多源融合检索**: 集成 Tavily、ArXiv、DuckDuckGo 及本地向量知识库，获取全面、多维度的信息。
  - **✍️ 多格式报告生成**: 一键生成 Markdown, PDF, TXT, PowerPoint (`.pptx`) 甚至语音播报 (`.mp3`) 等多种格式的研究报告。
  - **🔌 高度可扩展**: 模块化的 Agent 和工具设计，可以轻松添加新的工具（如数据库、API）或自定义 Agent 行为。
  - **📊 监控与告警**: 内置基于 Redis 的任务队列长度和节点失败率监控，可通过邮件和钉钉发送告警，并支持 Prometheus 指标导出。
  - **🚀 两种运行模式**: 提供命令行（CLI）模式用于快速执行单个任务，以及 FastAPI 服务模式用于持续集成和 API 调用。
  - **🐳 Docker 一键部署**: 提供 `Dockerfile` 和 `docker-compose.yml`，实现服务的快速容器化部署和管理。

## 🏛️ 系统架构

DeerFlow 的核心是一个由 LangGraph 驱动的状态图（StateGraph），它协调多个智能代理（Agent）协同工作。

```mermaid
graph TD
    A[用户输入: 研究主题] --> B{启动模式};
    B --> C[CLI 模式];
    B --> D[服务模式 API];

    subgraph DeerFlow 核心流程
        C --> E[任务入队/直接执行];
        D --> E;
        E --> F(Planner Agent<br>生成研究计划);
        F --> G(Research Team<br>执行计划);
        G --> H(Researcher Agent<br>执行网络搜索);
        G --> I(Coder Agent<br>执行代码分析);
        G --> J[Reporter Agent<br>整合结果];
        J --> K(OutputGenerator<br>生成多格式报告);
        J --> L(Voice Agent<br>生成语音摘要);
    end

    subgraph 输出结果
        K --> M[MD/PDF/TXT/PPTX 文件];
        L --> N[MP3 音频文件];
    end
```

## 🛠️ 技术栈

  - **核心框架**: LangChain, LangGraph
  - **后端服务**: FastAPI, Uvicorn
  - **任务队列与缓存**: Redis
  - **AI 模型**: DeepSeek (可配置)
  - **报告生成**: python-pptx, gTTS, pdfkit
  - **部署**: Docker, Docker Compose

## 🚀 快速开始

### 1\. 环境设置

建议使用 `make` 命令来简化环境设置和项目运行。

```bash
# 1. 克隆项目
git clone git@github.com:quitedob/deeep-fllow.git
cd deeep-fllow

# 2. 使用 make 创建虚拟环境并安装依赖
# 该命令会自动创建 venv，安装 requirements.txt，并复制 .env.example 为 .env
make setup

# 3. 配置密钥和参数
# 编辑 .env 文件，填入你的 API_KEYS, SMTP, 钉钉机器人等配置
nano .env

# 编辑 conf.yaml 文件，配置所需的 LLM 模型和搜索引擎等
nano conf.yaml
```

### 2\. 运行项目

您可以根据需求选择 CLI 模式或服务模式。

#### CLI 模式

直接在命令行中执行研究任务。

```bash
# 激活虚拟环境
source venv/bin/activate

# 运行一个研究任务，并指定输出格式
python main.py --query "量子计算对现代密码学的影响" --output_options md pdf audio
```

#### 服务模式 (使用 Docker)

推荐使用 Docker Compose 启动后端服务和 Redis。

```bash
# 启动服务 (后台运行)
make docker-up

# 查看服务日志
docker-compose logs -f backend

# 停止并移除服务
make docker-down
```

服务启动后，您可以通过 API 与 DeerFlow 交互。

  - **API 文档**: `http://localhost:8000/docs`

### 3\. API 使用示例

#### 异步启动任务

```bash
curl -X POST "http://localhost:8000/api/start" \
-H "Content-Type: application/json" \
-H "X-API-KEY: your_api_key_here" \
-d '{
  "topic": "人工智能在医疗领域的最新进展"
}'
```

#### 实时查看进度

通过 WebSocket 连接，实时接收各节点的执行状态。

```javascript
// 使用 wscat 或任何 WebSocket 客户端
// wscat -c "ws://localhost:8000/ws/{session_id}" -H "X-API-KEY: your_api_key_here"
```

## 📁 项目结构

```
.
├── conf.yaml               # LLM模型、搜索引擎等应用配置
├── docker-compose.yml      # Docker 服务编排
├── Dockerfile              # 后端服务 Docker 镜像定义
├── langgraph.json          # LangGraph 图结构定义
├── main.py                 # 项目主入口 (CLI & Server)
├── Makefile                # 常用命令封装
├── requirements.txt        # Python 依赖
└── src/                    # 项目源码
    ├── adapters/           # 告警渠道适配器 (邮件, 钉钉)
    ├── agents/             # 各功能 Agent 的实现
    ├── api/                # API 路由定义
    ├── config/             # 配置加载和定义
    ├── graph/              # LangGraph 图的构建和执行
    ├── llms/               # LLM 模型封装
    ├── memory/             # 长期记忆管理
    ├── prompts/            # Agent 的提示模板
    ├── server/             # FastAPI 应用定义
    ├── tools/              # 各种工具 (搜索, 爬虫, 代码执行)
    ├── utils/              # 通用工具 (缓存, 日志, 锁)
    └── workers/            # 后台工作进程 (任务消费, 监控)
```

## 📜 许可证

本项目采用 [MIT 许可证](https://opensource.org/licenses/MIT)授权。