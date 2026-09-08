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

The queue starts with **Current listings** and **Live sources** enabled, so expired listings and the original demo examples do not clutter the review. Use the search box, recommendation buttons, company, source and tracker-stage selectors to narrow the queue. Turn off **Current listings** when you need to review a role that has disappeared from its company board. If one employer career board is temporarily unavailable, the refresh records the remaining boards instead of failing the entire search or incorrectly closing that employer's saved jobs.

Applicant Zero records when each role was first and last seen. Repeated copies with the same company, title and location are combined in the queue, while their underlying records remain available locally. Tracker notes survive every refresh, and the first move to **Applied** records the submission time. The Insights cards show current listings, roles worth reviewing, strong matches, submitted applications and interviews. **Company boards checked** shows the number of employer boards that completed during the latest refresh, rather than the number of job-site types.

The matcher also checks explicit experience requirements. A role that asks for four or more years is held for review even when its title does not say senior. Listings that mention unrestricted work rights or no sponsorship show a work-rights requirement to verify before application preparation.

Select **Prepare brief** under a role title to open its private preparation page. It shows the imported job description, matching evidence, requirements to check and a truthful application checklist.

From a preparation brief, select **Save private application packet** to create a Markdown packet in `private/application_packets`. It records the listing, approved résumé file, evidence, requirements to check and application checklist. The packet stays on your computer and is excluded from GitHub.

## Supervised application pilot

The dashboard labels every job by its application route. Lever forms have passed the browser-assistance test, while Greenhouse forms remain a supervised pilot because their browser-rendering behaviour varies. SEEK and LinkedIn are labelled as requiring the candidate's login, Workday is labelled as a complex multi-step form, and unknown systems stay in manual review.

Install the free local browser-control package once:

```powershell
python -m pip install -e ".[browser]"
```

Open **Prepare application** for a job, then:

1. Select **Scan application form** to inspect its current field count, required fields, account requirement and CAPTCHA markers.
2. Select **Open assisted application** for a supported route.
3. Review the separate browser window. Applicant Zero fills stable contact information, location, availability, the approved résumé and any reusable salary, notice-period or profile-link answers you have already confirmed.
4. Complete the highlighted unanswered fields, verification and any work-rights, salary or personal questions yourself.
5. Review the entire application before choosing the employer's Submit button yourself.

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
