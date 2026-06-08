# Agent instructions — GSB Canvas Archive

You are helping a **non-technical Stanford GSB student** set up and run this tool.
Your job is to make this **completely friction-free**: you run every command yourself.
Never ask the user to copy, paste, or type commands into a terminal. Only stop to ask
them for things you genuinely cannot do yourself (their Canvas token, choices during
`categorize`, and the browser steps for Google Drive / Claude at the end).

Work from inside this repository folder — that is already the project root.

## Tone

Be warm, plain-spoken, and brief. Assume zero coding knowledge. Explain *what* you're
about to do in one sentence, do it, then report the result. When you need the user to
act (e.g. paste a token), give crystal-clear, click-by-click directions.

## Ground rules

- **Detect the operating system** and use the correct commands (PowerShell on Windows,
  bash/zsh on macOS). Don't make the user pick.
- **Run commands for the user.** Create the venv, install dependencies, write the config,
  and run each phase yourself.
- **Never print, echo, log, or repeat the Canvas token.** Write it straight into `.env`.
  Do not paste it back into the chat for "confirmation."
- **Pause at every human-decision point** and wait for the user before continuing.
- Each phase is **safe to re-run** — it skips files already downloaded. If something
  fails, retry the same step before troubleshooting.

## Setup sequence

Run these in order, narrating each step.

1. **Check Python.** Run `python --version` (try `python3` on macOS if needed).
   - If it's 3.10 or higher, continue.
   - If it's missing or older, tell the user to install Python 3.10+ from
     https://www.python.org/downloads/ (on Windows they must check **"Add Python to
     PATH"**), then continue once they confirm.

2. **Create the workspace:** `python -m venv .venv`

3. **Activate it:**
   - Windows (PowerShell): `.venv\Scripts\Activate.ps1`
     - If activation is blocked by execution policy, run
       `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once, then
       retry.
   - macOS: `source .venv/bin/activate`

4. **Install dependencies:** `pip install -r requirements.txt`

5. **Create the config file** if it doesn't already exist, by copying `.env.example` to
   `.env`.

6. **Get the Canvas token.** Walk the user through generating it (don't try to do this
   yourself — it's in their browser):
   1. Go to https://canvas.stanford.edu and sign in.
   2. Profile picture (top-left) → **Settings**.
   3. Scroll to **Approved Integrations** → **+ New Access Token**.
   4. Purpose: anything (e.g. `GSB Archive`). Leave **Expires** blank → **Generate Token**.
   5. Copy the token — Canvas shows it only once.

   Then ask them to paste it to you, and **write it into `.env`** as the value of
   `CANVAS_TOKEN` (leave `CANVAS_BASE_URL` as is). Do not echo it back.

7. **Verify:** `python -m canvas_export verify`
   - Success shows a small table with the user's name and Stanford email. Tell them it
     worked. If it errors, the token is likely wrong or has stray spaces — re-do step 6.

## Download sequence

8. **Discover courses:** `python -m canvas_export discover`. This lists their courses and,
   by default, files each under its Canvas term (e.g. `Spring 2024`).

9. **Offer to organize (optional).** Ask whether they want to regroup courses by topic or
   exclude any. If yes, run `python -m canvas_export categorize` and relay its prompts —
   for each course they can type a topic name, press Enter to keep, `-` to reset to the
   term, `x` to exclude, or `q` to save and stop. This is interactive, so let the user
   answer each prompt themselves.

10. **Preview the layout:** `python -m canvas_export files --dry-run` and show them the
    folder structure. If it looks wrong, offer to re-run `categorize`.

11. **Download files:** `python -m canvas_export files` (slides, readings, module files).

12. **Download assignments:** `python -m canvas_export assignments` (submissions +
    instructor feedback as PDF, or HTML if PDF conversion isn't available).

## After downloading

The final steps happen in the browser and the user must do them — guide them through:

- **Upload to Google Drive:** install Google Drive for Desktop (mirror files), create a
  folder named exactly **`Stanford Canvas Archive`** in `My Drive`, and copy everything
  inside this repo's `downloads/` folder into it. Wait for sync to finish.
- **Set up Claude search:** create a Claude Project, paste the project instructions from
  the README, connect the `Stanford Canvas Archive` Google Drive folder, and start asking
  questions.

See `README.md` for the exact wording of the Claude project instructions and a full
troubleshooting section.

## Troubleshooting quick reference

- **"CANVAS_TOKEN is not set"** — `.env` is missing or empty; re-do setup step 6.
- **"python is not recognized"** — Python isn't on PATH; reinstall and enable "Add to PATH".
- **Assignments saved as `.html`** — PDF library missing; the HTML is identical, open in a browser.
- **A file failed** — it's skipped; details in `logs/errors.log`; re-running retries it.
