const $ = (selector) => document.querySelector(selector);

const decisionSections = [
  "assess-section",
  "score-section",
  "metrics",
  "insight-card",
  "plan-section",
  "history-section",
  "notice-section"
];

const images = {
  clear: "/static/assets/weather/clear-cn.png",
  cloudy: "/static/assets/weather/cloudy-cn.png",
  rain: "/static/assets/weather/rain-cn.png",
  thunder: "/static/assets/weather/thunder-cn.png",
  wind: "/static/assets/weather/wind-cn.png",
  heat: "/static/assets/weather/heat-cn.png",
  fog: "/static/assets/weather/fog-cn.png"
};

const state = {
  lastPlan: null,
  feedback: JSON.parse(localStorage.getItem("meteorisk_feedback") || "[]"),
  subscriptions: JSON.parse(localStorage.getItem("meteorisk_subscriptions") || "[]"),
  queryHistory: JSON.parse(localStorage.getItem("meteorisk_query_history") || "[]")
};

function fmt(value, suffix = "") {
  return value === null || value === undefined || value === "" ? "--" : `${value}${suffix}`;
}

function setStatus(text) {
  $("#api-status").textContent = text;
}

function startDesktopHeartbeat() {
  const ping = () => {
    fetch("/api/desktop-heartbeat", { method: "POST", keepalive: true }).catch(() => {});
  };
  ping();
  setInterval(ping, 3000);
}

function activityLabel(value) {
  return {
    cycling: "骑行",
    running: "跑步",
    camping: "露营",
    hiking: "徒步/登山",
    outdoor_event: "户外活动运营",
    parent_child: "亲子出行"
  }[value] || value || "户外活动";
}

function levelMeta(level) {
  if (level === "适合") return { color: "#22c55e", text: "适合", cls: "text-success", bg: "bg-success/10 text-success" };
  if (level === "谨慎") return { color: "#eab308", text: "谨慎", cls: "text-warning", bg: "bg-warning/15 text-warning" };
  if (level === "不推荐") return { color: "#ef4444", text: "不推荐", cls: "text-danger", bg: "bg-red-50 text-danger" };
  return { color: "#5d6469", text: "待评估", cls: "text-muted", bg: "bg-fog text-muted" };
}

function riskClass(level) {
  if (level === "high") return "risk-high";
  if (level === "medium") return "risk-medium";
  return "risk-low";
}

function planPayload(overrides = {}) {
  return {
    location: $("#location").value.trim(),
    activity_type: $("#activity").value,
    date: $("#date").value,
    start_time: $("#time").value,
    duration_hours: Number($("#duration").value || 2),
    people: Number($("#people").value || 1),
    children: $("#children").checked,
    elderly: $("#elderly").checked,
    ...overrides
  };
}

function localDateValue(offsetDays = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

function questionDateText(value) {
  if (!value) return "明天";
  if (value === localDateValue(0)) return "今天";
  if (value === localDateValue(1)) return "明天";
  return `${value} `;
}

function questionPlaceText(location) {
  return location?.trim() || "当前地点";
}

function quickQuestionsForPlan() {
  const payload = planPayload();
  const place = questionPlaceText(payload.location);
  const day = questionDateText(payload.date);
  const activity = activityLabel(payload.activity_type);
  const shared = `${place}${day}${activity}`;
  const templates = {
    cycling: [
      `${shared}适合吗？重点看雷雨、阵风和路面湿滑。`,
      `${place}${day}骑行需要带雨具、防晒还是改期？`,
      `如果${activity}途中遇到雷暴或强阵风，应该怎么处理？`
    ],
    running: [
      `${shared}适合吗？重点看体感温度、降水和紫外线。`,
      `${place}${day}跑步推荐什么时段，应该避开几点？`,
      `高温闷热天气跑步有哪些中暑风险和补水建议？`
    ],
    camping: [
      `${shared}适合吗？重点看夜间降雨、雷暴和阵风。`,
      `${place}${day}露营需要准备哪些防雨防风装备？`,
      `雷暴或大风天气露营应该取消还是改室内方案？`
    ],
    hiking: [
      `${shared}适合吗？重点看雷暴、降雨、能见度和体感温度。`,
      `${place}${day}徒步登山推荐什么时段出发？`,
      `山地徒步遇到雷雨和短时强降水应该怎么避险？`
    ],
    outdoor_event: [
      `${shared}适合组织吗？需要取消还是保留备用方案？`,
      `${place}${day}户外活动群通知应该怎么写？`,
      `多人户外活动遇到雷暴、降雨或高温时怎么做应急预案？`
    ],
    parent_child: [
      `${shared}适合吗？重点看儿童热压力、降雨和雷暴。`,
      `${place}${day}亲子出行需要带什么装备？`,
      `带儿童户外活动遇到高温或雷雨应该怎么调整计划？`
    ]
  };
  return templates[payload.activity_type] || [
    `${shared}适合吗？`,
    `${place}${day}需要带伞或防晒吗？`,
    `这个天气做${activity}有哪些风险？`
  ];
}

function renderQaQuickQuestions() {
  $("#qa-quick-questions").innerHTML = quickQuestionsForPlan().map((question) => `
    <button class="qa-quick rounded-full border border-line bg-fog px-3 py-2 text-left text-xs font-bold leading-snug text-muted" data-question="${escapeHtml(question)}" type="button">
      ${escapeHtml(question)}
    </button>
  `).join("");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;"
  }[char]));
}

