const columns = [
  { key: "排名", label: "#", type: "number" },
  { key: "代码", label: "代码", type: "text" },
  { key: "名称", label: "名称", type: "text" },
  { key: "日内走势", label: "日内", type: "trend", sortable: false },
  { key: "日线走势", label: "日线", type: "trend", sortable: false, optional: true },
  { key: "持仓操作", label: "持有", type: "holdingControl" },
  { key: "持仓市值", label: "市值(万)", type: "holdingValue" },
  { key: "仓位占比", label: "仓位", type: "holdPercent" },
  { key: "账户", label: "账户", type: "text" },
  { key: "板块", label: "板块", type: "text" },
  { key: "昨日排名", label: "昨日", type: "number" },
  { key: "排名变化", label: "变化", type: "text" },
  { key: "动态预警", label: "观察区", type: "text" },
  { key: "评级", label: "评级", type: "text" },
  { key: "最新收盘价", label: "最新价", type: "price" },
  { key: "当日涨跌幅", label: "当日涨跌", type: "percent" },
  { key: "MA5", label: "MA5", type: "price", optional: true },
  { key: "价格>MA5", label: ">MA5", type: "text", optional: true },
  { key: "MA15", label: "MA15", type: "price", optional: true },
  { key: "价格>MA15", label: ">MA15", type: "text", optional: true },
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
  backtest: null,
  backtestRequest: null,
  rankingDate: null,
  activePool: "a_share",
  strategyId: null,
  sortKey: "综合总分",
  sortDir: "desc",
  timer: null,
  noteDirty: false,
  noteSaving: false,
  noteLastKey: "",
  noteEntries: [],
  visibleColumns: null,
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
  columnOptions: document.querySelector("#columnOptions"),
  holdingEditStatus: document.querySelector("#holdingEditStatus"),
  noteScope: document.querySelector("#noteScope"),
  noteDate: document.querySelector("#noteDate"),
  noteDateList: document.querySelector("#noteDateList"),
  marketNote: document.querySelector("#marketNote"),
  noteStatus: document.querySelector("#noteStatus"),
  noteTodayBtn: document.querySelector("#noteTodayBtn"),
  noteSaveBtn: document.querySelector("#noteSaveBtn"),
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
  tableTitle: document.querySelector("#tableTitle"),
  rowCount: document.querySelector("#rowCount"),
  tableHead: document.querySelector("#tableHead"),
  tableBody: document.querySelector("#tableBody"),
};

const COLUMN_STORAGE_KEY = "etf.monitor.visibleColumns.v1";
const defaultVisibleColumnKeys = columns.filter((col) => !col.optional).map((col) => col.key);

function loadVisibleColumns() {
  try {
    const saved = JSON.parse(localStorage.getItem(COLUMN_STORAGE_KEY) || "null");
    if (Array.isArray(saved) && saved.length) {
      const known = new Set(columns.map((col) => col.key));
      const migrated = saved.map((key) => (key === "走势" ? "日内走势" : key));
      const filtered = migrated.filter((key) => known.has(key));
      const merged = filtered.includes("日内走势") ? [...filtered] : [...filtered.slice(0, 3), "日内走势", ...filtered.slice(3)];
      if (merged.length) return merged;
    }
  } catch {}
  return [...defaultVisibleColumnKeys];
}

function saveVisibleColumns() {
  localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(state.visibleColumns || defaultVisibleColumnKeys));
}

function visibleColumns() {
  const visible = new Set(state.visibleColumns || defaultVisibleColumnKeys);
  return columns.filter((col) => visible.has(col.key));
}

function renderColumnEditor() {
  if (!els.columnOptions) return;
  const visible = new Set(state.visibleColumns || defaultVisibleColumnKeys);
  els.columnOptions.innerHTML = columns
    .map((col) => `<label class="column-option"><input type="checkbox" value="${col.key}" ${visible.has(col.key) ? "checked" : ""} /> <span>${col.label}</span></label>`)
    .join("");
}

