# Sign-in

Applies to: signing in with an account, SSO, a code by email or SMS. Not for: creating an account (`sign-up.md`), resetting a password (`password-reset.md`).
Read with: `a11y-web.md` W-40–W-47 (fields and errors).

| Code | Check | Level |
|---|---|---|
| SI-01 | The page says which product or workspace you are signing in to | Must |
| SI-02 | Fields have visible labels; the user name field says what it takes (email, user name or both) | Must |
| SI-03 | `autocomplete="username"` and `current-password`, so password managers fill them | Must |
| SI-04 | Show or hide password, with a control that has a name | Should |
| SI-05 | Enter submits the form; the button names the action ("Sign in") | Must |
| SI-06 | A failed sign-in keeps the user name, clears nothing else, and does not say which of the two was wrong when that would expose accounts | Must |
| SI-07 | "Forgot password" sits next to the password field and keeps the typed email | Must |
| SI-08 | A locked or disabled account says why and what to do (wait time, contact) | Should |
| SI-09 | SSO options name the provider in text, not by logo alone; the order matches what most users of the product use | Should |
| SI-10 | A one-time code field accepts paste, takes digits only, and offers "Send again" with a wait time | Should |
| SI-11 | The button shows progress while waiting and cannot be pressed twice | Should |
| SI-12 | A link to create an account or request access when the product allows it | Should |
| SI-13 | After sign-in, people land where they were going (the link they opened), not always on the home page | Should |
| SI-14 | Caps Lock on is shown near the password field | Nice |
| SI-15 | "Keep me signed in" says for how long, when it exists | Nice |
