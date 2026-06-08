# Poke recipe — "Canvas Study Buddy"

A Poke **recipe** bundles three things so a user is productive in one click:
onboarding context + first-message behavior, the **required integration(s)**, and a
shareable install link (`https://poke.com/r/<code>`). This file is everything you
need to create that recipe in Poke's Kitchen. The machine-readable version is
[`recipe.json`](recipe.json).

> Recipes are created in Poke's web UI (you have to be signed in to your own Poke
> account), so this is a copy-paste guide rather than something a script can do
> for you. It takes ~2 minutes.

## Prerequisite

Deploy the MCP server first (see the repo [README](../README.md) → *Setup*). You'll
have a URL like `https://your-service.onrender.com/mcp`. Keep it handy.

## Create the recipe

1. Go to **[poke.com/kitchen](https://poke.com/kitchen)** → **Create recipe**.
2. **Name:** `Canvas Study Buddy`
   **Description:** *Ask Poke about your Canvas courses, assignments, grades, deadlines, announcements, and to-dos — answered live from your real Canvas account.*
3. **Required integration** — add the Canvas MCP server:
   - Name: `Canvas`
   - Server URL: `https://your-service.onrender.com/mcp`  *(note the `/mcp`, no trailing slash)*
   - Auth: **None** (credentials live on the server as env vars, so users don't paste a key)
   - If you deployed **one shared server for many schools**, instead choose **API key** auth and tell each user to paste `https://canvas.theirschool.edu::THEIR_CANVAS_TOKEN` as the key.
4. **Onboarding context** (paste verbatim):

   ```
   You help a student stay on top of their Canvas LMS coursework. You have a
   Canvas integration with read-only tools. Always start with list_courses to
   learn the student's courses and their ids before calling course-scoped tools
   (assignments, quizzes, modules, pages, files, discussions). Use list_todos and
   list_upcoming_events for "what's due", and get_recent_activity for "what
   changed / what's new". Canvas data is live, so never say it might be stale.
   When listing due dates, sort soonest-first and show the course name. Be concise
   and proactive about deadlines.
   ```

5. **Prefilled first message** (paste verbatim):

   ```
   Hey! I'm linked to your Canvas now. Want me to show what's due this week, or
   catch you up on anything new across your courses?
   ```

6. **Publish** → copy your share link `https://poke.com/r/<code>`. Anyone who opens
   it gets Poke pre-loaded with the Canvas integration and the context above.

## Proactive updates (optional but recommended)

To make Poke *tell you* when Canvas changes — instead of only answering when asked —
add these as scheduled automations in Poke (Settings → Automations), or just send
the prompt to Poke once and ask it to run on a schedule:

- **Morning digest — every weekday 8:00am**

  ```
  Call get_recent_activity and list_upcoming_events. If there's anything new since
  yesterday (new announcements, grade changes, newly due/assigned work), text me a
  short bulleted digest grouped by course. If nothing changed, stay quiet.
  ```

- **Grade-change watch — every day 6:00pm**

  ```
  Call get_recent_activity. If any item is a grade change or new submission
  comment, text me which course and assignment changed.
  ```

These rely on the live `get_recent_activity` tool, so they reflect real changes in
Canvas the moment they happen.

## Connect without the UI (Poke CLI)

If you just want to wire your own server to your own Poke account (no recipe needed),
one command does it:

```bash
npx poke@latest mcp add https://<your-host>/mcp -n "Canvas"
```

With API-key auth (shared/multi-school server), pass the key too:

```bash
npx poke@latest mcp add https://<your-host>/mcp -n "Canvas" -k "https://canvas.yourschool.edu::YOUR_TOKEN"
```

### Dynamic Client Registration (DCR)
This server uses simple env-var / Bearer auth, which Poke supports directly — there's
nothing to pre-register. If you later add OAuth, MCP servers that implement **Dynamic
Client Registration** are picked up by Poke automatically (no manual client-id/secret);
otherwise you'd register OAuth credentials once via a Kitchen template. For Canvas,
the token path here is simpler and recommended.

## Test the recipe

Open your share link (or your own Poke), then message:

- "What courses am I taking?" → exercises `list_courses`
- "What's due this week?" → `list_upcoming_events` / `list_todos`
- "Anything new in my classes?" → `get_recent_activity`
- "Show my grades in <course>" → `list_assignments`

If Poke doesn't pick the integration, send `clearhistory` and try again (per Poke's docs).
