# Applicant Zero

Applicant Zero is a private job-discovery and application-preparation tool for Rishi's Sydney data, business intelligence and junior business analysis search.

## Current local pilot

Applicant Zero reads permitted public job listings and can open a selected employer application in a supervised browser. It never clicks the final submission button. It:

1. imports a safe demo job feed;
2. checks location, seniority and role-family fit;
3. explains matched and missing evidence;
4. recommends one of the three approved résumé families;
5. classifies the application route and records compatibility checks;
6. fills stable contact fields and an approved résumé on supported forms; and
7. stores every decision and browser-assistance event in a local SQLite database.

No private profile, résumé, credential, visa document, password or application answer belongs in this repository.

## Future stages

- Add reliable hosted scheduling after the local workflow is proven.
- Add employer systems beyond Lever and Greenhouse after supervised testing.
- Measure completion rates and the reasons applications need human input.
- Add support for more application systems after each one passes a supervised pilot.

## First live discovery source: Adzuna

Applicant Zero supports Adzuna's official Australian job-search API as its first live source. It searches and scores vacancies only; it does not submit applications.

1. Register for a free API key at https://developer.adzuna.com/signup.
2. Create a file named `.env` in the project folder. This file is private and excluded from Git.
3. Add your credentials using this format:

```text
ADZUNA_APP_ID=your_app_id
ADZUNA_APP_KEY=your_app_key
```

4. In the VS Code terminal, run:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --adzuna --query "data analyst" --where "Sydney"
```

The API's default documented access limit is 2,500 requests each month, which is sufficient for the local discovery-and-matching validation stage. Do not share the `.env` file or either API credential in chat or GitHub.

## Company career-board discovery

The preferred first live source is public company career boards. Greenhouse and Lever publish open positions through documented public GET endpoints, so no account or API key is required to discover the roles.

1. Add only companies whose careers pages you want Applicant Zero to monitor to a private `data/company_boards.json` file.
2. Run:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --company-boards data/company_boards.json
```

The private company-board list is excluded from Git. This command only reads public job listings and records matching results locally; it does not open or submit an application.

For the Sydney pilot, a public starter list of 12 currently verified company boards is already included. Run:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --company-boards data/company_boards.starter.json
```

## Local review dashboard

After a discovery run, open a browser-based local review queue:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --dashboard
```

The dashboard opens only on your computer and displays the jobs already saved in the local database. Keep the terminal open while using it, then press `Ctrl+C` in the terminal to stop it.

Use the **Your tracker** column to keep the job's progress as New, Saved, Preparing, Applied, Interview, or Closed. You can also save a short personal note. This is your own local record; it does not contact the employer or submit anything.

When you record an employer confirmation after submitting, Applicant Zero creates a private follow-up reminder for eight business days later. It appears in **Daily priorities** and can be marked completed with an optional note. It never sends a follow-up message itself.

The queue starts with **Current listings** and **Live sources** enabled, so expired listings and the original demo examples do not clutter the review. Use the search box, recommendation buttons, company, source and tracker-stage selectors to narrow the queue. Turn off **Current listings** when you need to review a role that has disappeared from its company board. If one employer career board is temporarily unavailable, the refresh records the remaining boards instead of failing the entire search or incorrectly closing that employer's saved jobs.

Applicant Zero records when each role was first and last seen. Repeated copies with the same company, title and location are combined in the queue, while their underlying records remain available locally. Tracker notes survive every refresh, and the first move to **Applied** records the submission time. The Insights cards show current listings, roles worth reviewing, strong matches, submitted applications and interviews. **Company boards checked** shows the number of employer boards that completed during the latest refresh, rather than the number of job-site types.

The dashboard also records the last completed discovery refresh and provides a **New this week** filter. Use it after the daily refresh to focus on newly collected current listings instead of scanning the entire queue again.

## Daily operations

The existing refresh script now runs the complete daily discovery bundle: it checks your company boards, runs seven focused Sydney search queries when Adzuna is configured, records source health, and creates a private `daily_priority_digest.html` file. If Adzuna has not been configured, the company-board refresh still completes and the dashboard records that the query source was skipped.

Run it manually with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\refresh_company_boards.ps1"
```

Open **Daily priorities** in the dashboard whenever you want a short ordered list of new roles, roles already being prepared, and follow-ups. It is generated locally and uses no OpenAI API credits.

## Reliability and private backup

Use **System health** in the dashboard to confirm the profile, local database, and most recent discovery run are ready. You can also run `python -m applicant_zero --health-check` from the project terminal.

Create a dated local backup of your tracker and private configuration with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\backup_private_data.ps1"
```

The backup is kept only under `private\backups` on your computer and is excluded from GitHub.

The current local operating model and the conditions required before considering cloud hosting are documented in [operating-and-hosting-readiness.md](docs/operating-and-hosting-readiness.md).

The matcher also checks explicit experience requirements. A role that asks for four or more years is held for review even when its title does not say senior. Listings that mention unrestricted work rights or no sponsorship show a work-rights requirement to verify before application preparation.

Select **Prepare brief** under a role title to open its private preparation page. It shows the imported job description, matching evidence, requirements to check and a truthful application checklist.

### Listings you find yourself

Use **Add a job from another website** at the top of the dashboard for a public listing found on SEEK, LinkedIn, Indeed or a company site. Paste its link and job description once. Applicant Zero scores it, stores it in the same tracker, creates the same preparation brief and can generate a truthful AI review draft. It does not scrape the source website or submit anything.

From a preparation brief, select **Save private application packet** to create a Markdown packet in `private/application_packets`. It records the listing, approved résumé file, evidence, requirements to check and application checklist. The packet stays on your computer and is excluded from GitHub.

