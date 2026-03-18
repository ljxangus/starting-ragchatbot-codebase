# RAG 聊天机器人数据流程图

## 系统架构流程图

```mermaid
sequenceDiagram
    participant User as 👤 用户
    participant Frontend as 🌐 前端 (HTML/JS)
    participant API as ⚡ FastAPI 后端
    participant RAG as 🤖 RAG 系统
    participant Session as 📝 会话管理器
    participant AI as 🧠 智谱 AI (GLM-4)
    participant Tool as 🔍 搜索工具
    participant Vector as 📚 向量数据库 (ChromaDB)

    User->>Frontend: 1. 输入问题
    Frontend->>Frontend: 2. 获取用户输入和 session_id
    Frontend->>API: 3. POST /api/query<br/>{query, session_id}

    API->>API: 4. 验证请求 (Pydantic)
    API->>Session: 5. 获取或创建会话 ID

    alt 会话不存在
        Session->>Session: 创建新会话
        Session-->>API: 返回新 session_id
    else 会话已存在
        Session-->>RAG: 返回历史记录
    end

    API->>RAG: 6. rag_system.query(query, session_id)

    RAG->>Session: 7. 获取对话历史
    Session-->>RAG: 返回历史消息

    RAG->>AI: 8. generate_response()<br/>{query, history, tools}

    AI->>AI: 9. 构建系统提示词
    AI->>AI: 10. 准备消息列表

    AI->>AI: 11. 判断是否需要搜索工具

    alt 需要搜索课程内容
        AI->>Tool: 12. 调用搜索工具<br/>{search_query}

        Tool->>Vector: 13. 向量搜索<br/>语义相似度匹配
        Vector-->>Tool: 14. 返回相关文档片段

        Tool->>Tool: 15. 格式化搜索结果
        Tool-->>AI: 16. 返回搜索结果

        AI->>AI: 17. 基于搜索结果生成回答
    else 不需要搜索
        AI->>AI: 12a. 直接使用已有知识回答
    end

    AI-->>RAG: 18. 返回 AI 生成的回答

    RAG->>Tool: 19. 获取搜索来源
    Tool-->>RAG: 20. 返回 sources 列表

    RAG->>Session: 21. 更新会话历史<br/>{query, answer}
    Session-->>RAG: 确认更新

    RAG-->>API: 22. 返回 {answer, sources}

    API->>API: 23. 构建 QueryResponse
    API-->>Frontend: 24. JSON 响应<br/>{answer, sources, session_id}

    Frontend->>Frontend: 25. 解析 JSON 响应
    Frontend->>Frontend: 26. 渲染用户消息
    Frontend->>Frontend: 27. 渲染 AI 回答 + 来源
    Frontend-->>User: 28. 显示完整对话
```

## 组件架构图

```mermaid
graph TB
    subgraph "前端层 Frontend Layer"
        UI[🌐 HTML 界面<br/>index.html]
        JS[📜 JavaScript<br/>script.js]
        CSS[🎨 样式<br/>style.css]
    end

    subgraph "API 层 API Layer"
        FastAPI[⚡ FastAPI<br/>app.py]
        QueryEnd[POST /api/query]
        StatsEnd[GET /api/courses]
        Static[静态文件服务]
    end

    subgraph "业务逻辑层 Business Logic"
        RAG[🤖 RAG 系统<br/>rag_system.py]
        AIGen[🧠 AI 生成器<br/>ai_generator.py]
        SessionMgr[📝 会话管理器<br/>session_manager.py]
        ToolMgr[🔧 工具管理器<br/>search_tools.py]
    end

    subgraph "数据存储层 Data Storage"
        VectorDB[📚 向量数据库<br/>ChromaDB]
        DocProc[📄 文档处理器<br/>document_processor.py]
        CourseData[课程数据<br/>docs/]
    end

    subgraph "外部服务 External Services"
        ZhipuAI[🌐 智谱 AI<br/>GLM-4 API]
    end

    UI --> JS
    JS -->|fetch API| FastAPI
    FastAPI --> QueryEnd
    FastAPI --> StatsEnd
    FastAPI --> Static

    QueryEnd --> RAG
    RAG --> AIGen
    RAG --> SessionMgr
    RAG --> ToolMgr

    AIGen -->|HTTP 请求| ZhipuAI
    ZhipuAI -->|响应| AIGen

    ToolMgr --> VectorDB
    VectorDB --> DocProc
    DocProc --> CourseData

    SessionMgr -->|会话状态| RAG

    style UI fill:#e1f5ff
    style ZhipuAI fill:#ffe1e1
    style RAG fill:#fff4e1
    style VectorDB fill:#e1ffe1
```

## 数据处理流程详解

### 1️⃣ 前端处理流程

```mermaid
flowchart LR
    A[用户输入问题] --> B{点击发送或 Enter}
    B --> C[sendMessage 函数]
    C --> D[添加用户消息到 UI]
    D --> E[准备请求数据]
    E --> F[获取/生成 session_id]
    F --> G[POST /api/query]
    G --> H{等待响应}
    H --> I[接收 JSON 响应]
    I --> J[添加 AI 消息到 UI]
    J --> K[显示来源链接]
    K --> L[更新会话 ID]

    style A fill:#e3f2fd
    style L fill:#c8e6c9
```

