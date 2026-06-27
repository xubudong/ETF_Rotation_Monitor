const columns = [
  { key: "排名", label: "#", type: "number" },
  { key: "代码", label: "代码", type: "text" },
  { key: "名称", label: "名称", type: "text" },
  { key: "持仓", label: "持仓", type: "text" },
  { key: "账户", label: "账户", type: "text" },
  { key: "仓位占比", label: "仓位", type: "holdPercent" },
  { key: "板块", label: "板块", type: "text" },
  { key: "昨日排名", label: "昨日", type: "number" },
  { key: "排名变化", label: "变化", type: "text" },
  { key: "动态预警", label: "观察区", type: "text" },
  { key: "评级", label: "评级", type: "text" },
  { key: "最新收盘价", label: "最新价", type: "price" },
  { key: "当日涨跌幅", label: "当日涨跌", type: "percent" },
  { key: "MA20", label: "MA20", type: "price" },
  { key: "价格>MA20", label: ">MA20", type: "text" },
  { key: "20日涨幅", label: "20日涨幅", type: "percent" },
  { key: "量比", label: "量比", type: "ratio" },
  { key: "动量得分", label: "动量", type: "score" },
  { key: "量能得分", label: "量能", type: "score" },
  { key: "趋势得分", label: "趋势", type: "score" },
  { key: "综合总分", label: "总分", type: "score" },
];

const state = {
  payload: null,
  config: null,
  portfolio: null,
  backtest: null,
  backtestRequest: null,
  rankingDate: null,
  activePool: "a_share",
  strategyId: null,
  sortKey: "综合总分",
  sortDir: "desc",
  timer: null,
};

const els = {
  statusText: document.querySelector("#statusText"),
  sourceSelect: document.querySelector("#sourceSelect"),
  strategySelect: document.querySelector("#strategySelect"),
  rankingDate: document.querySelector("#rankingDate"),
  historyRankingBtn: document.querySelector("#historyRankingBtn"),
  liveRankingBtn: document.querySelector("#liveRankingBtn"),
  intervalSelect: document.querySelector("#intervalSelect"),
  autoRefresh: document.querySelector("#autoRefresh"),
  refreshBtn: document.querySelector("#refreshBtn"),
  cacheBtn: document.querySelector("#cacheBtn"),
  techPoolBtn: document.querySelector("#techPoolBtn"),
  viewTabs: document.querySelector(".view-tabs"),
  monitorView: document.querySelector("#monitorView"),
  backtestView: document.querySelector("#backtestView"),
  cacheStatusPanel: document.querySelector("#cacheStatusPanel"),
  cacheStatusText: document.querySelector("#cacheStatusText"),
  techPoolStatusPanel: document.querySelector("#techPoolStatusPanel"),
  techPoolStatusText: document.querySelector("#techPoolStatusText"),
  aShareTodayChange: document.querySelector("#aShareTodayChange"),
  aShareTodayPnl: document.querySelector("#aShareTodayPnl"),
  globalTodayChange: document.querySelector("#globalTodayChange"),
  globalTodayPnl: document.querySelector("#globalTodayPnl"),
  tabs: document.querySelector("#tabs"),
  searchInput: document.querySelector("#searchInput"),
  ratingFilter: document.querySelector("#ratingFilter"),
  holdOnly: document.querySelector("#holdOnly"),
  buyOnly: document.querySelector("#buyOnly"),
  aShareHoldFile: document.querySelector("#aShareHoldFile"),
  aShareHoldBtn: document.querySelector("#aShareHoldBtn"),
  globalHoldFile: document.querySelector("#globalHoldFile"),
  globalHoldBtn: document.querySelector("#globalHoldBtn"),
  summaryGrid: document.querySelector("#summaryGrid"),
  backtestPoolSelect: document.querySelector("#backtestPoolSelect"),
  backtestStrategySelect: document.querySelector("#backtestStrategySelect"),
  backtestExecutionMode: document.querySelector("#backtestExecutionMode"),
  backtestMonths: document.querySelector("#backtestMonths"),
  backtestCustomRange: document.querySelector("#backtestCustomRange"),
  backtestStartDate: document.querySelector("#backtestStartDate"),
  backtestEndDate: document.querySelector("#backtestEndDate"),
  backtestBenchmark: document.querySelector("#backtestBenchmark"),
  backtestBtn: document.querySelector("#backtestBtn"),
  backtestExportBtn: document.querySelector("#backtestExportBtn"),
  backtestFullscreenBtn: document.querySelector("#backtestFullscreenBtn"),
  backtestStatus: document.querySelector("#backtestStatus"),
  backtestMetrics: document.querySelector("#backtestMetrics"),
  backtestChart: document.querySelector("#backtestChart"),
  backtestRebalanceBody: document.querySelector("#backtestRebalanceBody"),
  portfolioPoolSelect: document.querySelector("#portfolioPoolSelect"),
  portfolioRefreshBtn: document.querySelector("#portfolioRefreshBtn"),
  portfolioStatus: document.querySelector("#portfolioStatus"),
  portfolioMetrics: document.querySelector("#portfolioMetrics"),
  portfolioBars: document.querySelector("#portfolioBars"),
  portfolioDetailBody: document.querySelector("#portfolioDetailBody"),
  tableTitle: document.querySelector("#tableTitle"),
  rowCount: document.querySelector("#rowCount"),
  tableHead: document.querySelector("#tableHead"),
  tableBody: document.querySelector("#tableBody"),
};

