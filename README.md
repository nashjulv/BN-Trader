# BN-Trader 本地短線交易系統

面向小白的本地單機版短線交易系統，支援幣安交易所主流幣交易。

## 支援平台

| 平台 | 狀態 |
|------|------|
| Windows 10/11 | ✅ 完整支援 |
| macOS (Intel / Apple Silicon) | ✅ 完整支援 |
| Linux (Ubuntu/Debian) | ✅ 完整支援 |

## 桌面安装包

GitHub Actions 会在手动触发时构建并保存 30 天，也会在推送 `v*` 标签时自动创建 Release：

- Windows x64：NSIS 安装程序 `.exe`、免安装便携版 `.zip`
- macOS Apple Silicon：拖拽安装镜像 `.dmg`、应用便携版 `.zip`

macOS 自动构建产物目前未签名，适合内部测试。正式公开分发需配置 Apple Developer ID 签名与公证。

升级、客户配置保留和旧版迁移规则详见 [软件升级与客户数据迁移](docs/升级与数据迁移.md)。

## 核心功能

- **智能場景識別**: 自動識別5種行情場景（趨勢、震盪、突破、反轉、極端）
- **資金池管理**: 智能倉位分配，資金回收與再投資
- **多層風控**: 單筆/日度/賬戶三層風控，強制復盤機制
- **自動交易**: 基於場景的策略自動執行
- **本地優先**: 數據本地存儲（SQLite），保護隱私

## 技術棧

- Python 3.10+
- PyQt6 (GUI) — 跨平台桌面框架
- SQLite (數據存儲) — 內建，無需額外安裝
- 幣安API (行情和交易)

---

## 快速開始

### 前置要求

- Python 3.10 或更高版本
- pip（Python 套件管理器）

檢查 Python 版本：
```bash
python --version    # Windows
python3 --version   # macOS / Linux
```

### 安裝方法

#### 方法一：一鍵安裝（推薦）

```bash
# 所有平台通用
python install.py
```

#### 方法二：平台特定腳本

**Windows:**
```batch
install.bat
```

**macOS / Linux:**
```bash
bash install.sh
```

#### 方法三：手動安裝

```bash
# 1. 建立虛擬環境
python -m venv .venv

# 2. 啟動虛擬環境
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 3. 安裝依賴
pip install -r requirements.txt
```

### 配置幣安 API（可選）

複製 `.env.example` 為 `.env`，填入你的幣安 API Key：

```
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
```

> **安全提示**: 建議使用幣安的「只讀 API Key」或設置交易權限限制。API Key 只存儲在本地 `.env` 文件中。

### 運行

```bash
# 啟動虛擬環境後
python main.py
```

---

## 目錄結構

```
BN-Trader/
├── main.py                  # 應用入口
├── config.py                # 配置中心
├── install.py               # 跨平台安裝腳本
├── install.sh               # macOS/Linux 安裝
├── install.bat              # Windows 安裝
├── requirements.txt         # Python 依賴
│
├── core/                    # 核心模塊
│   ├── app.py               # 應用主控類
│   └── database.py          # SQLite 數據庫
│
├── models/                  # 數據模型
│   ├── capital.py           # 資金模型
│   ├── trade.py             # 交易模型
│   ├── risk.py              # 風控模型
│   └── scene.py             # 場景模型
│
├── services/                # 業務邏輯
│   ├── binance_client.py    # 幣安 API 客戶端
│   ├── scene_detector.py    # 場景識別引擎
│   ├── capital_pool.py      # 資金池管理
│   ├── risk_manager.py      # 風控管理
│   └── strategy_engine.py   # 策略引擎
│
├── indicators/              # 技術指標
│   └── technical.py         # MA/MACD/RSI/布林帶/ATR/ADX
│
├── gui/                     # 界面組件
│   ├── main_window.py       # 主窗口
│   ├── chart_widget.py      # K線圖
│   ├── trade_panel.py       # 交易面板
│   ├── capital_panel.py     # 資金面板
│   ├── scene_panel.py       # 場景面板
│   ├── risk_panel.py        # 風控面板
│   ├── position_panel.py    # 持倉面板
│   ├── log_panel.py         # 日誌面板
│   ├── review_dialog.py     # 復盤對話框
│   └── styles.py            # 樣式定義
│
├── utils/                   # 工具
│   ├── logger.py            # 日誌
│   └── helpers.py           # 輔助函數
│
├── tests/                   # 測試
├── docs/                    # 培訓課件
└── .env.example             # 環境變數範例
```

---

## 培訓課件

詳見 `docs/` 目錄下的12課培訓文檔：

| 課號 | 主題 | 說明 |
|------|------|------|
| 01 | 環境搭建 | Python環境、依賴安裝、專案結構 |
| 02 | 幣安API | REST/WebSocket、數據獲取 |
| 03 | 技術指標 | MA/MACD/RSI/布林帶/ATR計算 |
| 04 | 場景識別 | 5種行情場景自動判別 |
| 05 | 資金池 | 倉位分配、資金回收 |
| 06 | 風控系統 | 多層風控、強制復盤 |
| 07 | 交易策略 | 趨勢/震盪/突破/反轉/極端 |
| 08 | 自動交易 | 信號生成、訂單執行 |
| 09 | 界面開發(上) | PyQt6佈局、K線圖 |
| 10 | 界面開發(下) | 交易面板、實時更新 |
| 11 | 數據持久化 | SQLite、CRUD操作 |
| 12 | 測試發布 | 單元測試、PyInstaller打包 |
