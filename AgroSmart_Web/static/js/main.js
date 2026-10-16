async function postJSON(url, body = {}) {
  const response = await fetch(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || "Não foi possível concluir a solicitação.");
  return data;
}

const loginForm = document.querySelector("#login-form");
if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.querySelector("#login-message");
    const button = loginForm.querySelector("button");
    button.disabled = true; button.textContent = "Verificando…"; message.textContent = "";
    try {
      const data = await postJSON("/api/login", {device_id: document.querySelector("#device-id").value});
      window.location.href = data.redirect;
    } catch (error) { message.textContent = error.message; }
    finally { button.disabled = false; button.innerHTML = 'Entrar no painel <span>→</span>'; }
  });
}

const logoutButton = document.querySelector("#logout-button");
if (logoutButton) logoutButton.addEventListener("click", async () => {
  try { const data = await postJSON("/api/logout"); window.location.href = data.redirect; }
  catch (_) { window.location.href = "/"; }
});

const irrigationButton = document.querySelector("#irrigate-button");
if (irrigationButton) irrigationButton.addEventListener("click", async () => {
  const message = document.querySelector("#irrigation-message");
  const accepted = window.confirm("Deseja solicitar a irrigação? A bomba poderá funcionar por até 10 segundos. Confirme que a área está segura.");
  if (!accepted) return;
  irrigationButton.disabled = true; message.textContent = "Enviando comando…";
  try {
    const data = await postJSON("/api/irrigation", {confirm: true});
    message.style.color = "#39764b";
    message.textContent = `${data.message} Limite: ${data.max_seconds}s.`;
  } catch (error) { message.style.color = "#a34a3d"; message.textContent = error.message; }
  finally { irrigationButton.disabled = false; }
});

const reportDeviceId = window.AGRO_DEVICE_ID;
let reportHistory = [];
async function loadReport() {
  if (!reportDeviceId) return;
  const refresh = document.querySelector("#refresh-button");
  if (refresh) refresh.disabled = true;
  try {
    const response = await fetch(`/api/telemetry/${encodeURIComponent(reportDeviceId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Não foi possível carregar as leituras.");
    const latest = data.latest;
    reportHistory = data.history || [];
    if (latest) {
      document.querySelector("#moisture").innerHTML = `${Number(latest.moisture).toFixed(1)}<small>%</small>`;
      document.querySelector("#temperature").innerHTML = `${Number(latest.temperature).toFixed(1)}<small>°C</small>`;
      document.querySelector("#ph").textContent = Number(latest.ph).toFixed(1);
      document.querySelector("#moisture-bar").style.width = `${Math.max(0, Math.min(100, Number(latest.moisture)))}%`;
      document.querySelector("#temperature-status").textContent = "Leitura recebida";
      document.querySelector("#ph-status").textContent = Number(latest.ph) < 7 ? "Ácido (estimativa)" : Number(latest.ph) > 7 ? "Alcalino (estimativa)" : "Neutro (estimativa)";
      document.querySelector("#last-updated").textContent = `Atualizado: ${formatDate(latest.created_at)}`;
      const latestAge = Date.now() - new Date(latest.created_at).getTime();
      document.querySelector("#demo-warning").style.display = latestAge > 5 * 60 * 1000 ? "flex" : "none";
    }
    const tbody = document.querySelector("#history-body");
    tbody.innerHTML = "";
    if (!reportHistory.length) {
      tbody.innerHTML = '<tr><td colspan="4">Ainda não há leituras enviadas.</td></tr>';
    } else {
      reportHistory.forEach(row => {
        const tr = document.createElement("tr");
        [formatDate(row.created_at), `${Number(row.moisture).toFixed(1)}%`, `${Number(row.temperature).toFixed(1)} °C`, Number(row.ph).toFixed(1)].forEach(value => {
          const td = document.createElement("td"); td.textContent = value; tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }
  } catch (error) {
    document.querySelector("#history-body").innerHTML = `<tr><td colspan="4">${escapeHTML(error.message)}</td></tr>`;
  } finally { if (refresh) refresh.disabled = false; }
}
function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("pt-BR");
}
function escapeHTML(value) {
  return String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
}
const refreshButton = document.querySelector("#refresh-button");
if (refreshButton) { refreshButton.addEventListener("click", loadReport); loadReport(); }
const downloadButton = document.querySelector("#download-report");
if (downloadButton) downloadButton.addEventListener("click", () => {
  if (!reportHistory.length) { alert("Não há dados para baixar ainda."); return; }
  const rows = [["Data e hora","Umidade (%)","Temperatura (°C)","pH"], ...reportHistory.map(r => [formatDate(r.created_at), r.moisture, r.temperature, r.ph])];
  const csv = "\uFEFF" + rows.map(row => row.map(value => `"${String(value ?? "").replace(/"/g,'""')}"`).join(";")).join("\r\n");
  const blob = new Blob([csv], {type:"text/csv;charset=utf-8;"});
  const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `relatorio-agrosmart-${reportDeviceId}.csv`; link.click(); URL.revokeObjectURL(link.href);
});
