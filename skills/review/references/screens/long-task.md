# Long or AI task

Applies to: anything that runs for seconds or minutes: generate a document, import, export, analyse, an AI task. Read with: `states-and-edge-data.md` S-04, S-05.

| Code | Check | Level |
|---|---|---|
| LT-01 | Before starting, says what will happen and roughly how long it takes | Should |
| LT-02 | While running: progress or the current step, never only a spinner for more than a few seconds | Must |
| LT-03 | Stop or Cancel, saying what happens to partial work | Must |
| LT-04 | People can leave the screen; the task continues and tells them when it is done | Should |
| LT-05 | A finished task says what was made and where; one action to open it | Must |
| LT-06 | A failed task says what failed, what was kept, and offers Retry without typing everything again | Must |
| LT-07 | Partial results are shown as they arrive when the task allows it | Nice |
| LT-08 | AI output is marked as generated, can be edited, and the source or input is visible | Must |
| LT-09 | AI output can be regenerated or rated; the previous version is not lost | Should |
| LT-10 | Words follow the user's language, not the system's (no "prompt", "token", "job ID" in front of business users) | Should |
| LT-11 | Two tasks started at once do not mix their results | Should |