function fmt(value, type) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (type === "percent" && Number.isFinite(num)) return `${(num * 100).toFixed(2)}%`;
  if (type === "holdPercent" && Number.isFinite(num)) return `${num.toFixed(2)}%`;
  if (type === "holdingValue" && Number.isFinite(num)) return `${(num / 10000).toFixed(2)}`;
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

function renderTrendSparkline(values) {
  const points = Array.isArray(values) ? values.map(Number).filter(Number.isFinite) : [];
  if (points.length < 2) return `<span class="sparkline-empty">-</span>`;
  const width = 92;
  const height = 40;
  const padX = 3;
  const padY = 5;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const rawSpan = max - min;
  const buffer = rawSpan > 0 ? rawSpan * 0.12 : Math.max(Math.abs(max) * 0.005, 0.01);
  const chartMin = min - buffer;
  const chartMax = max + buffer;
  const span = chartMax - chartMin || 1;
  const lastUp = points[points.length - 1] >= points[0];
  const tone = lastUp ? "up" : "down";
  const coords = points.map((value, index) => {
    const x = padX + (index / (points.length - 1)) * (width - padX * 2);
    const y = padY + ((chartMax - value) / span) * (height - padY * 2);
    return [x, y];
  });
  const path = coords.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${path} L${(width - padX).toFixed(1)} ${(height - padY).toFixed(1)} L${padX.toFixed(1)} ${(height - padY).toFixed(1)} Z`;
  const title = `${fmt(points[0], "price")} -> ${fmt(points[points.length - 1], "price")}`;
  return `
    <span class="sparkline sparkline-${tone}" title="${title}">
      <svg viewBox="0 0 ${width} ${height}" aria-label="走势">
        <path class="sparkline-area" d="${area}"></path>
        <path class="sparkline-line" d="${path}"></path>
      </svg>
    </span>
  `;
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
  if (!account?.holdings) {
    pnlEl.textContent = "\u6682\u65e0\u6301\u4ed3";
    return;
  }
  const missing = Math.max(Number(account.holdings || 0) - Number(account.covered || 0), 0);
  const totalText = account.total_value ? ` / \u603b\u5e02\u503c ${fmtMoney(account.total_value)}` : "";
  pnlEl.textContent = missing
    ? `${signedMoney(pnl)}${totalText} / \u6301\u4ed3 ${account.holdings} \u4e2a\uff0c\u7f3a ${missing} \u4e2a\u884c\u60c5`
    : `${signedMoney(pnl)}${totalText} / \u6301\u4ed3 ${account.holdings} \u4e2a`;
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

function activeHoldingPool() {
  return state.config?.account_pools?.[state.activePool] ? state.activePool : null;
}

function holdingValueWan(row) {
  const value = Number(row?.["持仓市值"]);
  return Number.isFinite(value) && value > 0 ? value / 10000 : null;
}

function setHoldingEditStatus(text, tone = "") {
  if (!els.holdingEditStatus) return;
  els.holdingEditStatus.textContent = text;
  els.holdingEditStatus.className = `muted holding-edit-status ${tone}`;
}

async function saveManualHolding({ code, name, held, marketValueWan }) {
  const poolKey = activeHoldingPool();
  if (!poolKey) {
    setHoldingEditStatus("活跃科技页不作为独立账户维护持仓", "warn");
    return;
  }
  const value = Number(marketValueWan || 0);
  if (held && (!Number.isFinite(value) || value <= 0)) {
    setHoldingEditStatus("\u8bf7\u586b\u5199\u6301\u4ed3\u5e02\u503c\uff0c\u5355\u4f4d\u4e07", "warn");
    return;
  }
  setHoldingEditStatus("正在保存持仓...", "working");
  try {
    const res = await fetch(`/api/holdings/${encodeURIComponent(poolKey)}/manual`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code,
        name,
        held,
        market_value_wan: held ? value : 0,
      }),
    });
    if (!res.ok) throw new Error(await apiErrorMessage(res));
    const payload = await res.json();
    state.config.holdings = payload.status;
    await loadRankings(false);
    await loadAccountTodayChange();
    const action = held ? "已保存" : "已移除";
    setHoldingEditStatus(`${code} ${action}，仓位已自动重算`, "ok");
  } catch (error) {
    setHoldingEditStatus(`持仓保存失败：${error.message}`, "error");
  }
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
      const upCount = rows.filter((row) => Number(row["当日涨跌幅"]) > 0).length;
      const downCount = rows.filter((row) => Number(row["当日涨跌幅"]) < 0).length;
      const aboveMa20Count = rows.filter((row) => row["价格>MA20"] === "是").length;
      const belowMa20Count = rows.filter((row) => row["价格>MA20"] === "否").length;
      const holdStatus = state.config?.holdings?.[key];
      const top = rows[0];
      const holdText = holdStatus ? `账户 ${holdStatus.count} / ${holdStatus.updated_at || "未维护"}` : `持仓 ${holds}`;
      return `
        <button class="summary-card ${key === state.activePool ? "active" : ""}" type="button" data-pool="${key}">
          <span>${group.title}</span>
          <strong>${rows.length}</strong>
          <span class="summary-stats">
            <span>今日 <b class="positive">${upCount}</b>/<b class="negative">${downCount}</b></span>
            <span>&gt;MA20 <b class="positive">${aboveMa20Count}</b>/<b class="negative">${belowMa20Count}</b></span>
          </span>
          <small>买入 ${buys} / ${holdText}</small>
          <em>${top ? `${top["代码"]} ${top["名称"]}` : "暂无数据"}</em>
        </button>
      `;
    })
    .join("");
}

function renderTableHead() {
  els.tableHead.innerHTML = visibleColumns()
    .map((col) => {
      const active = col.key === state.sortKey ? `sorted ${state.sortDir}` : "";
      const sortAttr = col.sortable === false ? "" : ` data-sort="${col.key}"`;
      return `<th class="${active}"${sortAttr}>${col.label}</th>`;
    })
    .join("");
}

function renderTableBody(rows) {
  const rankGroup = (item) => {
    const rank = Number(item?.["排名"]);
    if (!Number.isFinite(rank)) return "";
    if (rank <= 8) return "rank-top8";
    if (rank <= 12) return "rank-top12";
    return "";
  };
  els.tableBody.innerHTML = rows
    .map((row, index) => {
      const groupClass = rankGroup(row);
      const trClasses = [];
      if (row["持仓"]) trClasses.push("holding-row");
      if (groupClass) {
        trClasses.push("rank-frame", groupClass);
        if (rankGroup(rows[index - 1]) !== groupClass) trClasses.push("rank-frame-start");
        if (rankGroup(rows[index + 1]) !== groupClass) trClasses.push("rank-frame-end");
      }
      const trClass = trClasses.join(" ");
      const cells = visibleColumns()
        .map((col) => {
          const value = row[col.key];
          const numeric = ["number", "percent", "holdPercent", "price", "ratio", "score"].includes(col.type) ? "numeric" : "";
          const sign = col.type === "percent" && Number(value) > 0 ? "positive" : col.type === "percent" && Number(value) < 0 ? "negative" : "";
          if (col.type === "holdingControl") {
            const poolKey = activeHoldingPool();
            const isHeld = Boolean(row["持仓"]);
            const disabled = poolKey ? "" : "disabled";
            const action = isHeld ? "remove" : "add";
            return `<td><button class="holding-toggle-btn ${isHeld ? "is-held" : ""}" type="button" data-action="${action}" data-code="${row["代码"] || ""}" data-name="${row["名称"] || ""}" ${disabled}>${isHeld ? "持有" : "空仓"}</button></td>`;
          }
          if (col.type === "holdingValue") {
            const poolKey = activeHoldingPool();
            const valueWan = holdingValueWan(row);
            const disabled = poolKey ? "" : "disabled";
            const valueText = valueWan === null ? "" : valueWan.toFixed(2);
            const displayText = valueText || "-";
            return `<td>
              <span class="holding-value-cell ${poolKey ? "" : "disabled"}" title="双击编辑" data-code="${row["代码"] || ""}" data-name="${row["名称"] || ""}">
                <span class="holding-value-display">${displayText}</span>
                <input class="holding-value-input" type="text" inputmode="decimal" value="${valueText}" data-code="${row["代码"] || ""}" data-name="${row["名称"] || ""}" ${disabled} />
              </span>
            </td>`;
          }
          if (col.key === "评级") {
            return `<td><span class="rating ${ratingClass(value)}">${fmt(value, col.type)}</span></td>`;
          }
          if (col.key === "动态预警" && value) {
            return `<td><span class="alert-chip">${fmt(value, col.type)}</span></td>`;
          }
          if (col.type === "trend") {
            return `<td class="trend-cell">${renderTrendSparkline(value)}</td>`;
          }
          if (col.key === "价格>MA5" || col.key === "价格>MA15" || col.key === "价格>MA20") {
            const maClass = value === "是" ? "ma-yes" : value === "否" ? "ma-no" : "ma-neutral";
            return `<td><span class="ma-chip ${maClass}">${fmt(value, col.type)}</span></td>`;
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

function todayText() {
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Shanghai" });
}

function noteDate() {
  return els.noteDate?.value || todayText();
}

function noteKey() {
  return noteDate();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function setNoteStatus(message = "", type = "") {
  if (!els.noteStatus) return;
  els.noteStatus.textContent = message;
  els.noteStatus.className = `muted note-status ${type}`.trim();
}

function renderNoteScope() {
  if (els.noteScope) els.noteScope.textContent = noteDate() === todayText() ? "\u4eca\u65e5" : noteDate();
}

function noteDateLabel(dateText) {
  if (dateText === todayText()) return "\u4eca\u65e5";
  const parts = String(dateText || "").split("-");
  return parts.length === 3 ? `${parts[1]}/${parts[2]}` : dateText;
}

function noteLongDateLabel(dateText) {
  const parts = String(dateText || "").split("-");
  return parts.length === 3 ? `${parts[0]}/${parts[1]}/${parts[2]}` : dateText;
}

function noteTimeLabel(value) {
  if (!value) return "";
  const text = String(value).replace("T", " ");
  return text.length > 16 ? text.slice(0, 16) : text;
}

function renderNoteDateList() {
  if (!els.noteDateList) return;
  const current = noteDate();
  const entries = [...state.noteEntries];
  if (!entries.some((item) => item.note_date === current)) {
    entries.unshift({ note_date: current, content: "", updated_at: null });
  }
  if (!entries.some((item) => item.note_date === todayText())) {
    entries.unshift({ note_date: todayText(), content: "", updated_at: null });
  }
  const seen = new Set();
  const uniqueEntries = entries.filter((item) => {
    if (!item?.note_date || seen.has(item.note_date)) return false;
    seen.add(item.note_date);
    return true;
  });
  els.noteDateList.innerHTML = uniqueEntries.length
    ? uniqueEntries
        .map((item) => {
          const dateText = item.note_date;
          const classes = ["note-card"];
          if (dateText === current) classes.push("active");
          if (dateText === todayText()) classes.push("today");
          const body = item.content?.trim() || "\u8fd9\u5929\u8fd8\u6ca1\u6709\u8bb0\u5f55";
          return `<button class="${classes.join(" ")}" type="button" data-note-date="${escapeHtml(dateText)}" title="${escapeHtml(dateText)}">
            <span class="note-card-date">${escapeHtml(noteLongDateLabel(dateText))}</span>
            <span class="note-card-time">${escapeHtml(item.updated_at ? `\u66f4\u65b0 ${noteTimeLabel(item.updated_at)}` : "\u672a\u8bb0\u5f55")}</span>
            <span class="note-card-body">${escapeHtml(body)}</span>
          </button>`;
        })
        .join("")
    : `<div class="note-empty">\u6682\u65e0\u7814\u7a76\u65e5\u5fd7</div>`;
}

async function loadMarketNoteDates() {
  try {
    const response = await fetch(`/api/notes/recent?limit=30`);
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    state.noteEntries = payload.notes || [];
  } catch (error) {
    state.noteEntries = [];
  }
  renderNoteDateList();
}

async function loadMarketNote() {
  if (!els.marketNote) return;
  const key = noteKey();
  state.noteLastKey = key;
  renderNoteScope();
  renderNoteDateList();
  setNoteStatus("\u8bfb\u53d6\u4e2d...");
  try {
    const response = await fetch(`/api/notes?note_date=${encodeURIComponent(noteDate())}`);
    if (!response.ok) throw new Error(await response.text());
    const payload = await response.json();
    if (state.noteLastKey !== key) return;
    els.marketNote.value = payload.content || "";
    state.noteDirty = false;
    setNoteStatus(payload.updated_at ? "\u5df2\u4fdd\u5b58" : "\u672a\u8bb0\u5f55", payload.updated_at ? "ok" : "");
  } catch (error) {
    setNoteStatus("\u8bfb\u53d6\u5931\u8d25", "error");
  }
}

async function saveMarketNote() {
  if (!els.marketNote || state.noteSaving || !state.noteDirty) return;
  const targetDate = state.noteLastKey || noteKey();
  state.noteSaving = true;
  setNoteStatus("\u4fdd\u5b58\u4e2d...");
  try {
    const response = await fetch(`/api/notes?note_date=${encodeURIComponent(targetDate)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: els.marketNote.value }),
    });
    if (!response.ok) throw new Error(await response.text());
    await response.json();
    if (state.noteLastKey === targetDate) {
      state.noteDirty = false;
      setNoteStatus(els.marketNote.value.trim() ? "\u5df2\u4fdd\u5b58" : "\u672a\u8bb0\u5f55", els.marketNote.value.trim() ? "ok" : "");
      await loadMarketNoteDates();
    }
  } catch (error) {
    setNoteStatus("\u4fdd\u5b58\u5931\u8d25", "error");
  } finally {
    state.noteSaving = false;
  }
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
  if (els.noteDate) els.noteDate.value = state.rankingDate;
  await loadMarketNoteDates();
  await loadMarketNote();
}

