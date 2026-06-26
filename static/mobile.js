const $ = (selector) => document.querySelector(selector);

const images = {
  clear: "/static/assets/weather/clear-cn.png",
  cloudy: "/static/assets/weather/cloudy-cn.png",
  rain: "/static/assets/weather/rain-cn.png",
  thunder: "/static/assets/weather/thunder-cn.png",
  wind: "/static/assets/weather/wind-cn.png",
  heat: "/static/assets/weather/heat-cn.png",
  fog: "/static/assets/weather/fog-cn.png"
};

function tomorrowDate() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  return date.toISOString().slice(0, 10);
}

function fmt(value, suffix = "") {
  return value === null || value === undefined || value === "" ? "--" : `${value}${suffix}`;
}

function setStatus(text) {
  $("#api-status").textContent = text;
}

function levelMeta(level) {
  if (level === "适合") return { color: "#22c55e", text: "适合", cls: "text-success", bg: "bg-success/10 text-success" };
  if (level === "谨慎") return { color: "#eab308", text: "谨慎", cls: "text-warning", bg: "bg-warning/15 text-warning" };
  return { color: "#ef4444", text: "不推荐", cls: "text-danger", bg: "bg-red-50 text-danger" };
}

function riskClass(level) {
  if (level === "high") return "risk-high";
  if (level === "medium") return "risk-medium";
  return "risk-low";
}

function setLoading(loading) {
  $("#risk-submit").disabled = loading;
  $("#risk-submit").textContent = loading ? "评估中..." : "评估风险";
}

function updateRing(score, level) {
  const meta = levelMeta(level);
  const circumference = 251.2;
  const offset = circumference * (1 - Math.max(0, Math.min(100, score)) / 100);
  $("#risk-ring").style.setProperty("--ring-offset", offset);
  $("#risk-ring").setAttribute("stroke", meta.color);
  $("#score").textContent = Number.isFinite(score) ? Math.round(score) : "--";
  $("#score").className = `font-mono text-[64px] font-bold leading-none ${meta.cls}`;
  $("#level").textContent = meta.text;
  $("#level-pill").className = `inline-flex items-center gap-2 rounded-full px-4 py-1 ${meta.bg}`;
}

function renderMetrics(window) {
  const precipMetric = window?.has_precip_probability
    ? ["降水概率", fmt(window?.max_precip_probability, "%")]
    : ["实测降水", fmt(window?.max_precipitation, " mm")];
  const rows = [
    [...precipMetric, "rainy", "text-danger"],
    ["体感温度", fmt(window?.max_apparent_temperature, "°C"), "thermostat", "text-warning"],
    ["风速/阵风", fmt(window?.max_wind_or_gust, " km/h"), "air", "text-muted"],
    ["紫外线指数", fmt(window?.max_uv_index), "wb_sunny", "text-warning"]
  ];
  $("#metrics").innerHTML = rows.map(([label, value, icon, cls]) => `
    <div class="rounded-lg border border-line bg-white p-4">
      <span class="font-mono text-[10px] uppercase tracking-[0.08em] text-muted">${label}</span>
      <div class="mt-2 flex items-end justify-between">
        <span class="font-mono text-2xl font-bold ${cls}">${value}</span>
        <span class="material-symbols-outlined ${cls}">${icon}</span>
      </div>
    </div>
  `).join("");
}

function renderFactors(factors) {
  $("#factors").innerHTML = (factors || []).map((factor) => `
    <div class="${riskClass(factor.level)} flex items-center justify-between rounded-r-lg border border-line bg-white p-4">
      <div class="pr-3">
        <p class="font-bold">${factor.name}</p>
        <p class="mt-1 text-sm text-muted">${factor.reason}</p>
      </div>
      <div class="rounded bg-fog px-2 py-0.5 font-mono text-[10px] text-muted">-${factor.points}</div>
    </div>
  `).join("") || `
    <div class="risk-low rounded-r-lg border border-line bg-white p-4">
      <p class="font-bold">暂无风险因素</p>
      <p class="mt-1 text-sm text-muted">完成评估后展示。</p>
    </div>
  `;
}