**关键代码位置**：
- `frontend/index.html:59-66` - 输入框和发送按钮
- `frontend/script.js:48-95` - sendMessage 函数

### 2️⃣ 后端 API 处理流程

```mermaid
flowchart TD
    A[接收 POST /api/query] --> B[Pydantic 验证]
    B --> C{session_id 存在?}
    C -->|否| D[创建新会话]
    C -->|是| E[使用现有会话]
    D --> F[调用 RAG 系统]
    E --> F
    F --> G[rag_system.query]
    G --> H[构建响应]
    H --> I[返回 QueryResponse]

    style A fill:#fff3e0
    style I fill:#c8e6c9
```

**关键代码位置**：
- `backend/app.py:56-74` - query_documents 函数
- `backend/models.py:7-12` - QueryRequest 模型
- `backend/models.py:15-20` - QueryResponse 模型

### 3️⃣ RAG 系统核心流程

```mermaid
flowchart TD
    A[RAGSystem.query] --> B[获取会话历史]
    B --> C[构建提示词]
    C --> D[AI 生成响应]
    D --> E{需要使用工具?}
    E -->|是| F[调用搜索工具]
    E -->|否| G[直接生成回答]
    F --> H[向量数据库搜索]
    H --> I[获取搜索结果]
    I --> J[基于结果生成回答]
    G --> K[获取来源]
    J --> K
    K --> L[更新会话历史]
    L --> M[返回回答 + 来源]

    style A fill:#f3e5f5
    style M fill:#c8e6c9
```

**关键代码位置**：
- `backend/rag_system.py:102-140` - query 方法
- `backend/ai_generator.py:43-94` - generate_response 方法
- `backend/search_tools.py:30-65` - CourseSearchTool.execute

### 4️⃣ AI 生成器工作流程

```mermaid
flowchart TD
    A[generate_response] --> B[构建系统提示]
    B --> C[准备消息列表]
    C --> D[添加工具定义]
    D --> E[调用智谱 AI API]
    E --> F{模型需要工具?}
    F -->|是| G[执行工具调用]
    F -->|否| H[返回直接响应]
    G --> I[搜索课程内容]
    I --> J[获取工具结果]
    J --> K[发送第二轮请求]
    K --> L[最终回答]
    H --> M[返回回答]

    style A fill:#fce4ec
    style L fill:#c8e6c9
    style M fill:#c8e6c9
```

**关键代码位置**：
- `backend/ai_generator.py:43-94` - generate_response
- `backend/ai_generator.py:111-169` - _handle_tool_execution
- `backend/ai_generator.py:96-109` - _convert_tools_to_zhipu_format

## 技术栈总结

### 前端技术栈
- **HTML5** - 页面结构
- **CSS3** - 样式设计
- **Vanilla JavaScript** - 交互逻辑（无框架）
- **Fetch API** - HTTP 请求

### 后端技术栈
- **Python 3.13** - 编程语言
- **FastAPI** - Web 框架
- **Pydantic** - 数据验证
- **Uvicorn** - ASGI 服务器

### AI 和数据技术栈
- **智谱 AI (ZhipuAI)** - GLM-4 语言模型
- **ChromaDB** - 向量数据库
- **Sentence Transformers** - 文本嵌入模型 (all-MiniLM-L6-v2)
- **Python-dotenv** - 环境变量管理

## 关键文件索引

| 文件路径 | 功能描述 | 关键函数/类 |
|---------|---------|-----------|
| `frontend/index.html` | 前端主页面 | UI 结构 |
| `frontend/script.js` | 前端逻辑 | sendMessage() |
| `backend/app.py` | API 主入口 | query_documents() |
| `backend/rag_system.py` | RAG 核心系统 | RAGSystem.query() |
| `backend/ai_generator.py` | AI 生成器 | AIGenerator.generate_response() |
| `backend/search_tools.py` | 搜索工具 | CourseSearchTool.execute() |
| `backend/vector_store.py` | 向量存储 | VectorStore.search() |
| `backend/session_manager.py` | 会话管理 | SessionManager |
| `backend/config.py` | 配置管理 | Config 数据类 |
| `.env` | 环境变量 | ZHIPU_API_KEY |

## API 端点规范

### POST /api/query
**请求**：
```json
{
  "query": "用户的问题",
  "session_id": "可选的会话ID"
}
```

**响应**：
```json
{
  "answer": "AI 的回答",
  "sources": ["来源1", "来源2"],
  "session_id": "会话ID"
}
```

### GET /api/courses
**响应**：
```json
{
  "total_courses": 5,
  "course_titles": ["课程1", "课程2"]
}
```

## 性能优化要点

1. **会话管理** - 维护对话上下文，避免重复发送历史
2. **向量搜索** - 语义搜索提高相关性
3. **工具调用** - 智能决策何时搜索，减少不必要的 API 调用
4. **异步处理** - FastAPI 异步支持提高并发性能
