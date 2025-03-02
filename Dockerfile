FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 添加Poetry到PATH
ENV PATH="${PATH}:/root/.local/bin"

# 复制项目文件
COPY pyproject.toml poetry.lock* ./

# 配置Poetry不创建虚拟环境
RUN poetry config virtualenvs.create false

# 安装依赖（包括服务器依赖）
RUN poetry install --extras server --no-interaction --no-ansi

# 复制应用程序代码
COPY . .

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD ["python", "main.py", "--server", "--host", "0.0.0.0", "--port", "8000"] 