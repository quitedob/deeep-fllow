# 文件路径：Dockerfile
# 使用官方 Python 3.12-slim 作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制项目源码到容器内
COPY src/ ./src/
COPY .env.example .env  # 容器内可根据实际情况修改 .env

# 设置环境变量，确保 Python 可以找到 src 包
ENV PYTHONPATH=/app/src

# 暴露应用端口
EXPOSE 8000

# 启动 Uvicorn 服务
# 若需要其他参数，可通过 docker run 时传入
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]