async function showRealtimeRankings() {
  state.rankingDate = null;
  els.rankingDate.value = "";
  els.sourceSelect.disabled = false;
  els.liveRankingBtn.disabled = true;
  resetTimer();
  await loadRankings(true);
  if (els.noteDate) els.noteDate.value = todayText();
  await loadMarketNoteDates();
  await loadMarketNote();
}

function parseWanValue(raw) {
  const normalized = String(raw || "")
    .replace(/[^0-9.-]/g, "")
    .trim();
  const value = Number(normalized || 0);
  return Number.isFinite(value) ? value : null;
}

function setRowHoldingVisual(code, held, valueWan = null) {
  const row = els.tableBody.querySelector(`.holding-toggle-btn[data-code="${code}"]`)?.closest("tr");
  if (!row) return;
  row.classList.toggle("holding-row", held);
  const toggle = row.querySelector(`.holding-toggle-btn[data-code="${code}"]`);
  if (toggle) {
    toggle.classList.toggle("is-held", held);
    toggle.dataset.action = held ? "remove" : "add";
    toggle.textContent = held ? "\u6301\u6709" : "\u7a7a\u4ed3";
  }
  const input = row.querySelector(`.holding-value-input[data-code="${code}"]`);
  const display = row.querySelector(`.holding-value-cell[data-code="${code}"] .holding-value-display`);
  if (valueWan !== null) {
    const text = valueWan > 0 ? valueWan.toFixed(2) : "";
    if (input) input.value = text;
    if (display) display.textContent = text || "-";
  }
}

