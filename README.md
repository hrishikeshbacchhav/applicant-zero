# Applicant Zero

Applicant Zero is a private job-discovery and application-preparation tool for Rishi's Sydney data, business intelligence and junior business analysis search.

## First prototype

The first local prototype does not access job sites or submit applications. It:

1. imports a safe demo job feed;
2. checks location, seniority and role-family fit;
3. explains matched and missing evidence;
4. recommends one of the three approved résumé families; and
5. stores every decision in a local SQLite database.

No private profile, résumé, credential, visa document, password or application answer belongs in this repository.

## Later stages

- Replace the demo feed with permitted discovery sources.
- Add a local review dashboard and application tracker.
- Generate tailored application packets.
- Test form assistance source by source, without bypassing platform controls.

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

For the first Sydney pilot, a public starter list is already included. Run:

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

The queue starts with **Live jobs only** so the original demo examples do not clutter the review. Use the search box, recommendation buttons and source selector to narrow the queue. If one employer career board is temporarily unavailable, the refresh records the remaining boards instead of failing the entire search.

The Insights cards count live listings only. **Company boards checked** shows the number of employer boards that completed during the latest refresh, rather than the number of job-site types.

Select **Prepare brief** under a role title to open its private preparation page. It shows the imported job description, matching evidence, requirements to check and a truthful application checklist.

From a preparation brief, select **Save private application packet** to create a Markdown packet in `private/application_packets`. It records the listing, approved résumé file, evidence, requirements to check and application checklist. The packet stays on your computer and is excluded from GitHub.

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
