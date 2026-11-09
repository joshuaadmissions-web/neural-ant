const stages = {
  setup: {
    kicker: "STAGE 01 / SETUP",
    title: "Start with your<br>verified profile.",
    copy: "Upload a resume once. Neural Ant extracts the facts it can read and keeps your search preferences in your private workspace.",
    detail: "You correct missing or uncertain profile details"
  },
  scrape: {
    kicker: "STAGE 02 / SCRAPE",
    title: "Search public<br>job sources.",
    copy: "Search configured employer boards and public job indexes in parallel. New results are deduplicated and linked to their source postings.",
    detail: "Public sources only · posting dates are checked"
  },
  rank: {
    kicker: "STAGE 03 / RANK",
    title: "See why a role<br>fits your profile.",
    copy: "Compare technical skills, experience, work style, and career direction. Separate language, eligibility, and location gates make uncertainty visible.",
    detail: "Scores are triage aids, not hiring predictions"
  },
  apply: {
    kicker: "STAGE 04 / APPLY",
    title: "Prepare drafts<br>grounded in your resume.",
    copy: "Create a role-specific resume and cover letter, then review each claim. Open the official posting, complete its form, and submit it yourself.",
    detail: "Drafts only · no form automation or submission"
  }
};

const tabs = [...document.querySelectorAll(".stage-tab")];
const panel = document.querySelector("#stage-panel");
const kicker = document.querySelector("#stage-kicker");
const title = document.querySelector("#stage-title");
const copy = document.querySelector("#stage-copy");
const detail = document.querySelector("#stage-detail");

function activateStage(key, focus = false) {
  const stage = stages[key];
  if (!stage) return;
  tabs.forEach(tab => {
    const selected = tab.dataset.stage === key;
    tab.classList.toggle("active", selected);
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && focus) tab.focus();
  });
  const selectedTab = tabs.find(tab => tab.dataset.stage === key);
  panel.setAttribute("aria-labelledby", selectedTab.id);
  kicker.textContent = stage.kicker;
  title.innerHTML = stage.title;
  copy.textContent = stage.copy;
  detail.textContent = stage.detail;
}

tabs.forEach((tab, index) => {
  tab.addEventListener("click", () => activateStage(tab.dataset.stage));
  tab.addEventListener("keydown", event => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0
      : event.key === "End" ? tabs.length - 1
      : (index + (event.key === "ArrowDown" ? 1 : -1) + tabs.length) % tabs.length;
    activateStage(tabs[next].dataset.stage, true);
  });
});
activateStage("setup");
