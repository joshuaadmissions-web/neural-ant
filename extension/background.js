chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== 'NEURAL_ANT_GET_PROFILE') return false;
  fetch('http://127.0.0.1:8080/api/form-profile')
    .then(async response => {
      if (!response.ok) throw new Error(response.status === 404
        ? 'Update and restart Neural Ant to the latest version.'
        : `Neural Ant returned ${response.status}. Make sure it is running.`);
      return response.json();
    })
    .then(profile => sendResponse({ ok: true, profile }))
    .catch(error => sendResponse({ ok: false, message: error.message || 'Could not connect to Neural Ant.' }));
  return true;
});