function saveQueryHistory(payload, data) {
  const resolved = data.plan?.resolved_location || data.data_source?.location || {};
  const historyItem = {
    payload,
    displayLocation: resolved.display_name || payload.location || "未命名地点",
    activity: activityLabel(payload.activity_type),
    time: `${payload.date} ${payload.start_time}`,
    duration: payload.duration_hours,
    score: data.score,
    level: data.level,
    weather: (data.weather_window?.weather_labels || []).join("、") || "天气平稳",
    createdAt: new Date().toLocaleString("zh-CN")
  };
  const key = `${payload.location}|${payload.activity_type}|${payload.date}|${payload.start_time}|${payload.duration_hours}`;
  state.queryHistory = state.queryHistory.filter((item) => {
    const itemPayload = item.payload || {};
    return `${itemPayload.location}|${itemPayload.activity_type}|${itemPayload.date}|${itemPayload.start_time}|${itemPayload.duration_hours}` !== key;
  });
  state.queryHistory.unshift(historyItem);
  state.queryHistory = state.queryHistory.slice(0, 12);
  localStorage.setItem("meteorisk_query_history", JSON.stringify(state.queryHistory));
  renderQueryHistory();
}

function renderQueryHistory() {
  $("#query-history-list").innerHTML = state.queryHistory.map((item, index) => {
    const meta = levelMeta(item.level);
    return `
      <div class="query-history-item rounded-lg border border-line bg-white p-3 active:scale-[.99]" data-index="${index}">
        <div class="flex items-start justify-between gap-3">
          <button class="query-history-restore min-w-0 flex-1 text-left" data-index="${index}" type="button">
            <p class="truncate text-sm font-bold">${escapeHtml(item.displayLocation)}</p>
            <p class="mt-1 text-xs text-muted">${escapeHtml(item.activity)} · ${escapeHtml(item.time)} · ${escapeHtml(item.duration)}小时</p>
            <p class="mt-2 truncate text-xs text-muted">${escapeHtml(item.weather)} · ${escapeHtml(item.createdAt)}</p>
          </button>
          <div class="flex shrink-0 items-center gap-2">
            <span class="rounded-full px-2 py-1 text-xs font-bold ${meta.bg}">${escapeHtml(item.level)} · ${escapeHtml(item.score)}</span>
            <button class="delete-query-history rounded bg-fog p-1 text-muted" data-index="${index}" type="button" aria-label="删除这条历史" title="删除这条历史">
              <span class="material-symbols-outlined text-base">close</span>
            </button>
          </div>
        </div>
      </div>
    `;
  }).join("") || `<div class="rounded-lg border border-dashed border-line bg-white p-3 text-sm text-muted">暂无查询历史。</div>`;
}

function restoreQueryHistory(index) {
  const item = state.queryHistory[index];
  if (!item?.payload) return;
  const payload = item.payload;
  $("#location").value = payload.location || "";
  $("#activity").value = payload.activity_type || "outdoor_event";
  $("#date").value = payload.date || $("#date").value;
  $("#time").value = payload.start_time || "18:00";
  $("#duration").value = payload.duration_hours || 2;
  $("#people").value = payload.people || 1;
  $("#children").checked = Boolean(payload.children);
  $("#elderly").checked = Boolean(payload.elderly);
  $("#geolocation-status").textContent = "已从查询历史回填，点击“评估风险”可重新拉取最新天气。";
  renderQaQuickQuestions();
  activateView("decision");
}

