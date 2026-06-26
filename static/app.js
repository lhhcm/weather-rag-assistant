const form = document.querySelector("#ask-form");
const questionInput = document.querySelector("#question");
const askButton = document.querySelector("#ask-button");
const answerEl = document.querySelector("#answer");
const statusEl = document.querySelector("#status");
const quickQuestionsEl = document.querySelector("#quick-questions");
const intentBadge = document.querySelector("#intent-badge");
const sourcesEl = document.querySelector("#sources");
const sourceCountEl = document.querySelector("#source-count");

const riskForm = document.querySelector("#risk-form");
const riskButton = document.querySelector("#risk-button");
const riskScore = document.querySelector("#risk-score");
const riskLevel = document.querySelector("#risk-level");
const riskConclusion = document.querySelector("#risk-conclusion");
const scoreRing = document.querySelector("#score-ring");
const riskMetrics = document.querySelector("#risk-metrics");
const riskFactors = document.querySelector("#risk-factors");
const factorCount = document.querySelector("#factor-count");
const bestHours = document.querySelector("#best-hours");
const contingencyList = document.querySelector("#contingency-list");
const notificationText = document.querySelector("#notification-text");
const riskSource = document.querySelector("#risk-source");

const fallbackQuestions = [
  "厄尔尼诺是什么？",
  "副热带高压为什么会影响高温？",
  "露点温度和相对湿度有什么区别？",
  "雷暴天气为什么不适合骑行？",
];

function setStatus(text, mode = "") {
  statusEl.className = `status ${mode}`.trim();
  statusEl.querySelector("span:last-child").textContent = text;
}

function formatValue(value, suffix = "") {
  if (value === null || value === undefined || value === "") return "--";
  return `${value}${suffix}`;
}

function setDefaultDate() {
  const date = new Date();
  date.setDate(date.getDate() + 1);
  document.querySelector("#risk-date").value = date.toISOString().slice(0, 10);
}

function renderRiskMetrics(window) {
  if (!window) {
    riskMetrics.innerHTML = "";
    return;
  }
  const metrics = [
    ["降水概率", formatValue(window.max_precip_probability, "%")],
    ["最高体感", formatValue(window.max_apparent_temperature, "C")],
    ["风/阵风", formatValue(window.max_wind_or_gust, " km/h")],
    ["UV", formatValue(window.max_uv_index)],
    ["天气", (window.weather_labels || []).join("、") || "--"],
    ["时间", `${window.start || "--"} 至 ${window.end || "--"}`],
  ];
  riskMetrics.innerHTML = metrics
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderFactorList(factors) {
  factorCount.textContent = `${factors.length} 项`;
  riskFactors.innerHTML = factors
    .map(
      (risk) => `
        <div class="risk ${risk.level}">
          <strong>${risk.name} · -${risk.points}</strong>
          <span>${risk.reason}</span>
        </div>
      `,
    )
    .join("");
}

function renderBestHours(hours) {
  if (!hours || hours.length === 0) {
    bestHours.innerHTML = `<div class="risk low"><strong>暂无建议</strong><span>当前日期没有可比较的白天时段。</span></div>`;
    return;
  }
  bestHours.innerHTML = hours
    .map(
      (hour) => `
        <div class="risk ${hour.score >= 75 ? "low" : "medium"}">
          <strong>${hour.time.slice(11, 16)} · ${Math.round(hour.score)} 分</strong>
          <span>${hour.weather}</span>
        </div>
      `,
    )
    .join("");
}

function renderContingency(items, notification) {
  contingencyList.innerHTML = items.map((item) => `<li>${item}</li>`).join("");
  notificationText.textContent = notification;
}

async function evaluateRisk() {
  riskButton.disabled = true;
  riskConclusion.textContent = "正在拉取真实小时级天气预报并计算风险...";
  setStatus("评估中", "");

  const payload = {
    city: document.querySelector("#risk-city").value.trim(),
    activity_type: document.querySelector("#risk-activity").value,
    date: document.querySelector("#risk-date").value,
    start_time: document.querySelector("#risk-time").value,
    duration_hours: Number(document.querySelector("#risk-duration").value),
    people: Number(document.querySelector("#risk-people").value),
    children: document.querySelector("#risk-children").checked,
  };

  try {
    const response = await fetch("/api/activity-risk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || "评估失败");

    riskScore.textContent = data.score;
    riskLevel.textContent = data.level;
    scoreRing.className = `score-ring ${data.level === "适合" ? "good" : data.level === "谨慎" ? "warn" : "bad"}`;
    riskConclusion.textContent = data.conclusion;
    riskSource.textContent = data.data_source?.provider || "真实预报";
    renderRiskMetrics(data.weather_window);
    renderFactorList(data.risk_factors || []);
    renderBestHours(data.best_hours || []);
    renderContingency(data.contingency || [], data.notification || "");
    setStatus("已连接", "ready");
  } catch (error) {
    riskConclusion.textContent = `评估失败：${error.message}`;
    setStatus("异常", "error");
  } finally {
    riskButton.disabled = false;
  }
}

function renderSources(sources) {
  sourceCountEl.textContent = `${sources.length} 条`;
  if (!sources.length) {
    sourcesEl.innerHTML = `<div class="source"><h3>暂无来源</h3><p>完成一次知识问答后会展示知识库命中的片段。</p></div>`;
    return;
  }
  sourcesEl.innerHTML = sources
    .map(
      (source) => `
        <article class="source">
          <h3>${source.title}</h3>
          <p>${source.snippet}</p>
          <div class="meta">
            <span>${source.source}</span>
            <span>score ${source.score}</span>
          </div>
        </article>
      `,
    )
    .join("");
}

async function ask(question) {
  askButton.disabled = true;
  answerEl.textContent = "正在检索气象知识库...";
  setStatus("生成中", "");

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || "请求失败");

    answerEl.textContent = data.answer;
    intentBadge.textContent = data.intent || "综合";
    renderSources(data.sources || []);
    setStatus("已连接", "ready");
  } catch (error) {
    answerEl.textContent = `请求失败：${error.message}`;
    setStatus("异常", "error");
  } finally {
    askButton.disabled = false;
  }
}

function renderQuickQuestions(questions) {
  quickQuestionsEl.innerHTML = questions
    .map((question) => `<button type="button" data-question="${question}">${question}</button>`)
    .join("");
  quickQuestionsEl.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      questionInput.value = button.dataset.question;
      ask(button.dataset.question);
    });
  });
}

riskForm.addEventListener("submit", (event) => {
  event.preventDefault();
  evaluateRisk();
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    questionInput.focus();
    return;
  }
  ask(question);
});

async function init() {
  setDefaultDate();
  renderRiskMetrics(null);
  renderFactorList([]);
  renderBestHours([]);
  renderContingency(["完成评估后自动生成。"], "完成评估后自动生成。");
  renderSources([]);
  renderQuickQuestions(fallbackQuestions);

  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    renderQuickQuestions(data.sample_questions || fallbackQuestions);
    setStatus(`${data.orchestrator || "workflow"} · ${data.documents} 片段`, "ready");
  } catch {
    setStatus("未连接", "error");
  }
}

init();
