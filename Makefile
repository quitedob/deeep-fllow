# 文件路径：Makefile
# -*- coding: utf-8 -*-
# Makefile：封装项目常用命令，简化部署与调试流程

# 定义虚拟环境目录
VENV_DIR = venv

.PHONY: help setup run ui test docker-up docker-down

help:
	@echo "可用目标："
	@echo "  setup       - 创建虚拟环境并安装依赖"
	@echo "  run         - 启动后端 FastAPI 服务"
	@echo "  ui          - 启动前端 UI 服务（需 Node.js 环境）"
	@echo "  test        - 运行单元测试"
	@echo "  docker-up   - 使用 docker-compose 启动后端与 Redis 服务"
	@echo "  docker-down - 停止并删除 docker-compose 启动的服务"

# ----------------------------
# 1. 设置开发环境 (虚拟环境 + 依赖)
# ----------------------------
setup:
	@echo "创建 Python 虚拟环境..."
	python3 -m venv $(VENV_DIR)
	@echo "激活虚拟环境并安装依赖..."
	@. $(VENV_DIR)/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@echo "复制示例配置文件为实际使用..."
	@cp .env.example .env || true
	@if [ -f conf.yaml.example ]; then cp conf.yaml.example conf.yaml || true; fi
	@echo "环境初始化完成，请编辑 .env 和 conf.yaml 后运行 make run 或 make docker-up。"

# ----------------------------
# 2. 启动后端服务
# ----------------------------
run:
	@echo "启动后端 FastAPI 服务..."
	@. $(VENV_DIR)/bin/activate && uvicorn src.main:app --reload

# ----------------------------
# 3. 启动前端 UI 服务（仅适用于项目有 Web 前端）
# ----------------------------
ui:
	@echo "启动前端 UI 服务..."
	@cd web && npm install && npm run dev

# ----------------------------
# 4. 运行单元测试
# ----------------------------
test:
	@echo "运行单元测试..."
	@. $(VENV_DIR)/bin/activate && pytest tests/ --maxfail=1 --disable-warnings -q

# ----------------------------
# 5. Docker Compose 启动
# ----------------------------
docker-up:
	@echo "使用 Docker Compose 启动后端与 Redis 服务..."
	docker-compose up --build -d

# ----------------------------
# 6. Docker Compose 停止
# ----------------------------
docker-down:
	@echo "停止并删除 Docker Compose 启动的服务..."
	docker-compose down