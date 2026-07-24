.PHONY: help start-dev install run test clean

# 自动检测 macOS/Linux 上的 python3
PYTHON := $(shell command -v python3 2>/dev/null || echo python)
VENV   := .venv
PIP    := $(VENV)/bin/pip
REQS   := requirements.txt

## —— 一键启动（开发模式）——————————————
# 自动创建虚拟环境、安装依赖、启动应用
start-dev: $(VENV) .env
	@echo "=== BN-Trader 启动中 ==="
	$(VENV)/bin/python main.py

## —— 安装依赖 —————————————————————————————
install: $(VENV)
	@echo "依赖已就绪"

$(VENV):
	@echo "创建虚拟环境..."
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip -q
	$(PIP) install -r $(REQS)
	@echo "安装完成 ✓"

## —— 配置文件 ——————————————————————————————
.env:
	@echo "生成默认 .env 配置文件..."
	cp .env.example .env
	@echo ".env 已创建（如需交易功能请填入币安 API Key）"

## —— 运行应用（跳过安装检查）————————————
run:
	$(VENV)/bin/python main.py

## —— 运行测试 —————————————————————————————
test: $(VENV)
	$(VENV)/bin/python -m pytest tests/ -v

## —— 清理 —————————————————————————————————
clean:
	rm -rf $(VENV) .pytest_cache __pycache__ */__pycache__ */*/__pycache__
	rm -rf build/ dist/ *.spec
	@echo "清理完成"

## —— 帮助 —————————————————————————————————
help:
	@echo "BN-Trader 开发命令:"
	@echo ""
	@echo "  make start-dev   一键启动（自动安装+运行）"
	@echo "  make install     仅安装依赖"
	@echo "  make run         直接运行（跳过安装检查）"
	@echo "  make test        运行全部测试"
	@echo "  make clean       清理虚拟环境和构建产物"