## Supervised application pilot

The dashboard labels every job by its application route. Lever forms have passed the browser-assistance test, while Greenhouse forms remain a supervised pilot because their browser-rendering behaviour varies. SEEK and LinkedIn can use a supervised login handoff: you sign in yourself, then Applicant Zero waits for a visible application form and fills only safe reusable answers. Workday gets the same supervised handoff for its multi-step forms. Unknown systems stay in manual review.

Install the free local browser-control package once:

```powershell
python -m pip install -e ".[browser]"
```

Open **Prepare application** for a job, then:

1. Select **Scan application form** to inspect its current field count, required fields, account requirement and CAPTCHA markers.
2. Select **Open assisted application** for a supported route.
3. Review the separate browser window. Applicant Zero fills stable contact information, location, availability, the approved résumé and reusable notice-period or profile-link answers. It uses the advertised salary range when one is clearly stated, otherwise your private fallback, and can choose a clearly matching "how did you hear about us" option.
4. On a supported multi-step form, it keeps watching for the next ordinary page, fills newly visible verified fields and can move through a normal **Next** or **Continue** step once every required field on that step is already complete. It stops for CAPTCHA, login, legal/identity declarations, unfamiliar questions and the final Submit button.
5. For a login handoff, sign in or complete account steps yourself. Applicant Zero does not enter, store or create passwords, and it waits for an application form before filling safe fields.
6. Complete the highlighted unanswered fields, verification and any work-rights, salary or personal questions yourself.
7. Review the entire application before choosing the employer's Submit button yourself.

The browser uses a private local profile under `private/browser_profile`. Login sessions may be retained there by the browser, while Applicant Zero never stores or creates passwords. Every route scan and assistance attempt appears under **Application activity** in the job brief.

Opening a preparation brief also creates `private/application_answers.json` from the verified values already in the private candidate profile. It keeps reusable answers locally and lists salary, notice period, LinkedIn, portfolio and similar unknowns separately until confirmed.

## Optional AI tailoring drafts

AI drafting is optional. It creates a review draft only; you must check every line before using it. The request is instructed to use only the evidence you place in a private evidence library and to flag unsupported requirements.

Create the private evidence library once:

```powershell
Copy-Item templates\candidate_evidence.example.json private\candidate_evidence.json
```

Replace the example sentence with verified facts from your employment, projects and education. Do not add passwords, visa documents, or claims you cannot support.

To enable the drafting button, create an OpenAI API key, then set it for the current terminal session without saving it in Git:

```powershell
$env:OPENAI_API_KEY = "paste_your_API_key_here"
```

Check the setup without exposing the key:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --tailoring-check
```

Open a role's preparation brief and select **Generate AI tailoring draft**. The output is saved as a private JSON file in `private/application_packets`. The request uses the OpenAI Responses API with `store: false`.
The same brief then displays the saved review draft, including suggested résumé bullets, a cover-letter draft, unsupported requirements and questions to confirm.
The setup check confirms only that a key value is present; the first draft verifies that the key is valid for the API.

Drafting uses the cost-conscious `gpt-5.6-terra` model by default and limits each response to 1,200 output tokens. The saved review shows the API-reported input and output token count. Set `APPLICANT_ZERO_MODEL` only if you deliberately want a different model.

After reviewing a generated draft, select **Create tailored resume review**. It creates a printable private résumé editing pack for the chosen résumé family, with the proposed summary, bullet wording, cover letter, application-answer drafts, unsupported requirements and questions to resolve. It does not overwrite your approved PDF; that keeps every final résumé change reviewable.

Use **Application question workspace** on a preparation brief for unfamiliar role-specific questions. Paste the question and Applicant Zero creates a short private review draft from your verified evidence. It refuses to draft visa, work-rights, identity, health or similar personal-eligibility answers; complete those directly in the employer form.

## Application readiness and confirmation

Each preparation brief now shows a private readiness checklist: approved résumé, AI tailoring draft, tailored résumé review, reusable application answers and your final review. Select **Mark materials reviewed** only after you have checked the role-specific content.

Applicant Zero does not submit applications. After an employer site confirms that you submitted, use **Record employer confirmation and mark Applied** to save a confirmation reference, confirmation-page link or short note. This records the submission date and proof in your local tracker.

## Private candidate profile

Before application assistance is enabled, create one private profile on your computer. It keeps your current answers and the locations of your approved résumé PDFs together. It is excluded from GitHub and must never contain a password.

```powershell
New-Item -ItemType Directory -Force private
Copy-Item templates\candidate_profile.example.json private\candidate_profile.json
```

Open `private/candidate_profile.json` in VS Code and replace each `REPLACE_...` value with your current, truthful information. Do not enter a future visa status before it is actually in effect. Then run:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --profile-check
```

The check reports only what is still missing; it does not print your personal information.

## Daily local refresh

Applicant Zero can refresh its permitted public career-board sources every morning on this computer. It updates the existing local database and saves a local run log. It does not apply for jobs.

To test one refresh manually:

```powershell
.\scripts\refresh_company_boards.ps1
```

To schedule it for 8:00 AM each day while this computer is on and you are signed in:

```powershell
.\scripts\create_daily_refresh_task.ps1
```

Open the dashboard after a refresh to review new jobs. The future hosted version will run independently of this computer; this local schedule is the safe first automation step.

## Running the prototype

After Python is installed locally, open the VS Code terminal in this folder and run:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --demo
```

The first line tells Python where the local program files are. The second writes `data/applicant_zero.sqlite3` locally and prints a ranked queue. The database is excluded from Git.
