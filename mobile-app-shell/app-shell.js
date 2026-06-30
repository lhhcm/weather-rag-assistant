const input = document.querySelector("#server-url");
const statusEl = document.querySelector("#status");
const saved = localStorage.getItem("weatherRiskServerUrl");
input.value = saved || "http://10.0.2.2:8765";

function normalizeUrl(value) {
  const trimmed = value.trim().replace(/\/+$/, "");
  if (!trimmed) return "";
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `http://${trimmed}`;
}

async function openAssistant() {
  const baseUrl = normalizeUrl(input.value);
  if (!baseUrl) {
    statusEl.textContent = "请先填写服务地址";
    return;
  }
  statusEl.textContent = "正在检查服务...";
  try {
    const response = await fetch(`${baseUrl}/api/health`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    localStorage.setItem("weatherRiskServerUrl", baseUrl);
    window.location.href = `${baseUrl}/`;
  } catch (error) {
    statusEl.textContent = "没有连上服务，请确认电脑和手机在同一网络，服务已启动。";
  }
}

document.querySelector("#open-app").addEventListener("click", openAssistant);
document.querySelector("#use-emulator").addEventListener("click", () => {
  input.value = "http://10.0.2.2:8765";
  openAssistant();
});
