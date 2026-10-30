const stages = {
  discover: {
    kicker: "STAGE 01 / DISCOVER",
    title: "Start with roles<br>from your sources.",
    copy: "Connect public Greenhouse, Lever, and Ashby career boards. Neural Ant searches those configured sources and puts matching roles in your workspace.",
    detail: "Sources: boards you select"
  },
  review: {
    kicker: "STAGE 02 / REVIEW",
    title: "See the evidence<br>behind each match.",
    copy: "Review fit, location, compensation, and any available sponsorship evidence. Employer filing history is shown as history, never as a promise for a specific role.",
    detail: "You decide which roles are worth pursuing"
  },
  prepare: {
    kicker: "STAGE 03 / PREPARE",
    title: "Shape a draft<br>from your real experience.",
    copy: "Create a resume draft for a role and verify every change. Local drafting is available; sending profile and job text to an external AI provider requires confirmation.",
    detail: "Draft only · verify every claim"
  },
  assist: {
    kicker: "STAGE 04 / ASSIST",
    title: "Move through the form<br>with a human checkpoint.",
    copy: "Choose an application link in the Chrome extension, open it, and fill supported empty fields from your saved profile. Review the answers, attach your file, complete attestations, and submit yourself.",
    detail: "The extension stops before submission"
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
activateStage("discover");