function fmt(value, type) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (type === "percent" && Number.isFinite(num)) return `${(num * 100).toFixed(2)}%`;
  if (type === "holdPercent" && Number.isFinite(num)) return `${num.toFixed(2)}%`;
  if (type === "price" && Number.isFinite(num)) return num.toFixed(3);
  if (type === "ratio" && Number.isFinite(num)) return num.toFixed(2);
  if (type === "score" && Number.isFinite(num)) return num.toFixed(1);
  return String(value);
}

function fmtMoney(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  if (Math.abs(num) >= 100000000) return `${(num / 100000000).toFixed(2)}亿`;
  if (Math.abs(num) >= 10000) return `${(num / 10000).toFixed(2)}万`;
  return num.toFixed(2);
}

function fmtPct(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  return `${(num * 100).toFixed(2)}%`;
}

function signedPct(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  const sign = num > 0 ? "+" : "";
  return `${sign}${(num * 100).toFixed(2)}%`;
}

function signedMoney(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "-";
  const sign = num > 0 ? "+" : "";
  return `${sign}${fmtMoney(num)}`;
}

function ratingClass(rating) {
  if (rating === "买入配仓") return "rating-buy";
  if (rating === "持有观察") return "rating-hold";
  if (rating === "空仓回避") return "rating-avoid";
  return "rating-neutral";
}

function setStatus(text, tone = "") {
  els.statusText.textContent = text;
  els.statusText.className = `status-line ${tone}`;
}

function describeCacheStatus(status) {
  if (!status) return "";
  const progress = status.progress || {};
  if (status.updating) {
    const percent = Number.isFinite(Number(progress.percent)) ? `${Number(progress.percent).toFixed(1)}%` : "-";
    const current = progress.current_code ? `，当前 ${progress.current_code} ${progress.current_name || ""}` : "";
    return `，本地库 EM 增量更新中 ${percent}（${progress.current || 0}/${progress.total || 0}，更新 ${progress.success || 0}，跳过 ${progress.skipped || 0}，失败 ${progress.failed || 0}${current}）`;
  }
  if (status.result) {
    const result = status.result;
    const stats = status.stats || result.cache_stats || {};
    const cached = stats.symbols ? `，已缓存 ${stats.symbols} 个标的至 ${stats.max_date || "-"}` : "";
    return `，本地库 ${result.finished_at || status.finished || ""} 完成：更新 ${result.success || 0}，跳过 ${result.skipped || 0}/${result.total || 0}，失败 ${result.failed || 0}${cached}`;
  }
  if (status.last_error) return `，本地库更新失败：${status.last_error}`;
  if (status.stats?.symbols) return `，本地库已缓存 ${status.stats.symbols} 个标的至 ${status.stats.max_date || "-"}`;
  return "";
}

function renderCacheStatus(status) {
  const stats = status?.stats || status?.result?.cache_stats || state.config?.cache_stats || {};
  const isUpdating = Boolean(status?.updating);
  const target = stats.target_date || "-";
  const maxDate = stats.max_date || stats.fallback_csv_max_date || "-";
  const symbols = stats.symbols || stats.fallback_csv_symbols || 0;
  const targetSymbols = stats.target_symbols || state.config?.cache_stats?.target_symbols || 0;
  const currentSymbols = stats.up_to_date_symbols || 0;
  const isCurrent = Boolean(stats.up_to_date);

  let tone = "warn";
  let text = `目标前一交易日 ${target}，当前最新 ${maxDate}，覆盖 ${symbols}/${targetSymbols || "-"} 个标的`;
  if (isUpdating) {
    tone = "working";
    const progress = status.progress || {};
    text = `增量更新中 ${Number(progress.percent || 0).toFixed(1)}%，${progress.current || 0}/${progress.total || 0}，更新 ${progress.success || 0}，跳过 ${progress.skipped || 0}，失败 ${progress.failed || 0}`;
    if (progress.current_code) text += `，当前 ${progress.current_code} ${progress.current_name || ""}`;
  } else if (isCurrent) {
    tone = "ok";
    text += `，已更新到前一交易日`;
  } else if (symbols > 0) {
    text += `，到期标的 ${currentSymbols}/${targetSymbols || symbols}`;
  } else {
    text = `本地库暂无数据，目标前一交易日 ${target}`;
  }

  els.cacheStatusPanel.className = `cache-status-panel ${tone}`;
  els.cacheStatusText.textContent = text;
}

function renderTechPoolStatus(status) {
  const updating = Boolean(status?.updating);
  const override = status?.override;
  let tone = "warn";
  let text = "仍使用 pools.json 内置活跃科技标的池";

  if (updating) {
    tone = "working";
    text = `正在通过 akshare 扫描并更新活跃科技标的池，开始于 ${status.started || "-"}`;
  } else if (status?.last_error) {
    text = `更新失败：${status.last_error}`;
  } else if (override) {
    tone = "ok";
    text = `已覆盖 ${override.count} 个标的，更新至 ${override.updated_at || "-"}，来源 ${override.source || "-"}`;
  }

  els.techPoolStatusPanel.className = `cache-status-panel tech-pool-status-panel ${tone}`;
  els.techPoolStatusText.textContent = text;
}

