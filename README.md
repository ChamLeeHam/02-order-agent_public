## 本地配置

将 `.env.example` 复制为 `.env`，填写本地数据库、模型 API 和高德 `AMAP_API_KEY` 配置。真实 `.env` 不提交到 Git。

## 一、 UV的基本使用
    UV 和 conda都是目前非常流行的python环境和包管理工具。
- conda是一个跨语言的环境管理工具
- uv是conda的子集，专门用来管理python环境
### 1.1 UV安装
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
### 1.2 基本使用
    uv venv --python 3.12   #创建项目环境
    uv init project
    cd project
    uv add langchain
    uv add langchain-openai
    uv rm langchain-openai  #删除依赖
    
    uv sync  #同步依赖
    uv run python文件 --arg1 -- arg2 #运行python文件并传入参数
        
        
### Docker命令
    docker run -d  --name attu   -p 8000:3000 -e MILVUS_URL=host.docker.internal:19530  zilliz/attu:v2.5

    standalone.bat start




### 前端链接
    http://localhost:3000//docs#/default/chat_endpoint_chat_post