function renderBestHours(hours) {
  $("#best-hours").innerHTML = (hours || []).map((hour, index) => {
    const good = hour.score >= 75;
    const start = (hour.start || hour.time || "").slice(11, 16);
    const end = (hour.end || "").slice(11, 16);
    const label = end ? `${start}-${end}` : start;
    return `
      <button class="min-w-[140px] rounded-xl border ${index === 0 ? "border-success bg-success/5" : "border-line bg-white"} p-4 text-center active:scale-95" type="button">
        <span class="text-[11px] font-bold ${good ? "text-success" : "text-warning"}">${index === 0 ? "最佳时段" : "备选时段"}</span>
        <p class="my-1 font-mono text-2xl font-bold">${Math.round(hour.score)}</p>
        <p class="text-sm font-bold">${label}</p>
        <p class="mt-1 truncate text-xs text-muted">${hour.weather}</p>
      </button>
    `;
  }).join("") || `<div class="min-w-full rounded-xl border border-line bg-white p-4 text-sm text-muted">暂无可比较时段</div>`;
}

function pickGoodWeatherMood(data, labels) {
  const maxFeelsLike = Number(data.weather_window?.max_apparent_temperature);
  const candidates = [
    {
      match: /晴|少云/,
      title: "晴光正好，适合出发",
      quote: "“晴空一鹤排云上，便引诗情到碧霄。”",
      note: "把计划落到脚下，把好心情带上路。"
    },
    {
      match: /多云|阴/,
      title: "云影从容，步调刚好",
      quote: "“行到水穷处，坐看云起时。”",
      note: "云层替阳光收了锋芒，适合慢慢进入状态。"
    },
    {
      match: /风|微风/,
      title: "清风在侧，轻装上路",
      quote: "“沾衣欲湿杏花雨，吹面不寒杨柳风。”",
      note: "风不急，心也不急，今天适合把节奏放稳。"
    }
  ];
  const hotMood = {
    title: "天光明亮，记得补水",
    quote: "“接天莲叶无穷碧，映日荷花别样红。”",
    note: "阳光给人能量，也提醒你把防晒和补水安排好。"
  };
  const coolMood = {
    title: "清爽宜行，心境开阔",
    quote: "“空山新雨后，天气晚来秋。”",
    note: "凉意让步伐更轻，适合把今天过得清清爽爽。"
  };
  if (Number.isFinite(maxFeelsLike) && maxFeelsLike >= 31) return hotMood;
  if (Number.isFinite(maxFeelsLike) && maxFeelsLike <= 22) return coolMood;
  return candidates.find((item) => item.match.test(labels)) || candidates[0];
}

function weatherVisual(data) {
  const codes = new Set((data.weather_window?.weather_codes || []).map((code) => Number(code)));
  const labels = (data.weather_window?.weather_labels || []).join("、");
  const maxPrecip = Number(data.weather_window?.max_precip_probability || 0);
  const maxRainfall = Number(data.weather_window?.max_precipitation || 0);
  const hasCode = (...values) => values.some((value) => codes.has(value));
  const hasRange = (min, max) => [...codes].some((code) => code >= min && code <= max);

  if (hasCode(95, 96, 99) || /雷暴/.test(labels)) return { type: "thunder", image: images.thunder, dot: "#ef4444" };
  if (hasRange(51, 67) || hasRange(80, 82) || /雨|阵雨|毛毛雨/.test(labels) || maxRainfall > 0) {
    return { type: "rain", image: images.rain, dot: "#16a3b8" };
  }
  if (hasCode(45, 48) || /雾/.test(labels)) return { type: "fog", image: images.fog, dot: "#94a3b8" };
  if (hasCode(2, 3) || /多云|阴/.test(labels) || maxPrecip >= 60) return { type: "cloudy", image: images.cloudy, dot: "#64748b" };
  if (hasCode(0, 1) || /晴/.test(labels)) return { type: "clear", image: images.clear, dot: "#22c55e" };
  return { type: "fallback", image: images.fog, dot: "#16a3b8" };
}

