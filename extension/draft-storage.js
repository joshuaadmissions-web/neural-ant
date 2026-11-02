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
    if (restoring) return { ok: false, message: 'A draft action is already running.' };
    restoring = true;
    try {
      const key = keyFor();
      const saved = (await chrome.storage.local.get(key))[key];
      if (!saved) return { ok: true, restoredCount: 0, message: 'No saved draft was found for this application page.' };
      if (Date.now() - saved.updatedAt > 30 * 24 * 60 * 60 * 1000) {
        await chrome.storage.local.remove(key);
        return { ok: true, restoredCount: 0, message: 'The saved draft was more than 30 days old and was removed.' };
      }
      const fields = controls();
      let restoredCount = 0;
      for (const [key, value] of Object.entries(saved.fields || {})) {
        const el = fields.find(candidate => identity(candidate) === key);
        if (!el) continue;
        const current = currentValue(el);
        const empty = (el.type === 'checkbox' || el.type === 'radio') ? current === false : !String(current || '').trim();
        if (empty) { setValue(el, value); restoredCount += 1; }
      }
      return { ok: true, restoredCount, updatedAt: saved.updatedAt,
        message: restoredCount ? `Restored ${restoredCount} empty field(s) from the local draft.` : 'The draft exists, but no matching empty fields were found.' };
    } finally { restoring = false; }
  }
  async function save() {
    if (restoring) return { ok: false, message: 'A draft action is already running.' };
    const fields = {};
    for (const el of controls()) {
      const id = identity(el);
      if (!id) continue;
      const value = currentValue(el);
      if ((el.type === 'checkbox' || el.type === 'radio') ? value : String(value || '').trim()) fields[id] = value;
    }
    const updatedAt = Date.now();
    await chrome.storage.local.set({ [keyFor()]: { fields, updatedAt } });
    return { ok: true, savedCount: Object.keys(fields).length, updatedAt,
      message: `Saved ${Object.keys(fields).length} eligible field(s) locally for this application page.` };
  }
  document.addEventListener('NEURAL_ANT_DRAFT_ACTION', event => {
    let request;
    try { request = typeof event.detail === 'string' ? JSON.parse(event.detail) : event.detail; } catch { return; }
    if (!request?.requestId || !['save', 'restore'].includes(request.action)) return;
    const operation = request.action === 'save' ? save() : restore();
    Promise.resolve(operation).then(result => {
      document.dispatchEvent(new CustomEvent('NEURAL_ANT_DRAFT_RESULT', {
        detail: JSON.stringify({ requestId: request.requestId, ...result }),
      }));
    }).catch(error => {
      document.dispatchEvent(new CustomEvent('NEURAL_ANT_DRAFT_RESULT', {
        detail: JSON.stringify({ requestId: request.requestId, ok: false, message: error.message || 'Could not update the local draft.' }),
      }));
    });
  });
  document.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(save, 500); }, true);
  document.addEventListener('change', () => { clearTimeout(timer); timer = setTimeout(save, 250); }, true);
  restore();
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(restore, 700); })
    .observe(document.documentElement, { childList: true, subtree: true });
})();
