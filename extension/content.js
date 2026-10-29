(() => {
  if (window.__neuralAntInstalled) return;
  window.__neuralAntInstalled = true;

  let banner;
  let dismissed = false;
  let timer;
  const norm = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

  function visible(element) {
    return !!element && !element.disabled && element.getClientRects().length > 0;
  }

  function fieldText(element) {
    const labels = [...(element.labels || [])].map(label => label.innerText || label.textContent || '');
    const labelledBy = (element.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map(id => document.getElementById(id)?.innerText || '').join(' ');
    return norm([
      ...labels,
      labelledBy,
      element.getAttribute('aria-label'),
      element.getAttribute('placeholder'),
      element.getAttribute('name'),
      element.id,
      element.closest('label')?.innerText,
    ].filter(Boolean).join(' '));
  }

  function nearbyQuestion(element) {
    const group = element.closest('fieldset,[role="group"]');
    if (group) return norm(group.innerText || group.textContent);
    let parent = element.parentElement;
    for (let depth = 0; parent && depth < 4; depth++, parent = parent.parentElement) {
      const text = norm(parent.innerText || parent.textContent);
      if (text.length < 1200 && /how many years|employment sponsorship|authorized to work|state do you currently reside/.test(text)) return text;
    }
    return fieldText(element);
  }

  function isApplicationPage() {
    const controls = [...document.querySelectorAll('input,select,textarea,[contenteditable="true"]')].filter(visible);
    if (controls.length < 2) return false;
    const context = norm(`${location.hostname} ${document.title} ${[...document.querySelectorAll('h1,h2')].map(x => x.innerText).join(' ')} ${document.body?.innerText?.slice(0, 5000)}`);
    const fieldSignals = new Set();
    for (const element of controls) {
      const text = fieldText(element);
      if (/full name|first name|your name/.test(text)) fieldSignals.add('name');
      if (/email|e mail/.test(text)) fieldSignals.add('email');
      if (/phone|mobile|telephone/.test(text)) fieldSignals.add('phone');
      if (/resume|curriculum vitae/.test(text)) fieldSignals.add('resume');
      if (/current company|current employer/.test(text)) fieldSignals.add('company');
    }
    const explicit = /submit (your )?application|job application|employment application|apply for this (job|role)|application questions/.test(context);
    const atsOrCareer = /lever\.co|greenhouse\.io|ashbyhq\.com|workday|careers?|job application|apply now/.test(context);
    return explicit || (fieldSignals.size >= 2 && atsOrCareer);
  }

  function ensureBanner() {
    if (dismissed || banner || !isApplicationPage()) return;
    const host = document.createElement('div');
    host.id = 'neural-ant-assistant-host';
    host.style.cssText = 'all:initial;position:fixed;z-index:2147483647;right:18px;bottom:18px;width:300px;height:116px;';
    const shadow = host.attachShadow({ mode: 'closed' });
    shadow.innerHTML = `<style>
      *{box-sizing:border-box}section{font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#16251d;background:#fff;border:1px solid #dce8df;border-radius:14px;box-shadow:0 8px 32px #10271b33;padding:14px}
      header{display:flex;justify-content:space-between;align-items:center;font-weight:700;color:#19573c}small{display:block;color:#5d6d63;font-size:12px;margin:3px 0 10px}
      button{font:inherit;border:0;border-radius:8px;padding:8px 12px;cursor:pointer}#fill{background:#1d6b4d;color:#fff;font-weight:700}#close{background:transparent;color:#64736a;font-size:18px;padding:0 5px}
      #status{font-size:12px;color:#48564d;margin-top:8px;white-space:normal}
    </style><section role="status"><header><span>Neural Ant · Application detected</span><button id="close" aria-label="Dismiss">×</button></header><small>Fill recognized fields from your saved profile. Review before submitting.</small><button id="fill">Fill application</button><div id="status"></div></section>`;
    document.documentElement.appendChild(host);
    banner = { host, shadow };
    shadow.querySelector('#close').addEventListener('click', () => { dismissed = true; host.remove(); banner = undefined; });
    shadow.querySelector('#fill').addEventListener('click', () => fillFromProfile(shadow.querySelector('#status')));
  }

  function scheduleDetection() {
    clearTimeout(timer);
    timer = setTimeout(ensureBanner, 500);
  }

  async function fetchProfile() {
    const result = await chrome.runtime.sendMessage({ type: 'NEURAL_ANT_GET_PROFILE' });
    if (!result?.ok) throw new Error(result?.message || 'Could not load your saved profile.');
    return result.profile;
  }

  async function fillFromProfile(statusNode) {
    const button = banner?.shadow.querySelector('#fill');
    if (button) { button.disabled = true; button.textContent = 'Filling…'; }
    if (statusNode) statusNode.textContent = 'Connecting to Neural Ant…';
    try {
      const profile = await fetchProfile();
      const result = fillFields(profile);
      const message = result.filled.length
        ? `Filled ${result.filled.length} field(s): ${result.filled.join(', ')}.`
        : 'No recognized empty fields found. Check My profile and the form labels.';
      const remaining = result.skipped.length ? ` Still for you: ${result.skipped.join('; ')}.` : '';
      const finalMessage = `${message}${remaining} Nothing was submitted.`;
      if (statusNode) statusNode.textContent = finalMessage;
      chrome.runtime.sendMessage({ type: 'NEURAL_ANT_FILL_RESULT', result: finalMessage });
    } catch (error) {
      if (statusNode) statusNode.textContent = error.message || 'Could not fill this page.';
    } finally {
      if (button) { button.disabled = false; button.textContent = 'Fill application'; }
    }
  }

  function fillFields(profile) {
    const skills = (Array.isArray(profile.skills) ? profile.skills : []).map(norm);
    const nameParts = String(profile.name || '').trim().split(/\s+/);
    const location = norm(profile.location);
    const filled = [];
    const skipped = [];
    const controls = [...document.querySelectorAll('input,textarea,select')].filter(visible);
    const textControls = controls.filter(element => element.matches('input:not([type]),input[type="text"],input[type="email"],input[type="tel"],textarea'));
    const setValue = (element, value) => {
      const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set;
      if (setter) setter.call(element, value); else element.value = value;
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
    };

    const textFields = [
      ['name', profile.name, text => /(^| )full name( |$)|(^| )name( |$)|your name/.test(text) && !/first name|last name/.test(text)],
      ['first name', nameParts[0], text => /first name/.test(text)],
      ['last name', nameParts.length > 1 ? nameParts.slice(1).join(' ') : '', text => /last name|surname/.test(text)],
      ['email', profile.email, text => /email|e mail/.test(text)],
      ['phone', profile.phone, text => /phone|mobile|telephone/.test(text)],
      ['location', profile.location, text => /current location|city|location|address/.test(text)],
      ['current company', profile.current_company, text => /current company|current employer/.test(text)],
      ['current role', profile.current_role, text => /current role|current title/.test(text)],
    ];
    for (const [name, value, matches] of textFields) {
      if (!String(value || '').trim()) continue;
      const field = textControls.find(element => !element.value.trim() && matches(fieldText(element)));
      if (field) { setValue(field, String(value).trim()); filled.push(name); }
    }

    const years = Number(profile.years_experience);
    const matchesYears = text => {
      const range = text.match(/(\d+(?:\.\d+)?)\s*(?:to|-|–|—)\s*(\d+(?:\.\d+)?)/);
      if (range) return years >= Number(range[1]) && years <= Number(range[2]);
      const plus = text.match(/(\d+(?:\.\d+)?)\s*(?:\+|or more|and up)/);
      return !!plus && years >= Number(plus[1]);
    };
    if (Number.isFinite(years) && years > 0) {
      let selectedYears = false;
      for (const element of controls.filter(control => control.matches('select'))) {
        if (!/how many years|years of (hands on )?engineering experience|years of experience/.test(fieldText(element))) continue;
        const option = [...element.options].find(item => !item.disabled && matchesYears(norm(item.textContent)));
        if (option && option.value) { setValue(element, option.value); filled.push('years of experience'); selectedYears = true; }
      }
      for (const element of controls.filter(control => control.matches('input[type="radio"]'))) {
        if (!/how many years|years of (hands on )?engineering experience|years of experience/.test(nearbyQuestion(element))) continue;
        if (matchesYears(fieldText(element)) && !element.checked) { element.click(); filled.push('years of experience'); selectedYears = true; break; }
      }
      if (!selectedYears && controls.some(element => /how many years|years of (hands on )?engineering experience|years of experience/.test(nearbyQuestion(element)))) skipped.push('experience range');
    }

    const skillOptions = [
      { label: /prompting|prompt engineering/, evidence: /prompt/ },
      { label: /retrieval augmented generation|\brag\b/, evidence: /retrieval augmented generation|\brag\b/ },
      { label: /fine tuning|fine tune/, evidence: /fine tuning|fine tune/ },
      { label: /evaluation framework|llm evaluation|evaluation/, evidence: /evaluation/ },
      { label: /agentic|tool use|tool calling/, evidence: /agent|tool use|tool calling/ },
    ];
    for (const element of controls.filter(control => control.matches('input[type="checkbox"]'))) {
      const text = fieldText(element);
      if (element.checked || /none of these/.test(text)) continue;
      const mapping = skillOptions.find(item => item.label.test(text));
      if (mapping && skills.some(skill => mapping.evidence.test(skill))) { element.click(); filled.push(text); }
    }

    const hasPython = skills.some(skill => skill === 'python' || skill.includes('python'));
    if (hasPython) {
      const choice = controls.find(element => element.matches('input[type="radio"]') && /yes primarily python/.test(fieldText(element)) && !element.checked);
      if (choice) { choice.click(); filled.push('Python response'); }
    }

    const sponsorshipText = norm(`${profile.work_authorization || ''} ${profile.sponsorship_preferences || ''}`);
    if (/h 1b|h1b|sponsorship|visa sponsor/.test(sponsorshipText)) {
      for (const element of controls.filter(control => control.matches('select'))) {
        if (!/now or in the future require employment sponsorship/.test(fieldText(element))) continue;
        const yes = [...element.options].find(option => norm(option.textContent) === 'yes');
        if (yes) { setValue(element, yes.value); filled.push('future sponsorship'); }
      }
      for (const element of controls.filter(control => control.matches('input[type="radio"]'))) {
        if (/now or in the future require employment sponsorship/.test(nearbyQuestion(element)) && fieldText(element) === 'yes' && !element.checked) {
          element.click(); filled.push('future sponsorship'); break;
        }
      }
    }

    const state = ['alabama','alaska','arizona','arkansas','california','colorado','connecticut','delaware','florida','georgia','hawaii','idaho','illinois','indiana','iowa','kansas','kentucky','louisiana','maine','maryland','massachusetts','michigan','minnesota','mississippi','missouri','montana','nebraska','nevada','new hampshire','new jersey','new mexico','new york','north carolina','north dakota','ohio','oklahoma','oregon','pennsylvania','rhode island','south carolina','south dakota','tennessee','texas','utah','vermont','virginia','washington','west virginia','wisconsin','wyoming'].find(item => location.includes(item));
    if (state) {
      for (const element of controls.filter(control => control.matches('select'))) {
        if (!/state do you currently reside|current state|state of residence/.test(fieldText(element))) continue;
        const option = [...element.options].find(item => norm(item.textContent) === state || norm(item.textContent).startsWith(`${state} `));
        if (option && option.value) { setValue(element, option.value); filled.push('state'); }
      }
    }

    if (controls.some(element => /authorized to work/.test(nearbyQuestion(element)))) skipped.push('current work authorization');
    if (controls.some(element => /production|live users/.test(nearbyQuestion(element)))) skipped.push('production experience claim');
    if (controls.some(element => /healthcare|regulated|high stakes/.test(nearbyQuestion(element)))) skipped.push('regulated-domain experience claim');
    if (controls.some(element => /responsibility listed|newest to you/.test(nearbyQuestion(element)))) skipped.push('role-specific written response');
    if (controls.some(element => /currently work for curai|employee refer|how did you hear/.test(nearbyQuestion(element)))) skipped.push('employer-specific questions');
    if (controls.some(element => /gender|race|veteran/.test(nearbyQuestion(element)))) skipped.push('optional demographic questions');
    if (controls.some(element => element.matches('input[type="file"]'))) skipped.push('resume file (attach it yourself)');
    return { filled, skipped: [...new Set(skipped)] };
  }

  function findApplicationLinks() {
    const links = [...document.querySelectorAll('a[href]')].filter(visible).map(anchor => {
      const label = String(anchor.innerText || anchor.getAttribute('aria-label') || anchor.title || '').replace(/\s+/g, ' ').trim();
      let url;
      try { url = new URL(anchor.href, location.href); } catch { return null; }
      if (url.protocol !== 'https:' || /submit|send application|withdraw|cancel/.test(norm(label))) return null;
      const labelText = norm(label);
      const urlText = norm(url.pathname);
      const matches = (/\bapply\b/.test(labelText) && !/apply filters|apply search/.test(labelText))
        || /start application|job application|application form|continue application/.test(labelText)
        || /\bapply\b/.test(urlText);
      if (!matches) return null;
      return { label: label || 'Apply', url: url.href };
    }).filter(Boolean);
    const seen = new Set();
    return links.filter(link => {
      if (seen.has(link.url)) return false;
      seen.add(link.url);
      return true;
    }).slice(0, 10);
  }

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === 'NEURAL_ANT_FIND_APPLY_LINKS') {
      sendResponse({ ok: true, links: findApplicationLinks() });
      return false;
    }
    if (message?.type !== 'NEURAL_ANT_FILL') return false;
    if (!isApplicationPage()) { sendResponse({ ok: false, message: 'No job application form detected on this page.' }); return false; }
    const status = banner?.shadow.querySelector('#status');
    fillFromProfile(status).then(() => sendResponse({ ok: true, message: status?.textContent || 'Form fill finished. Review the page.' }));
    return true;
  });

  scheduleDetection();
  new MutationObserver(scheduleDetection).observe(document.documentElement, { childList: true, subtree: true });
})();
