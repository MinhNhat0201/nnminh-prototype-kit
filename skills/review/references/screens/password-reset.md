# Password reset

Applies to: asking for a reset link or code, and setting a new password from it. Not for: changing a password while signed in (`settings.md`).

| Code | Check | Level |
|---|---|---|
| PW-01 | The request page keeps the email typed on the sign-in page | Should |
| PW-02 | After the request, the same message whether the account exists or not, naming the address and how long the link lasts | Must |
| PW-03 | "Send again" with a wait time, and a way to change the address | Should |
| PW-04 | The new-password page shows the rules before typing and checks them while typing | Must |
| PW-05 | `autocomplete="new-password"`; show or hide password | Should |
| PW-06 | An expired or used link says so and offers a new one in one step | Must |
| PW-07 | After saving, people are signed in or sent to sign-in with a success message | Must |
| PW-08 | Says whether other devices were signed out | Nice |
| PW-09 | A way back to sign-in on every step | Should |
