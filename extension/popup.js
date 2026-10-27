const button = document.querySelector('#fill');
const status = document.querySelector('#status');

button.addEventListener('click', async () => {
  button.disabled = true;
  status.textContent = 'Checking this application page…';
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error('No active page found.');
    const result = await chrome.tabs.sendMessage(tab.id, { type: 'NEURAL_ANT_FILL' });
    if (!result?.ok) throw new Error(result?.message || 'Open a job application page and try again.');
    status.textContent = result.message;
  } catch (error) {
    status.textContent = error.message || 'Could not connect to the page. Refresh it and try again.';
  } finally {
    button.disabled = false;
  }
});