async function loadConfig() {
  const res = await fetch("/api/config");
  state.config = await res.json();
  els.sourceSelect.innerHTML = state.config.sources
    .map((source) => `<option value="${source}">${source}</option>`)
    .join("");
  els.sourceSelect.value = state.config.default_source;
  const scoring = state.config.scoring || {};
  state.strategyId = state.strategyId || scoring.default_strategy || "";
  const strategyOptions = (scoring.strategies || [])
    .map((item) => `<option value="${item.id}">${item.name}</option>`)
    .join("");
  els.strategySelect.innerHTML = strategyOptions;
  els.backtestStrategySelect.innerHTML = strategyOptions;
  els.strategySelect.value = state.strategyId;
  els.backtestStrategySelect.value = state.strategyId;
  els.backtestBenchmark.innerHTML = (state.config.benchmarks || [])
    .map((item) => `<option value="${item.code}">${item.name} ${item.code}</option>`)
    .join("");
  if (els.backtestBenchmark.querySelector('option[value="510300"]')) els.backtestBenchmark.value = "510300";
  renderTabs();
  renderCacheStatus({ stats: state.config.cache_stats });
  renderTechPoolStatus(state.config.tech_pool);
}

async function loadHoldingsStatus() {
  try {
    const res = await fetch("/api/holdings/status");
    state.config.holdings = await res.json();
  } catch {}
}

function setAccountChangeNode(changeEl, pnlEl, account) {
  const ret = account?.return_1d;
  const pnl = account?.today_pnl;
  changeEl.textContent = signedPct(ret);
  changeEl.className = Number(ret) > 0 ? "positive" : Number(ret) < 0 ? "negative" : "";
  pnlEl.textContent = account?.holdings
    ? `${signedMoney(pnl)} / 覆盖 ${account.covered}/${account.holdings}`
    : "暂无持仓";
}

async function loadAccountTodayChange() {
  try {
    const source = els.sourceSelect.value || state.config?.default_source || "tencent";
    const res = await fetch(`/api/accounts/today-change?source=${encodeURIComponent(source)}`);
    if (!res.ok) throw new Error(await res.text());
    const payload = await res.json();
    setAccountChangeNode(els.aShareTodayChange, els.aShareTodayPnl, payload.accounts?.a_share);
    setAccountChangeNode(els.globalTodayChange, els.globalTodayPnl, payload.accounts?.global);
  } catch (error) {
    els.aShareTodayChange.textContent = "-";
    els.globalTodayChange.textContent = "-";
    els.aShareTodayPnl.textContent = `读取失败：${error.message}`;
    els.globalTodayPnl.textContent = `读取失败：${error.message}`;
  }
}

function renderTabs() {
  if (!state.config) return;
  els.tabs.innerHTML = Object.entries(state.config.pools)
    .map(([key, title]) => {
      const active = key === state.activePool ? "active" : "";
      return `<button class="${active}" type="button" data-pool="${key}">${title}</button>`;
    })
    .join("");
}

async function loadRankings(refresh = false) {
  const source = els.sourceSelect.value || "tencent";
  const strategy = els.strategySelect.value || state.strategyId || "";
  state.strategyId = strategy;
  const asOfParam = state.rankingDate ? `&as_of=${encodeURIComponent(state.rankingDate)}` : "";
  const url = `/api/rankings?source=${encodeURIComponent(source)}&refresh=${refresh && !state.rankingDate ? "true" : "false"}&strategy_id=${encodeURIComponent(strategy)}${asOfParam}`;
  els.refreshBtn.disabled = true;
  setStatus(state.rankingDate ? `正在读取 ${state.rankingDate} 的收盘打分...` : refresh ? "正在刷新行情..." : "正在加载排名...");
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(await apiErrorMessage(res));
    state.payload = await res.json();
    const errors = state.payload.errors || [];
    let sourceText = state.payload.mode === "historical"
      ? `历史收盘打分：${state.payload.as_of_date}${state.payload.requested_as_of_date !== state.payload.as_of_date ? `（所选 ${state.payload.requested_as_of_date}）` : ""}`
      : state.payload.from_cache
      ? `兜底数据：${state.payload.report_file || state.payload.source}`
      : `数据源：${state.payload.source}`;
    if (state.payload.strategy_id) {
      const option = els.strategySelect.querySelector(`option[value="${state.payload.strategy_id}"]`);
      if (option) sourceText += `，策略：${option.textContent}`;
    }
    const marketState = state.payload.market_state;
    if (marketState?.enabled) {
      sourceText += marketState.available
        ? `，大盘：${marketState.status}，${marketState.signal_summary || ""}，仓位${(Number(marketState.position_ratio || 1) * 10).toFixed(1)}成`
        : `，大盘过滤不可用：${marketState.message || "-"}`;
    }
    const errorText = errors.length ? `，提示 ${errors.length} 条` : "";
    let cacheSuffix = "";
    try {
      const cacheRes = await fetch("/api/cache/status");
      const cacheStatus = await cacheRes.json();
      cacheSuffix = describeCacheStatus(cacheStatus);
      renderCacheStatus(cacheStatus);
    } catch {}
    const timeText = state.payload.mode === "historical" ? "，基于本地收盘库计算" : `，更新时间 ${state.payload.generated_at}`;
    setStatus(`${sourceText}${timeText}${errorText}${cacheSuffix}`, errors.length ? "warn" : "ok");
    render();
    if (!state.rankingDate) await loadAccountTodayChange();
  } catch (error) {
    setStatus(`加载失败：${error.message}`, "error");
  } finally {
    els.refreshBtn.disabled = false;
  }
}