function openHoldingValueEditor(input) {
  const cell = input?.closest(".holding-value-cell");
  if (!cell || cell.classList.contains("disabled")) return;
  cell.classList.add("editing");
  input.focus();
  input.select();
}

function updateLocalHoldingState(code, name, held, valueWan) {
  const poolKey = activeHoldingPool();
  const group = state.payload?.pools?.[poolKey];
  if (!poolKey || !group?.rows) return;
  const accountName = state.config?.account_pools?.[poolKey] || "";
  const value = Number(valueWan || 0) * 10000;
  group.rows.forEach((row) => {
    if (String(row["代码"]).padStart(6, "0") !== String(code).padStart(6, "0")) return;
    if (held && value > 0) {
      row["持仓"] = "★ 持有";
      row["账户"] = accountName;
      row["持仓市值"] = value;
    } else {
      row["持仓"] = "";
      row["账户"] = "";
      row["持仓市值"] = null;
      row["仓位占比"] = null;
    }
    if (name && !row["名称"]) row["名称"] = name;
  });
  const heldRows = group.rows.filter((row) => row["持仓"] && Number(row["持仓市值"]) > 0);
  const totalValue = heldRows.reduce((sum, row) => sum + Number(row["持仓市值"] || 0), 0);
  heldRows.forEach((row) => {
    row["仓位占比"] = totalValue > 0 ? (Number(row["持仓市值"] || 0) / totalValue) * 100 : null;
  });
  if (state.config?.holdings?.[poolKey]) {
    state.config.holdings[poolKey].count = heldRows.length;
    state.config.holdings[poolKey].source_file = "manual";
  }
  renderSummary();
  renderOptimisticAccountChange(poolKey);
}

