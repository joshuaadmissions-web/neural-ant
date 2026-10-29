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