async function pollCacheStatus() {
  try {
    const res = await fetch("/api/cache/status");
    const status = await res.json();
    els.cacheBtn.disabled = Boolean(status.updating);
    renderCacheStatus(status);
    if (state.rankingDate) {
      if (status.updating) {
        window.setTimeout(pollCacheStatus, 5000);
      } else if (status.result) {
        await loadRankings(false);
      }
      return;
    }
    const suffix = describeCacheStatus(status);
    if (suffix) {
      const base = state.payload
        ? `数据源：${state.payload.source}，更新时间 ${state.payload.generated_at}`
        : "排名数据尚未加载";
      setStatus(`${base}${suffix}`, status.last_error ? "warn" : "ok");
    }
    if (status.updating) {
      window.setTimeout(pollCacheStatus, 5000);
    } else if (status.result) {
      await loadRankings(true);
    }
  } catch (error) {
    setStatus(`缓存状态读取失败：${error.message}`, "error");
    els.cacheBtn.disabled = false;
  }
}

async function triggerCacheUpdate() {
  els.cacheBtn.disabled = true;
  setStatus("已提交本地库 EM 更新...");
  try {
    const res = await fetch("/api/cache/update", { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const payload = await res.json();
    if (!payload.accepted && payload.updating) {
      setStatus("本地库 EM 更新已在运行中...", "warn");
    }
    window.setTimeout(pollCacheStatus, 1500);
  } catch (error) {
    setStatus(`缓存更新提交失败：${error.message}`, "error");
    els.cacheBtn.disabled = false;
  }
}

async function pollTechPoolStatus() {
  try {
    const res = await fetch("/api/tech-pool/status");
    const status = await res.json();
    els.techPoolBtn.disabled = Boolean(status.updating);
    renderTechPoolStatus(status);
    if (status.updating) {
      window.setTimeout(pollTechPoolStatus, 3000);
    } else if (status.result) {
      await loadConfig();
      await loadRankings(true);
      setStatus(`活跃科技标的池已更新：${status.result.count} 个标的`, "ok");
    }
  } catch (error) {
    setStatus(`科技池状态读取失败：${error.message}`, "error");
    els.techPoolBtn.disabled = false;
  }
}

async function triggerTechPoolUpdate() {
  els.techPoolBtn.disabled = true;
  setStatus("已提交活跃科技标的池更新...");
  try {
    const res = await fetch("/api/tech-pool/update?top_n=100", { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const payload = await res.json();
    if (!payload.accepted && payload.updating) {
      setStatus("活跃科技标的池更新已在运行中...", "warn");
    }
    window.setTimeout(pollTechPoolStatus, 1200);
  } catch (error) {
    setStatus(`科技池更新提交失败：${error.message}`, "error");
    els.techPoolBtn.disabled = false;
  }
}

async function uploadHoldings(poolKey, fileInput) {
  const file = fileInput.files?.[0];
  if (!file) {
    setStatus("请先选择 table.xls 持仓文件", "warn");
    fileInput.click();
    return;
  }
  setStatus(`正在上传${state.config?.pools?.[poolKey] || poolKey}持仓...`);
  try {
    const body = await file.arrayBuffer();
    const res = await fetch(`/api/holdings/${poolKey}/upload?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body,
    });
    if (!res.ok) throw new Error(await res.text());
    const result = await res.json();
    await loadHoldingsStatus();
    await loadRankings(true);
    await loadAccountTodayChange();
    if (els.portfolioPoolSelect.value === poolKey || els.portfolioPoolSelect.value === "all") {
      await loadPortfolioAnalysis();
    }
    setStatus(`${state.config.pools[poolKey]}持仓已更新：${result.count} 个标的，${result.updated_at}`, "ok");
  } catch (error) {
    setStatus(`持仓上传失败：${error.message}`, "error");
  } finally {
    fileInput.value = "";
  }
}

function syncPortfolioPoolWithActiveTab() {
  if (state.activePool === "a_share" || state.activePool === "global") {
    els.portfolioPoolSelect.value = state.activePool;
  } else {
    els.portfolioPoolSelect.value = "all";
  }
}

async function loadPortfolioAnalysis() {
  const poolKey = els.portfolioPoolSelect.value || "all";
  els.portfolioRefreshBtn.disabled = true;
  els.portfolioStatus.textContent = "正在计算行业穿透...";
  try {
    const res = await fetch(`/api/portfolio/analysis?pool_key=${encodeURIComponent(poolKey)}`);
    if (!res.ok) throw new Error(await res.text());
    state.portfolio = await res.json();
    renderPortfolio();
  } catch (error) {
    els.portfolioStatus.textContent = `组合诊断失败：${error.message}`;
    els.portfolioMetrics.innerHTML = "";
    els.portfolioBars.innerHTML = "";
    els.portfolioDetailBody.innerHTML = "";
  } finally {
    els.portfolioRefreshBtn.disabled = false;
  }
}

function renderPortfolio() {
  const payload = state.portfolio;
  if (!payload || !payload.holdings_count) {
    els.portfolioStatus.textContent = "暂无可诊断持仓，请先上传对应账户的 table.xls。";
    els.portfolioMetrics.innerHTML = "";
    els.portfolioBars.innerHTML = "";
    els.portfolioDetailBody.innerHTML = "";
    return;
  }

  els.portfolioStatus.textContent = `${payload.title}，${payload.generated_at}，行业字典：${payload.source_file}`;
  els.portfolioMetrics.innerHTML = [
    ["总市值", fmtMoney(payload.total_value)],
    ["持仓数", payload.holdings_count],
    ["已映射", payload.mapped_count],
    ["未映射", payload.unmapped_count],
    ["Top3集中度", fmtPct(payload.top3_weight)],
    ["Top5集中度", fmtPct(payload.top5_weight)],
  ]
    .map(([label, value]) => `<div class="portfolio-metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");

  const topIndustries = (payload.primary || []).slice(0, 10);
  els.portfolioBars.innerHTML = topIndustries
    .map((row) => {
      const width = Math.max(2, Math.min(100, Number(row["组合占比"] || 0) * 100));
      return `
        <div class="portfolio-bar-row">
          <div class="portfolio-bar-label">
            <strong>${row["行业"]}</strong>
            <span>${fmtMoney(row["穿透金额"])} / ${fmtPct(row["组合占比"])}</span>
          </div>
          <div class="portfolio-bar-track"><span style="width:${width}%"></span></div>
        </div>
      `;
    })
    .join("");

  els.portfolioDetailBody.innerHTML = (payload.details || [])
    .slice(0, 80)
    .map(
      (row) => `
        <tr>
          <td>${row["申万一级行业"]}</td>
          <td>${row["申万二级细分"]}</td>
          <td>${row["代码"]}</td>
          <td>${row["名称"]}</td>
          <td class="numeric">${fmtMoney(row["穿透金额"])}</td>
          <td class="numeric">${fmtPct(row["组合占比"])}</td>
        </tr>
      `,
    )
    .join("");
}

function switchView(view) {
  const isBacktest = view === "backtest";
  els.monitorView.classList.toggle("active", !isBacktest);
  els.backtestView.classList.toggle("active", isBacktest);
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
}

function drawBacktestChart(curve) {
  const chart = els.backtestChart;
  chart.innerHTML = "";
  if (!curve?.length) return;
  const benchmarkKey = `benchmark_${state.backtest?.benchmark?.code}`;
  const dates = curve.map((row) => row.date);
  const pct = (key) => curve.map((row) => (Number.isFinite(Number(row[key])) ? Number(row[key]) * 100 : null));
  const traces = [
    {
      type: "scatter",
      mode: "lines",
      name: "策略收益",
      x: dates,
      y: pct("return"),
      line: { color: "#c9302c", width: 2.4 },
      hovertemplate: "%{x}<br>策略收益 %{y:.2f}%<extra></extra>",
      xaxis: "x",
      yaxis: "y",
    },
  ];
  if (curve.some((row) => Number.isFinite(Number(row[benchmarkKey])))) {
    traces.push({
      type: "scatter",
      mode: "lines",
      name: "基准收益",
      x: dates,
      y: pct(benchmarkKey),
      line: { color: "#1d5fd1", width: 1.9 },
      hovertemplate: "%{x}<br>基准收益 %{y:.2f}%<extra></extra>",
      xaxis: "x",
      yaxis: "y",
    });
  }
  traces.push({
    type: "scatter",
    mode: "lines",
    name: "策略回撤",
    x: dates,
    y: pct("drawdown"),
    fill: "tozeroy",
    line: { color: "#7a8699", width: 1.5 },
    fillcolor: "rgba(122, 134, 153, 0.18)",
    hovertemplate: "%{x}<br>回撤 %{y:.2f}%<extra></extra>",
    xaxis: "x2",
    yaxis: "y2",
  });
  const layout = {
    autosize: true,
    margin: { l: 58, r: 24, t: 28, b: 42 },
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#ffffff",
    hovermode: "x unified",
    dragmode: "pan",
    legend: { orientation: "h", x: 0, y: 1.12, font: { size: 12 } },
    xaxis: {
      domain: [0, 1],
      anchor: "y",
      showgrid: true,
      gridcolor: "#e6edf5",
      rangeslider: { visible: true, thickness: 0.06 },
      rangeselector: {
        buttons: [
          { count: 3, label: "3月", step: "month", stepmode: "backward" },
          { count: 6, label: "6月", step: "month", stepmode: "backward" },
          { count: 1, label: "1年", step: "year", stepmode: "backward" },
          { step: "all", label: "全部" },
        ],
      },
    },
    yaxis: {
      domain: [0.34, 1],
      title: "收益率",
      ticksuffix: "%",
      showgrid: true,
      zeroline: true,
      gridcolor: "#e6edf5",
      zerolinecolor: "#c8d2df",
    },
    xaxis2: {
      domain: [0, 1],
      anchor: "y2",
      matches: "x",
      showgrid: true,
      gridcolor: "#e6edf5",
    },
    yaxis2: {
      domain: [0, 0.22],
      title: "回撤",
      ticksuffix: "%",
      showgrid: true,
      gridcolor: "#e6edf5",
      zeroline: true,
      zerolinecolor: "#c8d2df",
    },
  };
  const config = {
    responsive: true,
    displaylogo: false,
    scrollZoom: true,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
    toImageButtonOptions: { format: "png", filename: "backtest_curve", scale: 2 },
  };
  if (!window.Plotly) {
    chart.innerHTML = '<div class="chart-fallback">Plotly 静态文件未加载，无法显示交互图表。</div>';
    return;
  }
  window.Plotly.newPlot(chart, traces, layout, config);
}

function renderBacktest() {
  const payload = state.backtest;
  if (!payload) return;
  const metrics = payload.metrics || {};
  const coverage = payload.data_coverage || {};
  const firstTrade = coverage.first_trade_date || "-";
  const marketText = payload.market_state?.enabled && payload.market_state.available
    ? `，大盘${payload.market_state.status}，${payload.market_state.signal_summary || ""}，仓位${(Number(payload.market_state.position_ratio || 1) * 10).toFixed(1)}成`
    : "";
  els.backtestStatus.textContent = `${payload.generated_at}，${payload.strategy?.name || payload.strategy?.id}，${payload.execution_mode_name || "次日开盘成交"}${marketText}，${payload.benchmark?.name || payload.benchmark?.code}，正式区间 ${coverage.actual_start_date || "-"} 至 ${coverage.actual_end_date || payload.curve?.at(-1)?.date || "-"}，首笔交易 ${firstTrade}，交易日 ${metrics.trading_days || 0}`;
  els.backtestMetrics.innerHTML = [
    ["最终资产", fmtMoney(metrics.final_value)],
    ["累计收益", fmtPct(metrics.total_return)],
    ["年化收益", fmtPct(metrics.annualized_return)],
    ["最大回撤", fmtPct(metrics.max_drawdown)],
    ["基准收益", fmtPct(metrics.benchmark_return)],
    ["Alpha", fmtPct(metrics.alpha)],
    ["覆盖标的", metrics.symbols ?? "-"],
  ]
    .map(([label, value]) => `<div class="backtest-metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
  drawBacktestChart(payload.curve || []);
  const summaryRows = payload.symbol_performance || [];
  els.backtestRebalanceBody.innerHTML = summaryRows.length
    ? summaryRows
    .map(
      (row) => `
        <tr>
          <td>${row.code}</td>
          <td>${row.name}</td>
          <td>${row.status}</td>
          <td class="numeric">${row.buy_count || 0} / ${row.sell_count || 0}</td>
          <td class="numeric">${fmtMoney(row.buy_amount)}</td>
          <td class="numeric">${fmtMoney(row.sell_amount)}</td>
          <td class="numeric">${fmtMoney(row.market_value)}</td>
          <td class="numeric ${Number(row.profit) > 0 ? "positive" : Number(row.profit) < 0 ? "negative" : ""}">${signedMoney(row.profit)}</td>
          <td class="numeric ${Number(row.profit_pct) > 0 ? "positive" : Number(row.profit_pct) < 0 ? "negative" : ""}">${signedPct(row.profit_pct)}</td>
        </tr>
      `,
    )
    .join("")
    : '<tr><td colspan="9" class="muted">区间内没有成交记录</td></tr>';
}

function toggleBacktestCustomRange() {
  const isCustom = els.backtestMonths.value === "custom";
  els.backtestCustomRange.classList.toggle("hidden", !isCustom);
  if (!isCustom || els.backtestStartDate.value) return;
  const endText = state.config?.cache_stats?.max_date || new Date().toISOString().slice(0, 10);
  const start = new Date(`${endText}T00:00:00`);
  start.setFullYear(start.getFullYear() - 1);
  const localDate = (date) => [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
  els.backtestStartDate.value = localDate(start);
  els.backtestEndDate.value = endText;
}

function buildBacktestRequest() {
  const isCustom = els.backtestMonths.value === "custom";
  if (isCustom && !els.backtestStartDate.value) throw new Error("请选择自定义回测的开始日期");
  return {
    pool_key: els.backtestPoolSelect.value || state.activePool || "a_share",
    strategy_id: els.backtestStrategySelect.value || els.strategySelect.value || state.strategyId,
    months: isCustom ? null : Number(els.backtestMonths.value || 12),
    start_date: isCustom ? els.backtestStartDate.value : null,
    end_date: isCustom ? (els.backtestEndDate.value || null) : null,
    benchmark_code: els.backtestBenchmark.value || "510300",
    execution_mode: els.backtestExecutionMode.value || "next_open",
    initial_capital: 200000,
  };
}

async function apiErrorMessage(response) {
  const text = await response.text();
  try {
    const payload = JSON.parse(text);
    return payload.detail || text;
  } catch (error) {
    return text || `请求失败（HTTP ${response.status}）`;
  }
}

async function runBacktest() {
  let payload;
  try {
    payload = buildBacktestRequest();
  } catch (error) {
    els.backtestStatus.textContent = error.message;
    return;
  }
  els.backtestBtn.disabled = true;
  els.backtestExportBtn.disabled = true;
  els.backtestStatus.textContent = "正在回测...";
  try {
    const res = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await apiErrorMessage(res));
    state.backtest = await res.json();
    state.backtestRequest = payload;
    els.backtestExportBtn.disabled = false;
    renderBacktest();
  } catch (error) {
    els.backtestStatus.textContent = `回测失败：${error.message}`;
    els.backtestMetrics.innerHTML = "";
    els.backtestChart.innerHTML = "";
    els.backtestRebalanceBody.innerHTML = "";
  } finally {
    els.backtestBtn.disabled = false;
  }
}

async function exportBacktestDetails() {
  if (!state.backtestRequest) return;
  els.backtestExportBtn.disabled = true;
  els.backtestStatus.textContent = "正在生成回测明细文件...";
  try {
    const res = await fetch("/api/backtest/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.backtestRequest),
    });
    if (!res.ok) throw new Error(await apiErrorMessage(res));
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const filename = disposition.match(/filename="([^"]+)"/)?.[1] || "backtest_details.xlsx";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
    els.backtestStatus.textContent = "回测明细已导出，页面仍显示标的最终盈亏汇总。";
  } catch (error) {
    els.backtestStatus.textContent = `导出失败：${error.message}`;
  } finally {
    els.backtestExportBtn.disabled = false;
  }
}

function chooseHoldingsFile(fileInput) {
  fileInput.click();
}

async function triggerBackgroundRefresh() {
  if (state.rankingDate) {
    await loadRankings(false);
    return;
  }
  const source = els.sourceSelect.value || "tencent";
  const strategy = els.strategySelect.value || state.strategyId || "";
  els.refreshBtn.disabled = true;
  setStatus("已提交后台刷新...");
  try {
    await fetch(`/api/refresh?source=${encodeURIComponent(source)}&strategy_id=${encodeURIComponent(strategy)}`, { method: "POST" });
    window.setTimeout(() => loadRankings(false), 2500);
  } catch (error) {
    setStatus(`刷新提交失败：${error.message}`, "error");
  } finally {
    window.setTimeout(() => {
      els.refreshBtn.disabled = false;
    }, 2500);
  }
}

function getRows() {
  const group = state.payload?.pools?.[state.activePool];
  if (!group) return [];
  const query = els.searchInput.value.trim().toLowerCase();
  const rating = els.ratingFilter.value;

  let rows = group.rows || [];
  rows = rows.filter((row) => {
    const searchable = `${row["代码"] || ""} ${row["名称"] || ""} ${row["板块"] || ""}`.toLowerCase();
    if (query && !searchable.includes(query)) return false;
    if (rating && row["评级"] !== rating) return false;
    if (els.holdOnly.checked && !row["持仓"]) return false;
    if (els.buyOnly.checked && row["评级"] !== "买入配仓") return false;
    return true;
  });

  rows = [...rows].sort((a, b) => {
    const av = a[state.sortKey];
    const bv = b[state.sortKey];
    const an = Number(av);
    const bn = Number(bv);
    let result;
    if (Number.isFinite(an) && Number.isFinite(bn)) result = an - bn;
    else result = String(av ?? "").localeCompare(String(bv ?? ""), "zh-CN");
    return state.sortDir === "asc" ? result : -result;
  });
  return rows;
}

function renderSummary() {
  const groups = state.payload?.pools || {};
  els.summaryGrid.innerHTML = Object.entries(groups)
    .map(([key, group]) => {
      const rows = group.rows || [];
      const buys = rows.filter((row) => row["评级"] === "买入配仓").length;
      const holds = rows.filter((row) => row["持仓"]).length;
      const holdStatus = state.config?.holdings?.[key];
      const top = rows[0];
      const holdText = holdStatus ? `账户 ${holdStatus.count} / ${holdStatus.updated_at || "未上传"}` : `持仓 ${holds}`;
      return `
        <button class="summary-card ${key === state.activePool ? "active" : ""}" type="button" data-pool="${key}">
          <span>${group.title}</span>
          <strong>${rows.length}</strong>
          <small>买入 ${buys} / ${holdText}</small>
          <em>${top ? `${top["代码"]} ${top["名称"]}` : "暂无数据"}</em>
        </button>
      `;
    })
    .join("");
}

function renderTableHead() {
  els.tableHead.innerHTML = columns
    .map((col) => {
      const active = col.key === state.sortKey ? `sorted ${state.sortDir}` : "";
      return `<th class="${active}" data-sort="${col.key}">${col.label}</th>`;
    })
    .join("");
}

function renderTableBody(rows) {
  els.tableBody.innerHTML = rows
    .map((row) => {
      const trClass = row["持仓"] ? "holding-row" : "";
      const cells = columns
        .map((col) => {
          const value = row[col.key];
          const numeric = ["number", "percent", "holdPercent", "price", "ratio", "score"].includes(col.type) ? "numeric" : "";
          const sign = col.type === "percent" && Number(value) > 0 ? "positive" : col.type === "percent" && Number(value) < 0 ? "negative" : "";
          if (col.key === "评级") {
            return `<td><span class="rating ${ratingClass(value)}">${fmt(value, col.type)}</span></td>`;
          }
          if (col.key === "动态预警" && value) {
            return `<td><span class="alert-chip">${fmt(value, col.type)}</span></td>`;
          }
          return `<td class="${numeric} ${sign}">${fmt(value, col.type)}</td>`;
        })
        .join("");
      return `<tr class="${trClass}">${cells}</tr>`;
    })
    .join("");
}

function render() {
  renderTabs();
  renderSummary();
  renderTableHead();
  const group = state.payload?.pools?.[state.activePool];
  const rows = getRows();
  els.tableTitle.textContent = group?.title || "排名";
  els.rowCount.textContent = `${rows.length} 条`;
  renderTableBody(rows);
}

function resetTimer() {
  if (state.timer) window.clearInterval(state.timer);
  if (!els.autoRefresh.checked || state.rankingDate) return;
  const ms = Number(els.intervalSelect.value || 180) * 1000;
  state.timer = window.setInterval(() => loadRankings(true), ms);
}

function invalidateBacktestExport() {
  state.backtestRequest = null;
  els.backtestExportBtn.disabled = true;
}

async function showHistoricalRankings() {
  if (!els.rankingDate.value) {
    setStatus("请先选择需要核对的历史日期", "warn");
    return;
  }
  state.rankingDate = els.rankingDate.value;
  els.sourceSelect.disabled = true;
  els.liveRankingBtn.disabled = false;
  els.autoRefresh.checked = false;
  resetTimer();
  await loadRankings(false);
}

async function showRealtimeRankings() {
  state.rankingDate = null;
  els.rankingDate.value = "";
  els.sourceSelect.disabled = false;
  els.liveRankingBtn.disabled = true;
  resetTimer();
  await loadRankings(true);
}

document.addEventListener("click", (event) => {
  const viewTab = event.target.closest("[data-view]");
  if (viewTab) {
    switchView(viewTab.dataset.view);
    return;
  }
  const tab = event.target.closest("[data-pool]");
  if (tab) {
    state.activePool = tab.dataset.pool;
    syncPortfolioPoolWithActiveTab();
    if (els.backtestPoolSelect.querySelector(`option[value="${state.activePool}"]`)) {
      els.backtestPoolSelect.value = state.activePool;
      invalidateBacktestExport();
    }
    render();
    loadPortfolioAnalysis();
    return;
  }
  const th = event.target.closest("th[data-sort]");
  if (th) {
    const key = th.dataset.sort;
    if (state.sortKey === key) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
    else {
      state.sortKey = key;
      state.sortDir = key === "排名" ? "asc" : "desc";
    }
    render();
  }
});

els.refreshBtn.addEventListener("click", () => triggerBackgroundRefresh());
els.historyRankingBtn.addEventListener("click", () => showHistoricalRankings());
els.liveRankingBtn.addEventListener("click", () => showRealtimeRankings());
els.cacheBtn.addEventListener("click", () => triggerCacheUpdate());
els.techPoolBtn.addEventListener("click", () => triggerTechPoolUpdate());
els.aShareHoldBtn.addEventListener("click", () => chooseHoldingsFile(els.aShareHoldFile));
els.globalHoldBtn.addEventListener("click", () => chooseHoldingsFile(els.globalHoldFile));
els.aShareHoldFile.addEventListener("change", () => uploadHoldings("a_share", els.aShareHoldFile));
els.globalHoldFile.addEventListener("change", () => uploadHoldings("global", els.globalHoldFile));
els.portfolioPoolSelect.addEventListener("change", () => loadPortfolioAnalysis());
els.portfolioRefreshBtn.addEventListener("click", () => loadPortfolioAnalysis());
els.sourceSelect.addEventListener("change", () => loadRankings(true));
els.strategySelect.addEventListener("change", () => {
  state.strategyId = els.strategySelect.value;
  els.backtestStrategySelect.value = state.strategyId;
  invalidateBacktestExport();
  loadRankings(true);
});
els.backtestStrategySelect.addEventListener("change", () => {
  state.strategyId = els.backtestStrategySelect.value;
  els.strategySelect.value = state.strategyId;
  invalidateBacktestExport();
});
els.backtestPoolSelect.addEventListener("change", invalidateBacktestExport);
els.backtestExecutionMode.addEventListener("change", invalidateBacktestExport);
els.backtestBenchmark.addEventListener("change", invalidateBacktestExport);
els.backtestMonths.addEventListener("change", () => {
  toggleBacktestCustomRange();
  invalidateBacktestExport();
});
els.backtestStartDate.addEventListener("change", invalidateBacktestExport);
els.backtestEndDate.addEventListener("change", invalidateBacktestExport);
els.backtestBtn.addEventListener("click", () => runBacktest());
els.backtestExportBtn.addEventListener("click", () => exportBacktestDetails());
els.backtestFullscreenBtn.addEventListener("click", async () => {
  if (!state.backtest?.curve?.length) return;
  await els.backtestChart.requestFullscreen?.();
  window.setTimeout(() => window.Plotly?.Plots.resize(els.backtestChart), 120);
});
document.addEventListener("fullscreenchange", () => {
  window.setTimeout(() => window.Plotly?.Plots.resize(els.backtestChart), 120);
});
els.intervalSelect.addEventListener("change", resetTimer);
els.autoRefresh.addEventListener("change", resetTimer);
[els.searchInput, els.ratingFilter, els.holdOnly, els.buyOnly].forEach((el) => {
  el.addEventListener("input", render);
  el.addEventListener("change", render);
});

(async function init() {
  try {
    await loadConfig();
    await loadHoldingsStatus();
    await loadRankings(false);
    await loadAccountTodayChange();
    syncPortfolioPoolWithActiveTab();
    await loadPortfolioAnalysis();
    resetTimer();
  } catch (error) {
    setStatus(`初始化失败：${error.message}`, "error");
  }
})();