function renderOptimisticAccountChange(poolKey) {
  const group = state.payload?.pools?.[poolKey];
  if (!group?.rows) return;
  let currentTotal = 0;
  let previousTotal = 0;
  let todayPnl = 0;
  let covered = 0;
  let holdings = 0;
  group.rows.forEach((row) => {
    if (!row["持仓"]) return;
    const currentValue = Number(row["持仓市值"] || 0);
    if (!Number.isFinite(currentValue) || currentValue <= 0) return;
    holdings += 1;
    currentTotal += currentValue;
    const ret = Number(row["当日涨跌幅"]);
    if (Number.isFinite(ret) && ret > -0.999) {
      const previousValue = currentValue / (1 + ret);
      previousTotal += previousValue;
      todayPnl += currentValue - previousValue;
      covered += 1;
    }
  });
  const account = {
    holdings,
    covered,
    total_value: currentTotal,
    previous_value: previousTotal,
    today_pnl: previousTotal > 0 ? todayPnl : null,
    return_1d: previousTotal > 0 ? todayPnl / previousTotal : null,
  };
  if (poolKey === "a_share") setAccountChangeNode(els.aShareTodayChange, els.aShareTodayPnl, account);
  if (poolKey === "global") setAccountChangeNode(els.globalTodayChange, els.globalTodayPnl, account);
}

