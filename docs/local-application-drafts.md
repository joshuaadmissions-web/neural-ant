# Local application draft save and resume

The Chrome extension saves visible application form answers in `chrome.storage.local` on the device where the extension is installed. The draft key uses the page hostname and pathname (query parameters are excluded). When that page is opened again, saved values are restored only into currently empty fields. Nonempty values are left as-is.

The extension excludes password, hidden, file-upload, submit, button, and reset controls. Resume attachments are not saved; attach the file again when you return. Drafts older than 30 days are ignored. Browser extension data can be cleared by removing the extension or clearing its stored data. Drafts are not synced to Neural Ant's server or another device.

## Use

1. Reload Neural Ant from `chrome://extensions` after updating the extension folder.
2. Open an employer application page in Chrome. Complete any account login or verification yourself.
3. Fill the fields you can answer. The extension saves visible field answers locally as you type or change selections.
4. Close the page. Later, reopen the same employer application URL in the same Chrome profile; saved answers are restored into empty matching fields.
5. Review all fields, reattach your resume, complete required attestations/signature, and submit yourself.

This is a best-effort prototype. Employer sites can change form structure, route, or labels. A different application URL/path may produce a separate draft; dynamic multi-page forms may not restore every field. Never rely on this feature as the only copy of an application.
