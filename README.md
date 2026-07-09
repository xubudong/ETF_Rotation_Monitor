# ETF 轮动行情监控台

## 安装依赖

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

如需使用 akshare EM 代理更新本地库，请在本机设置代理 token 环境变量：

```powershell
$env:AKSHARE_PROXY_TOKEN="你的代理token"
```

Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
```

如需使用 akshare EM 代理更新本地库，请在本机设置代理 token 环境变量：

```bash
export AKSHARE_PROXY_TOKEN="你的代理token"
```

## 启动

Windows:

```powershell
.\run_web.ps1
```

Linux:

```bash
chmod +x run_web.sh
./run_web.sh
```

默认访问 `http://127.0.0.1:8000`。

如需内网访问：

Windows:

```powershell
$env:WEB_HOST="0.0.0.0"
.\run_web.ps1
```

Linux:

```bash
WEB_HOST=0.0.0.0 ./run_web.sh
```

## 验证

```bash
python -m web_app.smoke_test
```

## 后端结构

`web_app/server.py` 现在只保留 FastAPI 路由和状态编排；核心逻辑拆到：

- `ranking.py`：读取池子、合并实时行情、本地历史库、评分与排名变化。
- `scoring.py`：轮动评分模型、评级规则和板块分类。
- `pools.py`：读取 `web_app/data/pools.json` 的 ETF 池配置。
- `storage.py`：SQLite 本地库、旧 CSV 兜底、两个账户持仓上传与状态。
- `cache_update.py`：点击按钮后的 akshare EM 本地库更新、代理补丁、进度和日志。
- `market_data.py`：腾讯/新浪/EM/yfinance 实时数据源适配。
- `tech_discovery.py`：活跃 ETF 扫描逻辑，更新 Web 版“活跃科技标的”池。

`A 股板块轮动` 和 `全球与大宗配置` 已移到 `web_app/data/pools.json`，可以直接删减代码和名称。`活跃科技标的` 也有内置配置，但页面点击 `更新科技池` 后会优先使用 `web_app/data/new_tech_pool.json`。

本地库更新按钮会先启用 `akshare_proxy_patch`，再通过 akshare 的东方财富 EM 接口更新 `web_app/data/etf_cache.sqlite`，只更新到前一交易日收盘数据，不写入当天盘中行情。页面每 5 秒显示进度；服务终端也会打印每个标的的更新日志。排名计算优先读取 SQLite，本地库没有该标的时兼容读取旧的 `etf_cache/*.csv`。

`A 股板块轮动` 和 `全球与大宗配置` 是两个独立账户。持仓不再通过券商 `table.xls` 上传维护，而是在排名表中手动勾选“持有”，并填写持仓市值，单位为“万”。保存后系统会按该账户全部持仓市值自动重算仓位占比；`活跃科技标的` 页面显示两个账户持仓并集，但不作为独立账户维护。排名表中的 `Top12` 列会标出相对上一交易日的新进前 12 和掉出前 12。
页面会常驻显示两个账户的今日涨跌幅。当前手动持仓模式优先使用持仓市值结合实时/缓存的当日涨跌幅估算账户今日盈亏；如果历史上传数据仍包含实际数量，则继续按 `持仓数量 × (实时最新价 - 昨收价)` 计算。单标的价格优先来自当前选择的实时数据源；实时缺失时回退到本地历史库最后两根 K 线。
排名表还会显示 `昨日排名` 和 `排名变化`，用于快速判断相对上一交易日的升降位。
页面顶部的 `更新科技池` 会通过 akshare 扫描全市场 ETF 实时列表，按成交额排序并按主题去重，然后写入 `web_app/data/new_tech_pool.json`。之后“活跃科技标的”Tab 会优先使用这个动态池；没有更新文件时回退到 `web_app/data/pools.json` 内置池。后续操作以 Web 页面为准，不再维护旧命令行流程。

## ETF 池配置

`web_app/data/pools.json` 是主要池子配置文件：
- `a_share`：A 股板块轮动账户，偏行业/主题 ETF。
- `global`：全球与大宗配置账户，定位为海外/跨市场/QDII 池，覆盖美股、港股/中概、日本、欧洲、巴西、商品与少量 A 股基准。
- `new_tech`：内置活跃科技池；页面点击“更新科技池”后，会优先读取 `web_app/data/new_tech_pool.json`。

新增或删除海外/QDII 标的时，直接编辑 `global` 对象即可，例如 `520870: 巴西ETF易方达`。新加入的标的需要点一次“更新本地库”，拿到截至前一交易日收盘的历史 K 线后才会进入完整评分和排名。


## Runtime, .env and service scripts

Create `.env` from `.env.example` when local secrets or runtime defaults are needed:

```text
AKSHARE_PROXY_TOKEN=your-token
WEB_HOST=127.0.0.1
WEB_PORT=8000
WEB_PORT_SCAN_LIMIT=30
```

Environment priority is: process environment > `.env` > code defaults. The real `.env` file is ignored by Git.

Windows:

```powershell
.\run_web.ps1              # background service
.\run_web.ps1 -Foreground  # foreground debug mode
.\stop_web.ps1             # stop by runtime/web.pid
```

Linux:

```bash
chmod +x run_web.sh stop_web.sh
./run_web.sh              # background service
./run_web.sh --foreground # foreground debug mode
./stop_web.sh             # stop by runtime/web.pid
```

Runtime PID and logs are written under `runtime/`, which is ignored by Git.
