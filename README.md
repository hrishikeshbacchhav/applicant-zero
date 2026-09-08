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

Select **Prepare brief** under a role title to open its private preparation page. It shows the imported job description, matching evidence, requirements to check and a truthful application checklist.

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

## Running the prototype

After Python is installed locally, open the VS Code terminal in this folder and run:

```powershell
$env:PYTHONPATH = "src"
python -m applicant_zero --demo
```

The first line tells Python where the local program files are. The second writes `data/applicant_zero.sqlite3` locally and prints a ranked queue. The database is excluded from Git.
