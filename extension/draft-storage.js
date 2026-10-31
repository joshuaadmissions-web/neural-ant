(() => {
  const keyFor = () => 'naDraft:' + location.hostname + location.pathname.replace(/\/+$/, '');
  const norm = value => String(value || '').replace(/\s+/g, ' ').trim().slice(0, 300);
  const controls = () => [...document.querySelectorAll('input,textarea,select,[contenteditable="true"]')]
    .filter(el => el.getClientRects().length && !el.disabled &&
      !['password','file','hidden','submit','button','reset'].includes((el.type || '').toLowerCase()));
  const labelFor = el => {
    const labels = [...(el.labels || [])].map(x => x.innerText || x.textContent || '');
    const by = (el.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map(id => document.getElementById(id)?.innerText || '').join(' ');
    return norm([...labels, by, el.getAttribute('aria-label'), el.getAttribute('placeholder'),
      el.name, el.id, el.closest('label')?.innerText].filter(Boolean).join(' '));
  };
  const identity = el => {
    const name = labelFor(el);
    if (!name || /work authorization|authorized to work|visa|sponsorship|immigration|social security|ssn|date of birth|gender|race|ethnicity|disability|veteran|criminal history|background check|signature|attest|legally eligible|require.*sponsor/i.test(name)) return '';
    const same = controls().filter(candidate => labelFor(candidate) === name);
    return name + '#' + same.indexOf(el);
  };
  const currentValue = el => {
    if (el.type === 'checkbox' || el.type === 'radio') return el.checked;
    if (el.isContentEditable) return el.innerText;
    return el.value;
  };
  const setValue = (el, value) => {
    if ((el.type === 'checkbox' || el.type === 'radio') && typeof value === 'boolean') {
      el.checked = value;
    } else if (el.isContentEditable) el.innerText = String(value);
    else el.value = String(value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  let restoring = false;
  let timer;
  async function restore() {
    if (restoring) return;
    restoring = true;
    try {
      const saved = (await chrome.storage.local.get(keyFor()))[keyFor()];
      if (!saved) return;
      if (Date.now() - saved.updatedAt > 30 * 24 * 60 * 60 * 1000) {
        await chrome.storage.local.remove(keyFor());
        return;
      }
      const fields = controls();
      for (const [key, value] of Object.entries(saved.fields || {})) {
        const el = fields.find(candidate => identity(candidate) === key);
        if (!el) continue;
        const current = currentValue(el);
        const empty = (el.type === 'checkbox' || el.type === 'radio') ? current === false : !String(current || '').trim();
        if (empty) setValue(el, value);
      }
    } finally { restoring = false; }
  }
  async function save() {
    if (restoring) return;
    const fields = {};
    for (const el of controls()) {
      const id = identity(el);
      if (!id) continue;
      const value = currentValue(el);
      if ((el.type === 'checkbox' || el.type === 'radio') ? value : String(value || '').trim()) fields[id] = value;
    }
    await chrome.storage.local.set({ [keyFor()]: { fields, updatedAt: Date.now() } });
  }
  document.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(save, 500); }, true);
  document.addEventListener('change', () => { clearTimeout(timer); timer = setTimeout(save, 250); }, true);
  restore();
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(restore, 700); })
    .observe(document.documentElement, { childList: true, subtree: true });
})();
