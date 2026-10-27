const button = document.querySelector('#fill');
const status = document.querySelector('#status');

button.addEventListener('click', async () => {
  button.disabled = true;
  status.textContent = 'Connecting to Neural Ant…';
  try {
    const response = await fetch('http://127.0.0.1:8080/api/form-profile');
    if (!response.ok) throw new Error(response.status === 404 ? 'Update Neural Ant to the latest local version, then restart it.' : `Neural Ant returned ${response.status}. Is it running?`);
    const profile = await response.json();
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error('No active application tab found.');
    const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: fillSupportedFields, args: [profile] });
    status.textContent = result.filled.length
      ? `Filled ${result.filled.length} field(s): ${result.filled.join(', ')}.\nReview all values before using them.`
      : 'No supported empty fields found. This form may need manual review.';
    if (result.skipped.length) status.textContent += `\nLeft for you: ${result.skipped.join(', ')}.`;
  } catch (error) {
    status.textContent = error.message || 'Could not fill this page.';
  } finally {
    button.disabled = false;
  }
});

function fillSupportedFields(profile) {
  const fields = {
    name: profile.name,
    email: profile.email,
    phone: profile.phone,
    location: profile.location,
    company: profile.current_company,
    title: profile.current_role,
  };
  const normalize = value => (value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const describe = element => {
    const labels = [...(element.labels || [])].map(label => label.innerText || label.textContent || '');
    const aria = element.getAttribute('aria-label') || '';
    const placeholder = element.getAttribute('placeholder') || '';
    const name = element.getAttribute('name') || '';
    const id = element.id || '';
    const wrapping = element.closest('label')?.innerText || '';
    const labelledBy = (element.getAttribute('aria-labelledby') || '').split(/\s+/).map(key => document.getElementById(key)?.innerText || '').join(' ');
    return normalize([labels.join(' '), aria, placeholder, name, id, wrapping, labelledBy].join(' '));
  };
  const candidates = [...document.querySelectorAll('input:not([type]), input[type="text"], input[type="email"], input[type="tel"], textarea')]
    .filter(element => !element.disabled && !element.readOnly && element.getClientRects().length);
  const filled = [];
  for (const [key, raw] of Object.entries(fields)) {
    const value = typeof raw === 'string' ? raw.trim() : '';
    if (!value) continue;
    const patterns = {
      name: /(^| )(full )?name( |$)|first name|your name/,
      email: /email|e mail/,
      phone: /phone|mobile|telephone/,
      location: /current location|city|location|address/,
      company: /current company|current employer|employer/,
      title: /current role|current title|job title|position/,
    };
    const element = candidates.find(candidate => !candidate.value && patterns[key].test(describe(candidate)));
    if (!element) continue;
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set;
    if (setter) setter.call(element, value); else element.value = value;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    filled.push(key);
  }
  const skipped = [];
  if (profile.work_authorization || profile.sponsorship_preferences) skipped.push('work authorization/sponsorship');
  skipped.push('legal attestations and demographic questions');
  return { filled, skipped };
}