async function saveHoldingValueInput(input) {
  const value = parseWanValue(input.value);
  if (value === null || value < 0) {
    setHoldingEditStatus("\u8bf7\u8f93\u5165\u6709\u6548\u7684\u6301\u4ed3\u5e02\u503c\uff0c\u5355\u4f4d\u4e07", "warn");
    input.focus();
    return;
  }
  input.closest(".holding-value-cell")?.classList.remove("editing");
  setRowHoldingVisual(input.dataset.code, value > 0, value);
  updateLocalHoldingState(input.dataset.code, input.dataset.name, value > 0, value);
  await saveManualHolding({
    code: input.dataset.code,
    name: input.dataset.name,
    held: value > 0,
    marketValueWan: value,
  });
}

document.addEventListener("keydown", async (event) => {
  const input = event.target.closest(".holding-value-input");
  if (!input) return;
  if (event.key === "Enter") {
    event.preventDefault();
    input.blur();
  }
  if (event.key === "Escape") {
    event.preventDefault();
    const wrapper = input.closest(".holding-value-cell");
    const display = wrapper?.querySelector(".holding-value-display")?.textContent || "";
    input.value = display === "-" ? "" : display;
    wrapper?.classList.remove("editing");
  }
});

document.addEventListener("focusout", async (event) => {
  const input = event.target.closest(".holding-value-input");
  if (!input) return;
  await saveHoldingValueInput(input);
});

