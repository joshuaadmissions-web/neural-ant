# RCC fit for Neural Ant's browser RPA

The [RCC repository](https://github.com/joshyorko/rcc) is a Python automation package and environment manager. It can package and run repeatable Python automations in isolated environments, commonly alongside a `robot.yaml` task definition.

## Can Neural Ant use it?

**Yes, as an optional runner for a separate Python automation.** RCC could package a future worker that runs a Python browser tool such as Playwright. It may help make that worker's dependencies repeatable.

**It is not a drop-in replacement for the current Chrome extension.** The extension runs in the user's logged-in Chrome session and fills supported empty application fields after a click. A Python automation launched through RCC would typically open or control its own browser process; it would not automatically share the Chrome profile, cookies, or active session. Adding RCC alone would therefore not make the existing fill flow more reliable or run hands-free while the computer is off.

## Recommendation

Keep the existing Chrome extension for user-supervised form assistance. Consider RCC only if a concrete, isolated Python automation is needed later and its separate browser/session model is acceptable. Any such worker should stop before final submission, avoid guessing sensitive/legal answers, and keep credentials and resume data out of source control.

No RCC dependency or runtime has been added to Neural Ant.