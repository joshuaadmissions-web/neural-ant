(function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);

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

  function renderStrength(profile, resume) {
    const head = $("profile")?.querySelector(".pagehead");
    if (!head) return;
    let card = $("profileStrength");
    if (!card) {
      card = document.createElement("div");
      card.className = "card profile-strength";
      card.id = "profileStrength";
      card.setAttribute("aria-live", "polite");
      head.insertAdjacentElement("afterend", card);
    }
    const items = profileStrengthItems(profile, resume);
    const complete = items.filter((item) => item.ok).length;
    const missing = items.length - complete;
    const percent = Math.round((complete / items.length) * 100);
    const details = items.map((item) => '<div class="strength-item ' + (item.ok ? 'complete' : 'missing') + '"><span>' + (item.ok ? '✓' : '○') + '</span><div><b>' + escapeHtml(item.label) + '</b><small>' + escapeHtml(item.ok ? 'Verified or present' : item.tip) + '</small></div></div>').join('');
    const note = missing ? 'Complete ' + missing + ' item' + (missing === 1 ? '' : 's') + ' to improve discovery and reduce manual form work.' : 'Your baseline is complete. Keep every claim verified.';
    card.innerHTML = '<div class="strength-head"><div><div class="eyebrow">PROFILE READINESS</div><h3>' + percent + '% ready for matching and supervised autofill</h3><p>' + note + '</p></div><strong>' + complete + '/' + items.length + '</strong></div><div class="strength-bar"><span style="width:' + percent + '%"></span></div><div class="strength-grid">' + details + '</div>';
  }

  function configureSourceOptions() {
    const select = $("sourceType");
    const slug = $("sourceSlug");
    if (!select || !slug || select.dataset.growthConfigured) return;
    select.dataset.growthConfigured = "true";
    const additions = [
      ["smartrecruiters", "SmartRecruiters public board"],
      ["adzuna", "Adzuna API"],
      ["usajobs", "USAJOBS API"],
    ];
    additions.forEach(([value, label]) => {
      if (!select.querySelector("option[value='" + value + "']")) select.insertAdjacentHTML("beforeend", '<option value="' + value + '">' + label + '</option>');
    });
    const descriptions = {
      greenhouse: "Employer slug, for example acme.",
      lever: "Employer slug, for example acme.",
      ashby: "Employer slug, for example acme.",
      smartrecruiters: "Company identifier from its SmartRecruiters URL, for example acme.",
      adzuna: "Use country|query|location, for example us|agentic ai engineer|remote. Requires Adzuna credentials in .env.local.",
      usajobs: "Use query|location, for example artificial intelligence|Washington DC. Requires USAJOBS credentials in .env.local.",
    };
    const update = () => {
      const value = select.value;
      slug.placeholder = value === "adzuna" ? "us|agentic ai engineer|remote" : value === "usajobs" ? "artificial intelligence|Washington DC" : value === "smartrecruiters" ? "company-identifier" : "company-name";
      let hint = slug.parentElement?.querySelector(".source-format-hint");
      if (!hint && slug.parentElement) {
        hint = document.createElement("small");
        hint.className = "source-format-hint";
        hint.style.color = "var(--muted)";
        hint.style.fontSize = "10px";
        slug.parentElement.appendChild(hint);
      }
      if (hint) hint.textContent = descriptions[value] || descriptions.greenhouse;
    };
    select.addEventListener("change", update);
    update();
  }

  window.addEventListener("neural-ant:profile-updated", (event) => {
    const { profile, resume } = event.detail || {};
    if (profile) renderStrength(profile, resume);
  });
  configureSourceOptions();
})();
