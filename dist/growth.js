(function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const request = async (path) => {
    const response = await fetch(`/api${path}`, { credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  };

  function profileStrengthItems(profile, resume) {
    const history = Array.isArray(profile.employment_history) ? profile.employment_history : [];
    const education = Array.isArray(profile.education_history) ? profile.education_history : [];
    const certifications = Array.isArray(profile.certifications) ? profile.certifications : [];
    return [
      { label: "Resume uploaded", ok: Boolean(resume), tip: "Upload the current resume and verify the extracted fields." },
      { label: "Name and contact", ok: Boolean(profile.name && profile.email && profile.phone), tip: "Add your name, email, and phone so forms can be reviewed faster." },
      { label: "Target roles", ok: Array.isArray(profile.target_titles) && profile.target_titles.length > 0, tip: "Add the role titles you are actually targeting." },
      { label: "Skills and tools", ok: Array.isArray(profile.skills) && profile.skills.length >= 3, tip: "Add at least three verified skills or tools." },
      { label: "Location and work mode", ok: Boolean(profile.location && Array.isArray(profile.work_modes) && profile.work_modes.length > 0), tip: "Set your current location and acceptable work modes." },
      { label: "Experience history", ok: history.length > 0 || Boolean(profile.current_company && profile.role), tip: "Add verified employment history or current company and role." },
      { label: "Education or certifications", ok: Boolean(profile.education || education.length > 0 || certifications.length > 0), tip: "Add education or certifications when relevant." },
      { label: "Professional links", ok: Boolean(profile.linkedin_url || profile.github_url || profile.portfolio_url || profile.website_url), tip: "Add a professional link when you want it reused in supported forms." },
    ];
  }

  function ensureStrengthCard() {
    if ($("profileStrength")) return;
    const profile = $("profile");
    const head = profile?.querySelector(".pagehead");
    if (!head) return;
    const card = document.createElement("div");
    card.className = "card profile-strength";
    card.id = "profileStrength";
    card.setAttribute("aria-live", "polite");
    head.insertAdjacentElement("afterend", card);
  }

  function renderStrength(profile, resume) {
    ensureStrengthCard();
    const card = $("profileStrength");
    if (!card) return;
    const items = profileStrengthItems(profile, resume);
    const complete = items.filter((item) => item.ok).length;
    const percent = Math.round((complete / items.length) * 100);
    const missing = items.filter((item) => !item.ok);
    card.innerHTML = `<div class="strength-head"><div><div class="eyebrow">PROFILE READINESS</div><h3>${percent}% ready for matching and supervised autofill</h3><p>${missing.length ? `Complete ${missing.length} item${missing.length === 1 ? "" : "s"} to improve discovery and reduce manual form work.` : "Your baseline is complete. Keep every claim verified."}</p></div><strong>${complete}/${items.length}</strong></div><div class="strength-bar"><span style="width:${percent}%"></span></div><div class="strength-grid">${items.map((item) => `<div class="strength-item ${item.ok ? "complete" : "missing"}"><span>${item.ok ? "✓" : "○"}</span><div><b>${escapeHtml(item.label)}</b><small>${escapeHtml(item.ok ? "Verified or present" : item.tip)}</small></div></div>`).join("")}</div>`;
  }

  function freshnessLabel(job) {
    const checked = job.last_seen || job.first_seen;
    if (!checked) return "";
    const ageHours = Math.max(0, Math.floor((Date.now() - new Date(checked).getTime()) / 3600000));
    const checkedText = ageHours < 1 ? "just now" : ageHours < 24 ? `${ageHours}h ago` : `${Math.floor(ageHours / 24)}d ago`;
    const isNew = job.first_seen && Date.now() - new Date(job.first_seen).getTime() < 86400000;
    return `<span class="job-freshness ${isNew ? "new" : ""}">${isNew ? "New · " : ""}Checked ${escapeHtml(checkedText)}</span>`;
  }

  async function refreshStrength() {
    try {
      const data = await request("/profile");
      renderStrength(data.profile, data.resume);
    } catch (_) {
      // The main application owns error reporting; this enhancement stays quiet offline.
    }
  }

  function configureSourceOptions() {
    const select = $("sourceType");
    const slug = $("sourceSlug");
    if (!select || !slug) return;
    const platformHeading = document.querySelector("#agents h2");
    if (platformHeading) platformHeading.textContent = "Employer boards + public job APIs";
    const additions = [
      ["smartrecruiters", "SmartRecruiters public board"],
      ["adzuna", "Adzuna API"],
      ["usajobs", "USAJOBS API"],
    ];
    additions.forEach(([value, label]) => {
      if (!select.querySelector(`option[value="${value}"]`)) select.insertAdjacentHTML("beforeend", `<option value="${value}">${label}</option>`);
    });
    const update = () => {
      const descriptions = {
        greenhouse: "Employer slug, for example acme.",
        lever: "Employer slug, for example acme.",
        ashby: "Employer slug, for example acme.",
        smartrecruiters: "Company identifier from its SmartRecruiters URL, for example acme.",
        adzuna: "Use country|query|location, for example us|agentic ai engineer|remote. Requires ADZUNA_APP_ID and ADZUNA_APP_KEY in .env.local.",
        usajobs: "Use query|location, for example artificial intelligence|Washington DC. Requires USAJOBS_API_KEY and USAJOBS_USER_AGENT in .env.local.",
      };
      slug.placeholder = valueFor(select) === "adzuna" ? "us|agentic ai engineer|remote" : valueFor(select) === "usajobs" ? "artificial intelligence|Washington DC" : valueFor(select) === "smartrecruiters" ? "company-identifier" : "company-name";
      let hint = slug.parentElement?.querySelector(".source-format-hint");
      if (!hint && slug.parentElement) {
        hint = document.createElement("small");
        hint.className = "source-format-hint";
        hint.style.color = "var(--muted)";
        hint.style.fontSize = "10px";
        slug.parentElement.appendChild(hint);
      }
      if (hint) hint.textContent = descriptions[valueFor(select)] || descriptions.greenhouse;
    };
    const valueFor = (element) => element.value;
    if (!select.__growthSourceWrapped) {
      select.addEventListener("change", update);
      select.__growthSourceWrapped = true;
    }
    update();
  }

  function wrapFunctions() {
    const originalProfile = window.loadProfile;
    if (typeof originalProfile === "function" && !originalProfile.__growthWrapped) {
      const wrappedProfile = async function () {
        const result = await originalProfile.apply(this, arguments);
        await refreshStrength();
        return result;
      };
      wrappedProfile.__growthWrapped = true;
      window.loadProfile = wrappedProfile;
    }

    const originalSave = window.saveProfile;
    if (typeof originalSave === "function" && !originalSave.__growthWrapped) {
      const wrappedSave = async function () {
        const result = await originalSave.apply(this, arguments);
        await refreshStrength();
        return result;
      };
      wrappedSave.__growthWrapped = true;
      window.saveProfile = wrappedSave;
    }

    const originalJobs = window.loadJobs;
    if (typeof originalJobs === "function" && !originalJobs.__growthWrapped) {
      const wrappedJobs = async function () {
        const result = await originalJobs.apply(this, arguments);
        try {
          const profile = await request("/profile");
          const threshold = Math.max(50, Number(profile.profile.match_threshold) || 50);
          const jobs = await request(`/jobs?min_score=${threshold}`);
          document.querySelectorAll("#cloudJobs article.job").forEach((card, index) => {
            const job = jobs[index];
            if (!job) return;
            const heading = card.querySelector("h4");
            if (heading && !heading.querySelector(".job-freshness")) heading.insertAdjacentHTML("beforeend", ` ${freshnessLabel(job)}`);
          });
        } catch (_) {
          // Freshness is supplementary; job results remain usable if the second read fails.
        }
        return result;
      };
      wrappedJobs.__growthWrapped = true;
      window.loadJobs = wrappedJobs;
    }
  }

  const timer = setInterval(() => {
    wrapFunctions();
    configureSourceOptions();
    ensureStrengthCard();
    if (typeof window.loadProfile === "function" && typeof window.loadJobs === "function") clearInterval(timer);
  }, 50);
  setTimeout(() => {
    refreshStrength();
    wrapFunctions();
  }, 500);
})();
