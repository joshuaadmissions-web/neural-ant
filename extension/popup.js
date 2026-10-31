const findButton = document.querySelector('#find');
const openButton = document.querySelector('#open');
const fillButton = document.querySelector('#fill');
const linksSelect = document.querySelector('#links');
const status = document.querySelector('#status');

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error('No active page found.');
  return tab;
}

findButton.addEventListener('click', async () => {
  findButton.disabled = true;
  status.textContent = 'Looking for employer application links…';
  linksSelect.replaceChildren(new Option('Searching…', ''));
  linksSelect.disabled = true;
  openButton.disabled = true;
  try {
    const tab = await activeTab();
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'NEURAL_ANT_FIND_APPLY_LINKS' });
    if (!result?.ok) throw new Error(result?.message || 'Could not inspect this page.');
    linksSelect.replaceChildren();
    if (!result.links.length) {
      linksSelect.add(new Option('No application links found', ''));
      status.textContent = 'Open the employer job posting first. No links were opened.';
      return;
    }
    for (const link of result.links) linksSelect.add(new Option(`${link.label} — ${new URL(link.url).hostname}`, link.url));
    linksSelect.disabled = false;
    openButton.disabled = false;
    status.textContent = `Found ${result.links.length} link(s). Choose the correct employer application page, then open it.`;
  } catch (error) {
    linksSelect.replaceChildren(new Option('Could not inspect this page', ''));
    status.textContent = error.message || 'Refresh the employer page and try again.';
  } finally {
    findButton.disabled = false;
  }
});

openButton.addEventListener('click', async () => {
  const url = linksSelect.value;
  if (!url || !url.startsWith('https://')) {
    status.textContent = 'Choose a valid HTTPS application link first.';
    return;
  }
  openButton.disabled = true;
  try {
    await chrome.tabs.create({ url, active: true });
    status.textContent = 'Application page opened. Review it, then use Fill this application.';
  } catch (error) {
    status.textContent = error.message || 'Could not open that link.';
  } finally {
    openButton.disabled = false;
  }
});

fillButton.addEventListener('click', async () => {
  fillButton.disabled = true;
  status.textContent = 'Checking this application page…';
  try {
    const tab = await activeTab();
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'NEURAL_ANT_FILL' });
    if (!result?.ok) throw new Error(result?.message || 'Open a job application page and try again.');
    status.textContent = result.message;
  } catch (error) {
    status.textContent = error.message || 'Could not connect to the page. Refresh it and try again.';
  } finally {
    fillButton.disabled = false;
  }
});

const clearDraftsButton = document.getElementById('clearDrafts');
clearDraftsButton.addEventListener('click', async () => {
  clearDraftsButton.disabled = true;
  status.textContent = 'Clearing saved drafts on this device…';
  try {
    const all = await chrome.storage.local.get(null);
    const keys = Object.keys(all).filter(key => key.startsWith('naDraft:'));
    if (keys.length) await chrome.storage.local.remove(keys);
    status.textContent = keys.length ? 'Saved application drafts cleared from this device.' : 'No saved application drafts were found.';
  } catch (error) {
    status.textContent = error.message || 'Could not clear local drafts.';
  } finally {
    clearDraftsButton.disabled = false;
  }
});