function deleteQueryHistory(index) {
  state.queryHistory.splice(index, 1);
  localStorage.setItem("meteorisk_query_history", JSON.stringify(state.queryHistory));
  renderQueryHistory();
  $("#geolocation-status").textContent = "已删除这条查询历史。";
}

function requestCurrentLocation() {
  if (!navigator.geolocation) {
    $("#geolocation-status").textContent = "当前浏览器不支持定位，请手动输入地标或经纬度。";
    return;
  }
  $("#use-current-location").disabled = true;
  $("#geolocation-status").textContent = "正在向浏览器申请定位权限...";
  navigator.geolocation.getCurrentPosition((position) => {
    const latitude = position.coords.latitude.toFixed(5);
    const longitude = position.coords.longitude.toFixed(5);
    $("#location").value = `${latitude},${longitude}`;
    $("#top-location").textContent = "当前位置坐标";
    $("#geolocation-status").textContent = `已获取当前位置：${latitude}, ${longitude}。点击“评估风险”开始查询。`;
    renderQaQuickQuestions();
    $("#use-current-location").disabled = false;
  }, (error) => {
    const messages = {
      1: "定位权限被拒绝，可在浏览器地址栏左侧权限设置中允许定位。",
      2: "暂时无法获取定位，请检查系统定位服务或手动输入地点。",
      3: "定位超时，请稍后重试或手动输入地点。"
    };
    $("#geolocation-status").textContent = messages[error.code] || "定位失败，请手动输入地点。";
    $("#use-current-location").disabled = false;
  }, {
    enableHighAccuracy: true,
    timeout: 10000,
    maximumAge: 300000
  });
}