function pickInsight(data) {
  const names = new Set((data.risk_factors || []).map((item) => item.name));
  const labels = (data.weather_window?.weather_labels || []).join("、");
  const visual = weatherVisual(data);
  const bad = data.level === "不推荐" || names.has("雷暴/强对流") || names.has("强风") || names.has("高温体感") || names.has("降水");

  if (visual.type === "thunder" || names.has("雷暴/强对流")) {
    return {
      kind: "雷暴安全提醒",
      dot: "#ef4444",
      image: visual.image,
      title: "雷暴靠近，停止户外骑行",
      body: "听到雷声就说明雷暴已在影响范围附近，优先进入坚固建筑或封闭车辆。",
      source: "防灾减灾知识 · AI生成示意配图",
      details: ["远离孤立大树、水边、金属围栏和高地。", "停止骑行、露营和水上活动。", "不要在空旷场地举伞或使用长杆器材。", "等待最后一次雷声后至少 30 分钟再恢复户外活动。"]
    };
  }
  if (visual.type === "rain" || names.has("降水")) {
    return {
      kind: "降水安全提醒",
      dot: visual.dot,
      image: visual.image,
      title: "降水影响路面与能见度",
      body: "雨天不是只影响舒适度，湿滑路面、低洼积水和视线下降会直接影响活动安全。",
      source: "城市降雨知识 · AI生成示意配图",
      details: ["避开低洼路段、桥洞和地下空间。", "骑行开启车灯，降低速度并增加跟车距离。", "强降水时优先改为室内备选方案。"]
    };
  }
  if (names.has("强风") || names.has("风偏大")) {
    return {
      kind: "大风安全提醒",
      dot: "#eab308",
      image: visual.type === "clear" || visual.type === "fallback" ? images.wind : visual.image,
      title: "风势偏强，固定物优先",
      body: "大风会放大骑行、帐篷、展架和树木风险，组织活动时要先处理撤离和固定。",
      source: "户外安全知识 · AI生成示意配图",
      details: ["收起帐篷、展架、横幅等受风面积大的物品。", "远离广告牌、临时搭建物和树木。", "骑行降低速度，横风明显时改期。"]
    };
  }
  if (names.has("高温体感")) {
    return {
      kind: "高温健康提醒",
      dot: "#eab308",
      image: visual.type === "clear" || visual.type === "fallback" ? images.heat : visual.image,
      title: "热压力偏高，避开正午",
      body: "高体感温度会降低运动表现，也会增加中暑风险。补水、阴凉点和休息节奏要提前安排。",
      source: "健康气象知识 · AI生成示意配图",
      details: ["避开 11:00-16:00 的高温时段。", "准备补水和电解质，不等口渴才喝水。", "出现头晕、恶心、皮肤灼热时立刻停止活动并降温。"]
    };
  }
  if (!bad) {
    const mood = pickGoodWeatherMood(data, labels);
    return {
      kind: "好天气心情卡",
      dot: visual.dot,
      image: visual.image,
      title: mood.title,
      body: `${mood.quote}${mood.note}`,
      source: "好天气心情卡 · AI生成示意配图",
      details: ["保持补水和防晒，轻装出发。", "把最佳时段设为提醒，临近活动前再复查一次天气。", "愿今天的风刚好，路也刚好。"]
    };
  }
  return {
    kind: "天气洞察",
    dot: visual.dot,
    image: visual.image,
    title: "天气平稳，也要临近复查",
    body: "预报会更新，活动前 2 小时复查一次，能把不确定性降到最低。",
    source: "预报不确定性知识 · AI生成示意配图",
    details: ["确认地点坐标是否准确。", "检查降水、风和体感温度是否有明显变化。", "保留一个可执行的备用方案。"]
  };
}

function renderInsight(data) {
  const insight = pickInsight(data);
  $("#insight-image").style.backgroundImage = `url("${insight.image}")`;
  $("#insight-dot").style.backgroundColor = insight.dot;
  $("#insight-kicker").textContent = insight.kind;
  $("#insight-title").textContent = insight.title;
  $("#insight-body").textContent = insight.body;
  $("#insight-source").textContent = insight.source;
  $("#insight-list").innerHTML = insight.details.map((item) => `<li>${item}</li>`).join("");
}

