# Multi-step flow (wizard)

Applies to: a task split into steps: setup, import with mapping, a request with review. Read with: `form.md` for each step.

| Code | Check | Level |
|---|---|---|
| WZ-01 | Shows how many steps, which one you are on, and the name of each | Must |
| WZ-02 | Back keeps what was typed; the browser Back does the same | Must |
| WZ-03 | Each step checks its own fields before Next; errors stay on that step | Must |
| WZ-04 | A last step shows a summary of the choices, each with a way to edit it | Should |
| WZ-05 | Leaving halfway keeps a draft, or says it will be lost and asks | Must |
| WZ-06 | Steps that do not apply to the user's choices are skipped, and the step count follows | Should |
| WZ-07 | The final button names the result ("Create workspace"), not "Next" or "Finish" | Should |
| WZ-08 | Optional steps say so and can be skipped | Should |
| WZ-09 | The end screen says what happened and what to do next | Must |
| WZ-10 | Finished steps can be revisited from the stepper when the order allows it | Nice |