function updateRing(score, level) {
  const meta = levelMeta(level);
  const circumference = 251.2;
  const safeScore = Number.isFinite(score) ? Math.max(0, Math.min(100, score)) : 0;
  const offset = circumference * (1 - safeScore / 100);
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
        <p class="mt-1 truncate text-xs text-muted">${hour.weather || "天气平稳"}</p>
      </button>
    `;
  }).join("") || `<div class="min-w-full rounded-xl border border-line bg-white p-4 text-sm text-muted">暂无可比较时段</div>`;
}

function pickGoodWeatherMood(data, labels) {
  const maxFeelsLike = Number(data.weather_window?.max_apparent_temperature);
  const candidates = [
    { match: /晴|少云/, title: "晴光正好，适合出发", quote: "“晴空一鹤排云上，便引诗情到碧霄。”", note: "把计划落到脚下，把好心情带上路。" },
    { match: /多云|阴/, title: "云影从容，步调刚好", quote: "“行到水穷处，坐看云起时。”", note: "云层替阳光收了锋芒，适合慢慢进入状态。" },
    { match: /风|微风/, title: "清风在侧，轻装上路", quote: "“沾衣欲湿杏花雨，吹面不寒杨柳风。”", note: "风不急，心也不急，今天适合把节奏放稳。" }
  ];
  if (Number.isFinite(maxFeelsLike) && maxFeelsLike >= 31) {
    return { title: "天光明亮，记得补水", quote: "“接天莲叶无穷碧，映日荷花别样红。”", note: "阳光给人能量，也提醒你把防晒和补水安排好。" };
  }
  if (Number.isFinite(maxFeelsLike) && maxFeelsLike <= 22) {
    return { title: "清爽宜行，心境开阔", quote: "“空山新雨后，天气晚来秋。”", note: "凉意让步伐更轻，适合把今天过得清清爽爽。" };
  }
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
  if (hasRange(51, 67) || hasRange(80, 82) || /雨|阵雨|毛毛雨/.test(labels) || maxRainfall > 0) return { type: "rain", image: images.rain, dot: "#16a3b8" };
  if (hasCode(45, 48) || /雾/.test(labels)) return { type: "fog", image: images.fog, dot: "#94a3b8" };
  if (hasCode(2, 3) || /多云|阴/.test(labels) || maxPrecip >= 60) return { type: "cloudy", image: images.cloudy, dot: "#64748b" };
  if (hasCode(0, 1) || /晴/.test(labels)) return { type: "clear", image: images.clear, dot: "#22c55e" };
  return { type: "fallback", image: images.fog, dot: "#16a3b8" };
}

function factorNames(data) {
  return new Set((data?.risk_factors || []).map((item) => item.name));
}

function pickInsight(data) {
  const names = factorNames(data);
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
      body: `${mood.quote} ${mood.note}`,
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

function equipmentFor(data) {
  const names = factorNames(data);
  const activity = data?.plan?.activity_type || $("#activity").value;
  const items = ["饮用水", "手机满电", "基础雨具", "轻便急救包"];
  if (names.has("降水")) items.push("防滑鞋", "防水袋", "备用袜子");
  if (names.has("雷暴/强对流")) items.push("室内避险点清单", "取消通知模板");
  if (names.has("强风") || names.has("风偏大")) items.push("固定绳", "收纳袋", "防风外套");
  if (names.has("高温体感")) items.push("电解质", "遮阳帽", "冰袖/速干衣");
  if (names.has("强紫外线") || names.has("紫外线")) items.push("防晒霜", "太阳镜");
  if (activity === "cycling") items.push("车灯", "头盔", "补胎工具");
  if (activity === "camping") items.push("地钉", "防潮垫", "备用照明");
  if (activity === "hiking") items.push("登山杖", "离线地图", "头灯");
  return [...new Set(items)];
}

function thresholdFor(data) {
  const activity = data?.plan?.activity_type || $("#activity").value;
  const base = [
    "雷暴/强对流：直接取消户外计划",
    "降水概率 ≥ 80%：改期或启用室内方案",
    "阵风 ≥ 39 km/h：取消帐篷、展架、骑行等受风活动",
    "体感温度 ≥ 35°C：避开正午并增加补水点"
  ];
  if (activity === "cycling") base.push("骑行专属：阵风 ≥ 28 km/h 即降速或改线");
  if (activity === "camping") base.push("露营专属：夜间降水或强风触发撤营预案");
  if ($("#children").checked || $("#elderly").checked) base.push("敏感人群：阈值下调一级，谨慎条件按不推荐处理");
  return base;
}

function explanationCards(data) {
  const names = factorNames(data);
  const cards = [];
  if (names.has("雷暴/强对流")) cards.push(["雷暴为什么一票否决", "雷电可在降雨前后影响户外区域，空旷地、树下、水边和金属设施附近都不安全。"]);
  if (names.has("降水")) cards.push(["降水为什么影响骑行/徒步", "湿滑路面会拉长刹车距离，低洼积水会遮挡坑洼，雨中能见度下降也会增加碰撞风险。"]);
  if (names.has("强风") || names.has("风偏大")) cards.push(["阵风为什么危险", "阵风不是稳定风，突发横风会让骑行偏航，也会掀动帐篷、展架、横幅等受风物。"]);
  if (names.has("高温体感")) cards.push(["体感温度为什么比气温重要", "湿度高时汗液蒸发慢，身体散热效率下降，实际热压力会明显高于气温数字。"]);
  if (!cards.length) cards.push(["为什么仍要复查", "预报会滚动更新，活动前 2 小时和 30 分钟复查能捕捉临近降水、阵风和雷暴变化。"]);
  return cards;
}

function emergencyPlan(data) {
  if (!data) return ["完成一次评估后自动生成集合、撤离、备选和通知预案。"];
  const location = data.plan?.location || $("#location").value;
  const activity = data.plan?.activity_label || activityLabel($("#activity").value);
  const bad = data.level === "不推荐";
  return [
    `决策：${bad ? "建议取消/改期，启用室内备选。" : data.level === "谨慎" ? "保留计划，但设置复查点和撤离条件。" : "可执行，保留常规备选。"}`,
    `集合：${location} 附近选择有遮蔽、可停车、可快速撤离的位置。`,
    `备选：${activity} 改为室内训练、咖啡集合、装备维护或短线低风险路线。`,
    `通知：活动前 6 小时发布初判，2 小时发布最终判断，30 分钟只做临近变化提醒。`,
    `安全：指定 1 名联系人，确认所有参与者知道取消阈值和撤离方向。`
  ];
}

function organizerPlan(data) {
  if (!data) return ["组织者模式会自动汇总：是否取消、备选方案、群通知、物资清单、安全提示。"];
  return [
    `<b>是否取消：</b>${data.level === "不推荐" ? "取消或改期" : data.level === "谨慎" ? "暂不取消，临近复查" : "按计划执行"}`,
    `<b>备选方案：</b>${data.level === "适合" ? "保留室内集合点即可" : "准备室内场地或缩短路线"}`,
    `<b>群通知：</b>${data.notification || "完成评估后生成通知文案"}`,
    `<b>物资：</b>${equipmentFor(data).slice(0, 8).join("、")}`,
    `<b>安全提示：</b>${(data.contingency || []).join("；")}`
  ];
}

function crowdAdaptation(data) {
  const score = Number(data?.score ?? 0);
  const rows = [
    ["普通成人", score, score >= 75 ? "适合" : score >= 55 ? "谨慎" : "不推荐"],
    ["儿童/亲子", score - 8, score - 8 >= 75 ? "适合" : score - 8 >= 55 ? "谨慎" : "不推荐"],
    ["老人/低体能", score - 12, score - 12 >= 75 ? "适合" : score - 12 >= 55 ? "谨慎" : "不推荐"],
    ["组织者/多人", score - 10, score - 10 >= 75 ? "适合" : score - 10 >= 55 ? "谨慎" : "不推荐"]
  ];
  return rows;
}

function renderDerivedTools(data = state.lastPlan) {
  $("#equipment-list").innerHTML = equipmentFor(data).map((item) => `<li>${item}</li>`).join("");
  $("#threshold-list").innerHTML = thresholdFor(data).map((item) => `<li>${item}</li>`).join("");
  $("#explain-cards").innerHTML = explanationCards(data).map(([title, body]) => `
    <div class="rounded-lg bg-fog p-3">
      <p class="text-sm font-bold text-ink">${title}</p>
      <p class="mt-1 text-sm leading-relaxed text-muted">${body}</p>
    </div>
  `).join("");
  $("#emergency-plan").innerHTML = emergencyPlan(data).map((item) => `<p>${item}</p>`).join("");
  $("#organizer-plan").innerHTML = organizerPlan(data).map((item) => `<p>${item}</p>`).join("");
  $("#crowd-adaptation").innerHTML = crowdAdaptation(data).map(([name, score, level]) => {
    const meta = levelMeta(level);
    return `
      <div class="flex items-center justify-between rounded-lg bg-fog p-3">
        <span class="text-sm font-bold">${name}</span>
        <span class="font-mono text-sm font-bold ${meta.cls}">${Math.max(0, Math.round(score))} · ${level}</span>
      </div>
    `;
  }).join("");
  renderReminders(data);
  renderSubscriptions();
}

function renderReminders(data = state.lastPlan) {
  const times = ["6 小时", "2 小时", "30 分钟"];
  $("#reminder-list").innerHTML = times.map((time, index) => `
    <div class="rounded-lg bg-fog p-3 text-center">
      <p class="font-mono text-sm font-bold">${time}</p>
      <p class="mt-1 text-[11px] text-muted">${index === 0 ? "初判" : index === 1 ? "最终判断" : "临近变化"}</p>
    </div>
  `).join("");
  if (data) {
    const action = data.level === "不推荐" ? "风险升高时立即生成取消通知。" : "若风险升高到谨慎/不推荐，自动生成改期文案。";
    $("#subscription-preview").textContent = `${data.plan?.location || "当前地点"} · ${activityLabel(data.plan?.activity_type)}：活动前 6小时/2小时/30分钟复查。${action}`;
  }
}

function renderSubscriptions() {
  $("#subscription-list").innerHTML = state.subscriptions.map((item, index) => `
    <div class="flex items-center justify-between rounded-lg border border-line p-3">
      <div>
        <p class="text-sm font-bold">${item.location}</p>
        <p class="text-xs text-muted">${item.activity} · ${item.time} · ${item.reminders}</p>
      </div>
      <button class="remove-sub rounded bg-fog px-2 py-1 text-xs font-bold" data-index="${index}" type="button">删除</button>
    </div>
  `).join("") || `<p class="text-sm text-muted">暂无订阅。</p>`;
}

function renderPlan(data) {
  state.lastPlan = data;
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
  renderDerivedTools(data);
}

async function fetchRisk(payload) {
  const response = await fetch("/api/activity-risk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await response.json();
  if (!response.ok || data.error) throw new Error(data.error || "评估失败");
  return data;
}

async function evaluateRisk() {
  $("#risk-submit").disabled = true;
  $("#risk-submit").textContent = "评估中...";
  setStatus("计算中");
  $("#conclusion").textContent = "正在拉取地点级真实小时预报并计算风险...";
  try {
    const payload = planPayload();
    const data = await fetchRisk(payload);
    renderPlan(data);
    saveQueryHistory(payload, data);
    setStatus("真实小时数据");
  } catch (error) {
    $("#conclusion").textContent = `评估失败：${error.message}`;
    setStatus("错误");
  } finally {
    $("#risk-submit").disabled = false;
    $("#risk-submit").textContent = "评估风险";
  }
}

async function runRouteCompare() {
  const locations = $("#compare-locations").value.split(/\n|,|，/).map((item) => item.trim()).filter(Boolean);
  if (!locations.length) return;
  $("#compare-results").innerHTML = `<div class="feature-card"><p>正在生成路线风险图...</p></div>`;
  const results = [];
  for (const location of locations) {
    try {
      const data = await fetchRisk(planPayload({ location }));
      results.push({ location, data });
    } catch (error) {
      results.push({ location, error: error.message });
    }
  }
  $("#compare-results").innerHTML = results.map((item, index) => {
    if (item.error) {
      return `<div class="feature-card risk-high"><h4>${index + 1}. ${item.location}</h4><p>${item.error}</p></div>`;
    }
    const data = item.data;
    const window = data.weather_window || {};
    const meta = levelMeta(data.level);
    const names = factorNames(data);
    const best = data.best_hours?.[0];
    const bestLabel = best ? `${(best.start || best.time || "").slice(11, 16)}-${(best.end || "").slice(11, 16)}` : "暂无";
    return `
      <div class="feature-card ${data.level === "不推荐" ? "risk-high" : data.level === "谨慎" ? "risk-medium" : "risk-low"}">
        <div class="flex items-center justify-between">
          <h4>${index + 1}. ${item.location}</h4>
          <span class="rounded-full px-3 py-1 text-xs font-bold ${meta.bg}">${data.level} · ${data.score}</span>
        </div>
        <div class="mt-3 grid grid-cols-4 gap-2 text-center">
          <div class="rounded bg-fog p-2"><p class="font-mono text-sm font-bold">${fmt(window.max_precip_probability, "%")}</p><p class="text-[10px] text-muted">降水</p></div>
          <div class="rounded bg-fog p-2"><p class="font-mono text-sm font-bold">${fmt(window.max_wind_or_gust)}</p><p class="text-[10px] text-muted">风</p></div>
          <div class="rounded bg-fog p-2"><p class="font-mono text-sm font-bold">${fmt(window.max_apparent_temperature, "°")}</p><p class="text-[10px] text-muted">热</p></div>
          <div class="rounded bg-fog p-2"><p class="font-mono text-sm font-bold">${names.has("雷暴/强对流") ? "有" : "无"}</p><p class="text-[10px] text-muted">雷雨</p></div>
        </div>
        <p class="mt-2 rounded bg-fog p-2 text-sm font-bold">推荐时段：${bestLabel}</p>
        <p class="mt-2 text-xs leading-relaxed text-muted">天气：${(window.weather_labels || []).join("、") || "天气平稳"}</p>
        <p class="mt-3 text-sm leading-relaxed text-muted">${data.conclusion}</p>
      </div>
    `;
  }).join("");
}

async function runCalendar() {
  $("#calendar-results").innerHTML = `<div class="col-span-2 feature-card"><p>正在计算未来 7 天...</p></div>`;
  const base = new Date($("#date").value || new Date().toISOString().slice(0, 10));
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(base);
    date.setDate(base.getDate() + index);
    return date.toISOString().slice(0, 10);
  });
  const cards = [];
  for (const date of days) {
    try {
      const data = await fetchRisk(planPayload({ date }));
      cards.push({ date, data });
    } catch (error) {
      cards.push({ date, error: error.message });
    }
  }
  $("#calendar-results").innerHTML = cards.map((item) => {
    if (item.error) return `<div class="feature-card risk-high"><h4>${item.date.slice(5)}</h4><p>${item.error}</p></div>`;
    const meta = levelMeta(item.data.level);
    return `
      <button class="feature-card text-left ${item.data.level === "不推荐" ? "risk-high" : item.data.level === "谨慎" ? "risk-medium" : "risk-low"}" type="button">
        <div class="flex items-center justify-between">
          <h4>${item.date.slice(5)}</h4>
          <span class="${meta.cls} font-mono text-sm font-bold">${item.data.score}</span>
        </div>
        <p class="mt-1 font-bold ${meta.cls}">${item.data.level}</p>
        <p class="mt-1">${(item.data.weather_window?.weather_labels || []).join("、") || "天气平稳"}</p>
      </button>
    `;
  }).join("");
}

async function askKnowledge() {
  $("#qa-answer").textContent = "正在通过 LangChain 组织天气数据与知识库上下文...";
  $("#qa-backend").textContent = "生成中";
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: $("#qa-question").value.trim() })
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || "请求失败");
    $("#qa-answer").textContent = data.answer;
    if (data.answer_backend === "domain-guard") {
      $("#qa-backend").textContent = "非天气领域问题已拦截";
    } else {
      $("#qa-backend").textContent = data.llm?.connected
        ? `已接入大模型：${data.answer_backend} · ${data.llm.model}`
        : `未接入外部大模型：${data.answer_backend || "langchain-local-rag"} · 本地 RAG 兜底`;
    }
  } catch (error) {
    $("#qa-answer").textContent = `请求失败：${error.message}`;
    $("#qa-backend").textContent = "请求失败";
  }
}

function activateView(view) {
  decisionSections.forEach((id) => {
    const node = $(`#${id}`);
    if (node) node.classList.toggle("hidden", view !== "decision");
  });
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `${view}-section`);
  });
  document.querySelectorAll(".module-action, .nav-action").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("bg-primary", active && button.classList.contains("module-action"));
    button.classList.toggle("bg-carbon", active && button.classList.contains("nav-action"));
    button.classList.toggle("text-white", active);
    button.classList.toggle("text-muted", !active);
    if (button.classList.contains("module-action")) button.classList.toggle("bg-white", !active);
    if (button.classList.contains("nav-action")) button.classList.toggle("rounded-xl", active);
  });
  $("#workspace-nav").scrollIntoView({ behavior: "smooth", block: "start" });
}

