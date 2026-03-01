const analyzeBtn = document.getElementById("analyzeBtn");
const youtubeUrlInput = document.getElementById("youtubeUrl");
const loadingEl = document.getElementById("loading");
const errorEl = document.getElementById("error");
const resultsEl = document.getElementById("results");

const videoIdEl = document.getElementById("videoId");
const sampleMetaEl = document.getElementById("sampleMeta");
const positiveCountEl = document.getElementById("positiveCount");
const neutralCountEl = document.getElementById("neutralCount");
const negativeCountEl = document.getElementById("negativeCount");
const commentsListEl = document.getElementById("commentsList");

const positiveThemesEl = document.getElementById("positiveThemes");
const negativeThemesEl = document.getElementById("negativeThemes");
const neutralThemesEl = document.getElementById("neutralThemes");

const sampleButtons = document.querySelectorAll(".sample-btn");
let selectedSampleSize = 50;

sampleButtons.forEach((button) => {
  button.addEventListener("click", () => {
    selectedSampleSize = Number(button.dataset.size);

    sampleButtons.forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");
  });
});

function showLoading(isLoading) {
  loadingEl.classList.toggle("hidden", !isLoading);
  analyzeBtn.disabled = isLoading;

  sampleButtons.forEach((btn) => {
    btn.disabled = isLoading;
  });
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove("hidden");
}

function clearError() {
  errorEl.textContent = "";
  errorEl.classList.add("hidden");
}

function hideResults() {
  resultsEl.classList.add("hidden");
  commentsListEl.innerHTML = "";
  positiveThemesEl.innerHTML = "";
  negativeThemesEl.innerHTML = "";
  neutralThemesEl.innerHTML = "";
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function renderThemeList(element, themes) {
  element.innerHTML = "";

  if (!themes || themes.length === 0) {
    const li = document.createElement("li");
    li.textContent = "None detected";
    element.appendChild(li);
    return;
  }

  themes.forEach((themeGroup) => {
    const li = document.createElement("li");

    const themeName = escapeHtml(themeGroup.theme || "other");
    const themeCount = Number(themeGroup.count || 0);

    let detailsHtml = "";

    if (Array.isArray(themeGroup.details) && themeGroup.details.length > 0) {
      const detailItems = themeGroup.details
        .map((detail) => {
          const detailName = escapeHtml(detail.detail || "general feedback");
          const detailCount = Number(detail.count || 0);
          return `<li>${detailName} (${detailCount})</li>`;
        })
        .join("");

      detailsHtml = `<ul>${detailItems}</ul>`;
    }

    li.innerHTML = `
      <span class="theme-label">${themeName} (${themeCount})</span>
      ${detailsHtml}
    `;

    element.appendChild(li);
  });
}

function renderResults(data) {
  const total = Array.isArray(data.comments) ? data.comments.length : 0;

  const positivePct = total
    ? ((data.summary.positive / total) * 100).toFixed(1)
    : "0.0";
  const neutralPct = total
    ? ((data.summary.neutral / total) * 100).toFixed(1)
    : "0.0";
  const negativePct = total
    ? ((data.summary.negative / total) * 100).toFixed(1)
    : "0.0";

  videoIdEl.textContent = data.video_id || "Unknown";
  sampleMetaEl.textContent = `${total} comments analyzed`;

  positiveCountEl.textContent = `${data.summary.positive} (${positivePct}%)`;
  neutralCountEl.textContent = `${data.summary.neutral} (${neutralPct}%)`;
  negativeCountEl.textContent = `${data.summary.negative} (${negativePct}%)`;

  renderThemeList(positiveThemesEl, data.insights?.positive_themes || []);
  renderThemeList(negativeThemesEl, data.insights?.negative_themes || []);
  renderThemeList(neutralThemesEl, data.insights?.neutral_themes || []);

  commentsListEl.innerHTML = "";

  data.comments.forEach((comment) => {
    const div = document.createElement("div");
    div.className = "comment";

    const author = escapeHtml(comment.author || "Unknown");
    const text = escapeHtml(comment.text || "");
    const sentiment = escapeHtml(comment.sentiment || "neutral");
    const reason = escapeHtml(comment.reason || "No explanation available.");
    const theme = escapeHtml(comment.theme || "other");
    const themeDetail = escapeHtml(comment.theme_detail || "general feedback");

    div.innerHTML = `
      <div class="author">${author}</div>
      <div class="comment-text">${text}</div>
      <div class="sentiment ${sentiment}">
        Sentiment: ${sentiment}
      </div>
      <div class="comment-meta"><strong>Why:</strong> ${reason}</div>
      <div class="comment-meta"><strong>Theme:</strong> ${theme}</div>
      <div class="comment-meta"><strong>Specific area:</strong> ${themeDetail}</div>
    `;

    commentsListEl.appendChild(div);
  });

  resultsEl.classList.remove("hidden");
}

async function analyzeVideo() {
  const youtubeUrl = youtubeUrlInput.value.trim();

  clearError();
  hideResults();

  if (!youtubeUrl) {
    showError("Please enter a YouTube URL.");
    return;
  }

  showLoading(true);

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        youtube_url: youtubeUrl,
        sample_size: selectedSampleSize
      })
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Something went wrong.");
    }

    renderResults(data);
  } catch (error) {
    showError(error.message || "Request failed.");
  } finally {
    showLoading(false);
  }
}

analyzeBtn.addEventListener("click", analyzeVideo);

youtubeUrlInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    analyzeVideo();
  }
});