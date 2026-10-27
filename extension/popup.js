const button = document.querySelector('#fill');
const status = document.querySelector('#status');

button.addEventListener('click', async () => {
  button.disabled = true;
  status.textContent = 'Connecting to Neural Ant…';
  try {
    const response = await fetch('http://127.0.0.1:8080/api/form-profile');
    if (!response.ok) throw new Error(response.status === 404
      ? 'Update Neural Ant to the latest version, then restart it.'
      : `Neural Ant returned ${response.status}. Is the latest version running?`);
    const profile = await response.json();
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error('No active application tab found.');
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: fillSupportedFields,
      args: [profile],
    });
    status.textContent = result.filled.length
      ? `Filled ${result.filled.length}: ${result.filled.join(', ')}.`
      : 'No supported empty fields found.';
    if (result.skipped.length) status.textContent += `\nPlease complete/review: ${result.skipped.join(', ')}.`;
    status.textContent += '\nReview every answer. Nothing is submitted.';
  } catch (error) {
    status.textContent = error.message || 'Could not fill this page.';
  } finally {
    button.disabled = false;
  }
});

function fillSupportedFields(profile) {
  const normalized = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  const nameParts = String(profile.name || '').trim().split(/\s+/);
  const skills = (Array.isArray(profile.skills) ? profile.skills : []).map(normalized);
  const evidence = normalized(`${profile.summary || ''} ${profile.current_role || ''}`);
  const location = normalized(profile.location);
  const filled = [];
  const skipped = [];
  const controls = [...document.querySelectorAll('input, textarea, select')]
    .filter(element => !element.disabled && !element.readOnly && element.getClientRects().length);

  const labelText = element => {
    const explicit = [...(element.labels || [])].map(label => label.innerText || label.textContent || '');
    const labelledBy = (element.getAttribute('aria-labelledby') || '').split(/\s+/)
      .map(id => document.getElementById(id)?.innerText || '').join(' ');
    return normalized([
      ...explicit,
      labelledBy,
      element.getAttribute('aria-label'),
      element.getAttribute('placeholder'),
      element.getAttribute('name'),
      element.id,
      element.closest('label')?.innerText,
    ].filter(Boolean).join(' '));
  };
  const setValue = (element, value) => {
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set;
    if (setter) setter.call(element, value); else element.value = value;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const optionsFor = element => [...(element.options || [])].map(option => ({ option, text: normalized(option.textContent) }));
  const experienceQuestion = element => {
    let parent = element.closest('fieldset,[role="group"]');
    if (!parent) {
      parent = element.parentElement;
      for (let depth = 0; parent && depth < 4; depth++, parent = parent.parentElement) {
        const text = normalized(parent.innerText || parent.textContent);
        if (/how many years|years of (hands on )?engineering experience|years of experience/.test(text)) return text;
      }
      return '';
    }
    return normalized(parent.innerText || parent.textContent);
  };
  const yearsMatch = text => {
    const range = text.match(/(\d+(?:\.\d+)?)\s*(?:to|-|–|—)\s*(\d+(?:\.\d+)?)/);
    if (range) return years >= Number(range[1]) && years <= Number(range[2]);
    const plus = text.match(/(\d+(?:\.\d+)?)\s*(?:\+|or more|and up)/);
    return !!plus && years >= Number(plus[1]);
  };
  const selectMatchingOption = (element, predicate, field) => {
    const match = optionsFor(element).find(({ option, text }) => !option.disabled && predicate(text));
    if (match && match.option.value) {
      setValue(element, match.option.value);
      filled.push(field);
      return true;
    }
    return false;
  };
  const stateNames = {
    alabama: 'alabama', alaska: 'alaska', arizona: 'arizona', arkansas: 'arkansas', california: 'california',
    colorado: 'colorado', connecticut: 'connecticut', delaware: 'delaware', florida: 'florida', georgia: 'georgia',
    hawaii: 'hawaii', idaho: 'idaho', illinois: 'illinois', indiana: 'indiana', iowa: 'iowa', kansas: 'kansas',
    kentucky: 'kentucky', louisiana: 'louisiana', maine: 'maine', maryland: 'maryland', massachusetts: 'massachusetts',
    michigan: 'michigan', minnesota: 'minnesota', mississippi: 'mississippi', missouri: 'missouri', montana: 'montana',
    nebraska: 'nebraska', nevada: 'nevada', 'new hampshire': 'new hampshire', 'new jersey': 'new jersey',
    'new mexico': 'new mexico', 'new york': 'new york', 'north carolina': 'north carolina',
    'north dakota': 'north dakota', ohio: 'ohio', oklahoma: 'oklahoma', oregon: 'oregon', pennsylvania: 'pennsylvania',
    'rhode island': 'rhode island', 'south carolina': 'south carolina', 'south dakota': 'south dakota',
    tennessee: 'tennessee', texas: 'texas', utah: 'utah', vermont: 'vermont', virginia: 'virginia',
    washington: 'washington', 'west virginia': 'west virginia', wisconsin: 'wisconsin', wyoming: 'wyoming',
  };
  const state = Object.keys(stateNames).find(candidate => location.includes(candidate));

  // Fill ordinary text inputs from the saved, user-verified profile.
  const textControls = controls.filter(element => element.matches('input:not([type]), input[type="text"], input[type="email"], input[type="tel"], textarea'));
  const textFields = [
    { key: 'name', value: profile.name, test: text => /(^| )full name( |$)|(^| )name( |$)|your name/.test(text) && !/first name|last name/.test(text) },
    { key: 'first name', value: nameParts[0], test: text => /first name/.test(text) },
    { key: 'last name', value: nameParts.length > 1 ? nameParts.slice(1).join(' ') : '', test: text => /last name|surname/.test(text) },
    { key: 'email', value: profile.email, test: text => /email|e mail/.test(text) },
    { key: 'phone', value: profile.phone, test: text => /phone|mobile|telephone/.test(text) },
    { key: 'location', value: profile.location, test: text => /current location|city|location|address/.test(text) },
    { key: 'current company', value: profile.current_company, test: text => /current company|current employer/.test(text) },
    { key: 'current role', value: profile.current_role, test: text => /current role|current title/.test(text) },
  ];
  for (const field of textFields) {
    if (!String(field.value || '').trim()) continue;
    const element = textControls.find(candidate => !candidate.value.trim() && field.test(labelText(candidate)));
    if (!element) continue;
    setValue(element, String(field.value).trim());
    filled.push(field.key);
  }

  // Pick the experience range only when the profile has a numeric experience value.
  const years = Number(profile.years_experience);
  if (Number.isFinite(years) && years > 0) {
    for (const element of controls.filter(control => control.matches('select'))) {
      if (!/years? of (hands on )?engineering experience|years? of experience/.test(labelText(element))) continue;
      const selected = selectMatchingOption(element, yearsMatch, 'years of experience');
      if (!selected) skipped.push('years of experience (choose the matching range)');
    }
    for (const element of controls.filter(control => control.matches('input[type="radio"]'))) {
      const question = experienceQuestion(element);
      if (!/how many years|years of (hands on )?engineering experience|years of experience/.test(question)) continue;
      if (!yearsMatch(labelText(element)) || element.checked) continue;
      element.click();
      filled.push('years of experience');
      break;
    }
  }

  // Select only skills explicitly listed on the saved profile.
  const skillOptionPatterns = [
    { match: /prompting|prompt engineering/, evidence: /prompt/ },
    { match: /retrieval augmented generation|\brag\b/, evidence: /retrieval augmented generation|\brag\b/ },
    { match: /fine tuning|fine tuning/, evidence: /fine tuning|fine tune/ },
    { match: /evaluation framework|llm evaluation|evaluation/, evidence: /evaluation/ },
    { match: /agentic|tool use|tool calling/, evidence: /agent|tool use|tool calling/ },
  ];
  for (const element of controls.filter(control => control.matches('input[type="checkbox"]'))) {
    const text = labelText(element);
    if (element.checked || /none of these/.test(text)) continue;
    const option = skillOptionPatterns.find(item => item.match.test(text));
    if (!option || !skills.some(skill => option.evidence.test(skill))) continue;
    element.click();
    filled.push(text || 'matching skill');
  }

  // Answer the Python choice only when Python is explicitly in the verified skills.
  const hasPython = skills.some(skill => skill === 'python' || skill.includes('python'));
  if (hasPython) {
    const pythonChoice = controls.find(element => element.matches('input[type="radio"]') && /yes primarily python/.test(labelText(element)) && !element.checked);
    if (pythonChoice) { pythonChoice.click(); filled.push('Python production-code question'); }
  }

  // Sponsorship need is known from the saved preference; current work authorization is not inferred.
  const needsSponsorship = /h 1b|h1b|sponsorship|visa sponsor/.test(normalized(`${profile.work_authorization || ''} ${profile.sponsorship_preferences || ''}`));
  if (needsSponsorship) {
    for (const element of controls.filter(control => control.matches('select'))) {
      if (!/now or in the future require employment sponsorship/.test(labelText(element))) continue;
      if (!selectMatchingOption(element, text => text === 'yes', 'future sponsorship')) skipped.push('future sponsorship (choose Yes)');
    }
  }

  // Choose a state only when it is explicitly present in the saved location.
  if (state) {
    for (const element of controls.filter(control => control.matches('select'))) {
      if (!/state do you currently reside|current state|state of residence/.test(labelText(element))) continue;
      if (!selectMatchingOption(element, text => text === state || text.startsWith(`${state} `), 'state')) skipped.push('state');
    }
  }

  if (controls.some(element => /production|live users/.test(labelText(element)))) skipped.push('production experience answer (verify personally)');
  if (controls.some(element => /healthcare|regulated|high stakes/.test(labelText(element)))) skipped.push('regulated-domain experience (verify personally)');
  if (controls.some(element => /responsibility listed|newest to you/.test(labelText(element)))) skipped.push('role-specific written response');
  if (controls.some(element => /authorized to work/.test(labelText(element)))) skipped.push('current work authorization');
  if (controls.some(element => /previously|currently work for curai|employee refer|how did you hear/.test(labelText(element)))) skipped.push('employer-specific answers');
  if (controls.some(element => /gender|race|veteran/.test(labelText(element)))) skipped.push('optional demographic questions');
  if (controls.some(element => element.matches('input[type="file"]'))) skipped.push('resume attachment (choose your resume file)');

  return { filled, skipped: [...new Set(skipped)] };
}