document.addEventListener("dblclick", (event) => {
  const cell = event.target.closest(".holding-value-cell");
  if (!cell || cell.classList.contains("disabled")) return;
  openHoldingValueEditor(cell.querySelector(".holding-value-input"));
});

document.addEventListener("click", async (event) => {
  const toggle = event.target.closest(".holding-toggle-btn");
  if (!toggle) return;
  const input = els.tableBody.querySelector(`.holding-value-input[data-code="${toggle.dataset.code}"]`);
  if (toggle.dataset.action === "remove") {
    setRowHoldingVisual(toggle.dataset.code, false, 0);
    updateLocalHoldingState(toggle.dataset.code, toggle.dataset.name, false, 0);
    await saveManualHolding({
      code: toggle.dataset.code,
      name: toggle.dataset.name,
      held: false,
      marketValueWan: 0,
    });
    return;
  }
  const value = parseWanValue(input?.value);
  if (value === null || value <= 0) {
    openHoldingValueEditor(input);
    setHoldingEditStatus("\u8bf7\u586b\u5199\u6301\u4ed3\u5e02\u503c\uff0c\u5355\u4f4d\u4e07", "warn");
    return;
  }
  setRowHoldingVisual(toggle.dataset.code, true, value);
  updateLocalHoldingState(toggle.dataset.code, toggle.dataset.name, true, value);
  await saveManualHolding({
    code: toggle.dataset.code,
    name: toggle.dataset.name,
    held: true,
    marketValueWan: value,
  });
});

document.addEventListener("click", async (event) => {
  const viewTab = event.target.closest("[data-view]");
  if (viewTab) {
    switchView(viewTab.dataset.view);
    return;
  }
  const tab = event.target.closest("[data-pool]");
  if (tab) {
    await saveMarketNote();
    state.activePool = tab.dataset.pool;
    if (els.backtestPoolSelect.querySelector(`option[value="${state.activePool}"]`)) {
      els.backtestPoolSelect.value = state.activePool;
      invalidateBacktestExport();
    }
    render();
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
els.noteDate?.addEventListener("change", async () => {
  await saveMarketNote();
  await loadMarketNoteDates();
  await loadMarketNote();
});
els.noteTodayBtn?.addEventListener("click", async () => {
  await saveMarketNote();
  if (els.noteDate) els.noteDate.value = todayText();
  await loadMarketNoteDates();
  await loadMarketNote();
});
els.noteSaveBtn?.addEventListener("click", async () => {
  await saveMarketNote();
});
els.noteDateList?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-note-date]");
  if (!button) return;
  await saveMarketNote();
  if (els.noteDate) els.noteDate.value = button.dataset.noteDate;
  await loadMarketNote();
});
els.marketNote?.addEventListener("input", () => {
  state.noteDirty = true;
  setNoteStatus("\u672a\u4fdd\u5b58", "warn");
});
els.marketNote?.addEventListener("blur", () => saveMarketNote());
els.marketNote?.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    saveMarketNote();
  }
});
els.intervalSelect.addEventListener("change", resetTimer);
els.autoRefresh.addEventListener("change", resetTimer);
[els.searchInput, els.ratingFilter, els.holdOnly, els.buyOnly].forEach((el) => {
  el.addEventListener("input", render);
  el.addEventListener("change", render);
});
els.columnOptions?.addEventListener("change", (event) => {
  const input = event.target.closest('input[type="checkbox"]');
  if (!input) return;
  const checked = Array.from(els.columnOptions.querySelectorAll('input[type="checkbox"]:checked')).map((item) => item.value);
  state.visibleColumns = checked.length ? checked : [...defaultVisibleColumnKeys];
  saveVisibleColumns();
  render();
});

(async function init() {
  try {
    state.visibleColumns = loadVisibleColumns();
    renderColumnEditor();
    await loadConfig();
    await loadHoldingsStatus();
    if (els.noteDate) els.noteDate.value = todayText();
    await loadRankings(false);
    await loadMarketNoteDates();
    await loadMarketNote();
    await loadAccountTodayChange();
    resetTimer();
  } catch (error) {
    setStatus(`初始化失败：${error.message}`, "error");
  }
})();
