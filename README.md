# Applicant Zero

Applicant Zero is a private job-discovery, preparation and tracking workspace for Rishi's Sydney job search.

## Current local pilot

Applicant Zero reads permitted public job listings and prepares a transparent application pack. Rishi applies personally on the employer’s site. It:

1. imports a safe demo job feed;
2. checks location, seniority and role-family fit;
3. explains matched and missing evidence;
4. recommends one of the three approved résumé families;
5. highlights public listing details such as salary, closing information and public contact emails;
6. creates truthful, reviewable résumé and cover-letter materials; and
7. stores every discovery, preparation and tracker decision in a local SQLite database.

No private profile, résumé, credential, visa document, password or application answer belongs in this repository.

## Future stages

- Add reliable hosted scheduling after the local workflow is proven.
- Add more verified public career boards and recruitment-agency sources.
- Add a read-only job-search Gmail sync after a separate job-search inbox is set up.
- Improve the dashboard's role-lane filtering and preparation workflow.

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

For the Sydney pilot, a public starter list of 20 currently verified company boards is already included. Run:

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

Use **Application operations** for the ordered working queue. It separates current roles that are ready for local preparation from roles that need an evidence decision, and can prepare up to three eligible roles in one action. Bulk preparation creates only private material files; it does not open an employer site, use AI credits or submit anything.

### Search campaigns

Use **Search campaigns** to choose the role groups included in future discovery refreshes: Data/BI and business analysis, IT support and service desk, broader entry-level IT, and full-time administration. The selection is stored privately in `private/search_campaigns.json`. Sydney and NSW are searched separately; an advertisement labelled only “NSW” is kept for location review rather than automatically treated as a Sydney job.

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

## Preparation workflow

Open **Prepare application** for a job. Its preparation brief shows the evidence that matched, the requirements to check, and listing intelligence drawn only from the imported description:

- advertised salary where present;
- closing wording where present;
- public contact email addresses where present;
- employment type and location signals; and
- the approved résumé family and its evidence route.

Select **Prepare role materials** to save a local evidence manifest, application packet and editable Word copy. Select **Generate AI tailoring draft** only when you want a review draft; it uses your own private evidence and must be checked before use. Open the original listing yourself, submit personally, then record the employer confirmation to update the tracker.

Applicant Zero does not open, scan or fill employer application forms. It does not store passwords, create employer accounts, solve CAPTCHA challenges or submit applications.

Opening a preparation brief also creates `private/application_answers.json` from the verified values already in the private candidate profile. It keeps reusable answers locally and lists salary, notice period, LinkedIn, portfolio and similar unknowns separately until confirmed.

## Optional AI tailoring drafts

AI drafting is optional. It creates a review draft only; you must check every line before using it. The request is instructed to use only the evidence you place in a private evidence library and to flag unsupported requirements.

Create the private evidence library once:

```powershell
Copy-Item templates\candidate_evidence.example.json private\candidate_evidence.json
```

Replace the example sentence with verified facts from your employment, projects and education. Do not add passwords, visa documents, or claims you cannot support.

The **Approved résumé evidence** action also builds a private inventory from each approved PDF and any linked editable Word master. It extracts original wording locally, records file fingerprints, and never edits either source. The readiness checklist requires evidence for the selected résumé family before treating a role as ready for final review.

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

Create one private profile on your computer. It keeps your current answers and the locations of your approved résumé PDFs together. It is excluded from GitHub and must never contain a password.

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

Applicant Zero can refresh permitted public career-board sources three times a day on this computer. It updates the existing local database and saves a private run log. It does not apply for jobs or create paid AI drafts during a scheduled refresh.

To test one refresh manually:

```powershell
.\scripts\refresh_company_boards.ps1
```

To create the default 8:00 AM, 1:00 PM and 6:00 PM local schedule while this computer is on and you are signed in:

```powershell
.\scripts\create_daily_refresh_task.ps1
```

The default schedule checks public company boards only. If you have chosen to configure the optional Adzuna broad job-feed API, create the schedule with up to three controlled queries per run:

```powershell
.\scripts\create_daily_refresh_task.ps1 -MaxQueries 3
```

Check the local schedule at any time:

```powershell
.\scripts\show_discovery_tasks.ps1
```

The **System health** page shows whether the newest private refresh log completed successfully. Remove the schedule later with `scripts\remove_daily_refresh_tasks.ps1`.

Open the dashboard after a refresh to review new jobs. The future hosted version will run independently of this computer; this local schedule is the safe first automation step.

## Running the prototype

After Python is installed locally, open the VS Code terminal in this folder and run:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --demo
```

The first line tells Python where the local program files are. The second writes `data/applicant_zero.sqlite3` locally and prints a ranked queue. The database is excluded from Git.

### Eligibility and role-readiness decisions

Before a role is prepared, Applicant Zero now detects explicit citizenship, residency, clearance, work-rights and sponsorship conditions in the imported listing. A direct citizenship or residency conflict with the confirmed private profile is marked **blocked**. Other conditions stay visible as **confirm** items for the candidate to verify in the employer form. The system does not infer protected answers or submit declarations.

### Listing links and personal submission

Applicant Zero keeps the original listing link for every discovered role and marks whether the link is a direct hosted listing, likely to need login, or appears multi-step. This is context for your own application process, not browser automation. The tracker changes to Applied only after you record an employer confirmation.

### Lifecycle reporting and recovery

The tracker separates Applied, Interview, Offer, Rejected and Closed outcomes. Search progress reports application, interview and response rates from only the facts you record. The private runtime already creates verified SQLite snapshots before dashboard, refresh and collection operations; a damaged tracker is quarantined and restored only from a verified snapshot when available.

## Everyday workflow

The dashboard’s **How to use this** page gives the normal six-step routine: refresh, review, prepare, verify, apply personally, then record the outcome. It is also the quickest place to see which actions Applicant Zero performs locally and which employer-facing actions remain yours.

## Daily workflow

The review queue includes **Today’s workflow**: an ordered local plan based on role fit, evidence gaps, preparation effort, tracker status and the latest discovery-log health. It links directly to **Application operations** and **Manual actions**, so the next useful step stays visible without hunting through the dashboard.
