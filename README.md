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

## Running the prototype

After Python is installed locally, run:

```powershell
python -m applicant_zero --demo
```

The command writes `data/applicant_zero.sqlite3` locally and prints a ranked queue. The database is excluded from Git.