function scrollToTarget(targetId) {
  const target = $(`#${targetId}`);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

function openWeatherAi() {
  activateView("decision");
  renderQaQuickQuestions();
  $("#qa-panel").classList.remove("hidden");
  $("#qa-toggle").scrollIntoView({ behavior: "smooth", block: "center" });
}

function applyScenario(button) {
  $("#activity").value = button.dataset.activity;
  $("#time").value = button.dataset.time;
  $("#duration").value = button.dataset.duration;
  renderQaQuickQuestions();
  activateView("decision");
}

function addSubscription() {
  const payload = planPayload();
  state.subscriptions.unshift({
    location: payload.location || "未命名地点",
    activity: activityLabel(payload.activity_type),
    time: `${payload.date} ${payload.start_time}`,
    reminders: "6小时 / 2小时 / 30分钟"
  });
  state.subscriptions = state.subscriptions.slice(0, 8);
  localStorage.setItem("meteorisk_subscriptions", JSON.stringify(state.subscriptions));
  renderSubscriptions();
}

function addFeedback(label) {
  const payload = planPayload();
  state.feedback.unshift({
    label,
    note: $("#feedback-note").value.trim(),
    location: payload.location,
    activity: activityLabel(payload.activity_type),
    date: payload.date,
    score: state.lastPlan?.score,
    level: state.lastPlan?.level,
    createdAt: new Date().toLocaleString("zh-CN")
  });
  state.feedback = state.feedback.slice(0, 20);
  localStorage.setItem("meteorisk_feedback", JSON.stringify(state.feedback));
  $("#feedback-note").value = "";
  renderFeedback();
}

function renderFeedback() {
  const hot = state.feedback.filter((item) => item.label.includes("热")).length;
  const wind = state.feedback.filter((item) => item.label.includes("风")).length;
  const rain = state.feedback.filter((item) => item.label.includes("雨")).length;
  const comfort = state.feedback.filter((item) => item.label.includes("舒服")).length;
  const tips = [];
  if (hot) tips.push(`你有 ${hot} 次反馈“太热”，建议把高温阈值再下调 2°C。`);
  if (wind) tips.push(`你对风更敏感，骑行/露营建议提前避开阵风偏大的窗口。`);
  if (rain) tips.push(`出现过降雨误判，之后建议活动前 30 分钟必须复查雷达/临近预报。`);
  if (comfort) tips.push(`舒适反馈会沉淀为地点经验，后续可优先推荐相似天气窗口。`);
  $("#personal-model").textContent = tips.join(" ") || "暂无反馈。完成一次记录后，这里会提示你的偏好。";
  $("#feedback-history").innerHTML = state.feedback.map((item) => `
    <div class="feature-card">
      <div class="flex items-center justify-between">
        <h4>${item.location || "未命名地点"}</h4>
        <span class="text-xs font-bold text-muted">${item.createdAt}</span>
      </div>
      <p class="mt-1">${item.activity} · ${item.label} · ${item.level || "未评估"} ${item.score ?? ""}</p>
      ${item.note ? `<p class="mt-1">${item.note}</p>` : ""}
    </div>
  `).join("") || `<div class="feature-card"><p>还没有复盘记录。</p></div>`;
}

function init() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  $("#date").value = date.toISOString().slice(0, 10);
  updateRing(undefined, "待评估");
  renderMetrics(null);
  renderFactors([]);
  renderBestHours([]);
  renderDerivedTools(null);
  renderFeedback();
  renderQueryHistory();
  renderQaQuickQuestions();

  $("#risk-form").addEventListener("submit", (event) => {
    event.preventDefault();
    evaluateRisk();
  });
  ["#location", "#activity", "#date", "#time", "#duration"].forEach((selector) => {
    const node = $(selector);
    node.addEventListener("input", renderQaQuickQuestions);
    node.addEventListener("change", renderQaQuickQuestions);
  });
  $("#use-current-location").addEventListener("click", requestCurrentLocation);
  $("#clear-query-history").addEventListener("click", () => {
    state.queryHistory = [];
    localStorage.removeItem("meteorisk_query_history");
    renderQueryHistory();
    $("#geolocation-status").textContent = "查询历史已清空。";
  });
  $("#query-history-list").addEventListener("click", (event) => {
    const deleteButton = event.target.closest(".delete-query-history");
    if (deleteButton) {
      deleteQueryHistory(Number(deleteButton.dataset.index));
      return;
    }
    const restoreButton = event.target.closest(".query-history-restore");
    if (!restoreButton) return;
    restoreQueryHistory(Number(restoreButton.dataset.index));
  });
  $("#fill-demo").addEventListener("click", () => {
    $("#location").value = "广州天河体育中心";
    $("#activity").value = "cycling";
    $("#time").value = "18:00";
    $("#duration").value = "2";
    $("#people").value = "4";
    $("#children").checked = false;
    $("#elderly").checked = false;
    renderQaQuickQuestions();
  });
  $("#qa-toggle").addEventListener("click", () => {
    renderQaQuickQuestions();
    $("#qa-panel").classList.toggle("hidden");
  });
  $("#qa-quick-questions").addEventListener("click", (event) => {
    const button = event.target.closest(".qa-quick");
    if (!button) return;
    $("#qa-question").value = button.dataset.question || "";
    $("#qa-question").focus();
  });
  $("#qa-submit").addEventListener("click", askKnowledge);
  $("#copy-notice").addEventListener("click", async () => {
    await navigator.clipboard.writeText($("#notice").textContent);
    $("#copy-notice").innerHTML = '<span class="material-symbols-outlined text-lg">done</span>';
    setTimeout(() => {
      $("#copy-notice").innerHTML = '<span class="material-symbols-outlined text-lg">content_copy</span>';
    }, 1500);
  });
  $("#copy-emergency").addEventListener("click", async () => {
    await navigator.clipboard.writeText(emergencyPlan(state.lastPlan).join("\n"));
    $("#copy-emergency").textContent = "已复制";
    setTimeout(() => { $("#copy-emergency").textContent = "复制"; }, 1500);
  });
  $("#compare-run").addEventListener("click", runRouteCompare);
  $("#calendar-run").addEventListener("click", runCalendar);
  $("#add-subscription").addEventListener("click", addSubscription);
  $("#apply-coordinates").addEventListener("click", () => {
    const lat = $("#lat-input").value.trim();
    const lon = $("#lon-input").value.trim();
    if (lat && lon) $("#location").value = `${lat},${lon}`;
    renderQaQuickQuestions();
    activateView("decision");
  });
  $("#menu-toggle").addEventListener("click", () => {
    activateView("tools");
  });
  document.querySelectorAll(".module-action, .nav-action").forEach((button) => {
    button.addEventListener("click", () => activateView(button.dataset.view));
  });
  document.querySelectorAll(".menu-action").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.target === "qa-toggle") openWeatherAi();
      if (button.dataset.view) activateView(button.dataset.view);
    });
  });
  document.querySelectorAll(".scenario-action").forEach((button) => {
    button.addEventListener("click", () => applyScenario(button));
  });
  document.querySelectorAll(".map-point").forEach((button) => {
    button.addEventListener("click", () => {
      $("#location").value = button.dataset.location;
      renderQaQuickQuestions();
      activateView("decision");
    });
  });
  document.querySelectorAll(".feedback-action").forEach((button) => {
    button.addEventListener("click", () => addFeedback(button.dataset.feedback));
  });
  $("#subscription-list").addEventListener("click", (event) => {
    const button = event.target.closest(".remove-sub");
    if (!button) return;
    state.subscriptions.splice(Number(button.dataset.index), 1);
    localStorage.setItem("meteorisk_subscriptions", JSON.stringify(state.subscriptions));
    renderSubscriptions();
  });
  startDesktopHeartbeat();
}

init();