function renderPlan(data) {
  const resolved = data.plan.resolved_location || data.data_source?.location || {};
  $("#top-location").textContent = resolved.display_name || data.plan.location || data.plan.city;
  updateRing(data.score, data.level);
  $("#conclusion").textContent = data.conclusion;
  renderMetrics(data.weather_window);
  renderInsight(data);
  renderFactors(data.risk_factors || []);
  renderBestHours(data.best_hours || []);
  $("#contingency").innerHTML = (data.contingency || []).map((item) => `<li>${item}</li>`).join("");
  $("#notice").textContent = data.notification || "";
}

function activateNav(targetId) {
  document.querySelectorAll(".nav-action").forEach((item) => {
    const active = item.dataset.target === targetId;
    item.classList.toggle("bg-carbon", active);
    item.classList.toggle("text-white", active);
    item.classList.toggle("text-muted", !active);
    item.classList.toggle("rounded-xl", active);
  });
}

function scrollToTarget(targetId) {
  if (targetId === "settings-panel") {
    $("#settings-panel").classList.remove("hidden");
  }
  const target = $(`#${targetId}`);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
  activateNav(targetId);
}

function openWeatherAi() {
  $("#qa-panel").classList.remove("hidden");
  $("#qa-toggle").scrollIntoView({ behavior: "smooth", block: "center" });
}

async function evaluateRisk() {
  $("#risk-submit").disabled = true;
  $("#risk-submit").textContent = "评估中...";
  setStatus("计算中");
  $("#conclusion").textContent = "正在拉取地点级真实小时预报并计算风险...";
  const payload = {
    location: $("#location").value.trim(),
    activity_type: $("#activity").value,
    date: $("#date").value,
    start_time: $("#time").value,
    duration_hours: Number($("#duration").value || 2),
    people: Number($("#people").value || 1),
    children: $("#children").checked
  };

  try {
    const response = await fetch("/api/activity-risk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || "评估失败");
    renderPlan(data);
    setStatus("真实小时数据");
  } catch (error) {
    $("#conclusion").textContent = `评估失败：${error.message}`;
    setStatus("错误");
  } finally {
    $("#risk-submit").disabled = false;
    $("#risk-submit").textContent = "评估风险";
  }
}

async function askKnowledge() {
  $("#qa-answer").textContent = "正在检索气象知识库...";
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: $("#qa-question").value.trim() })
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || "请求失败");
    $("#qa-answer").textContent = data.answer;
  } catch (error) {
    $("#qa-answer").textContent = `请求失败：${error.message}`;
  }
}

function init() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  $("#date").value = date.toISOString().slice(0, 10);
  updateRing(0, "待评估");
  renderMetrics(null);
  renderFactors([]);
  renderBestHours([]);

  $("#risk-form").addEventListener("submit", (event) => {
    event.preventDefault();
    evaluateRisk();
  });
  $("#fill-demo").addEventListener("click", () => {
    $("#location").value = "广州天河体育中心";
    $("#activity").value = "cycling";
    $("#time").value = "18:00";
    $("#duration").value = "2";
    $("#people").value = "4";
  });
  $("#toggle-insight").addEventListener("click", () => {
    $("#insight-details").classList.toggle("hidden");
  });
  $("#qa-toggle").addEventListener("click", () => {
    $("#qa-panel").classList.toggle("hidden");
  });
  $("#qa-submit").addEventListener("click", askKnowledge);
  $("#copy-notice").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("#notice").textContent);
    $("#copy-notice").innerHTML = '<span class="material-symbols-outlined text-lg">done</span>';
    setTimeout(() => {
      $("#copy-notice").innerHTML = '<span class="material-symbols-outlined text-lg">content_copy</span>';
    }, 1500);
  });
  $("#menu-toggle").addEventListener("click", () => {
    const panel = $("#settings-panel");
    const isHidden = panel.classList.contains("hidden");
    panel.classList.toggle("hidden", !isHidden);
    if (isHidden) scrollToTarget("settings-panel");
  });
  document.querySelectorAll(".nav-action").forEach((button) => {
    button.addEventListener("click", () => scrollToTarget(button.dataset.target));
  });
  document.querySelectorAll(".menu-action").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.target === "qa-toggle") {
        openWeatherAi();
      } else {
        scrollToTarget(button.dataset.target);
      }
    });
  });
}

init();
