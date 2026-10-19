# GeM Tender Alert

An independent alert bot that checks publicly accessible GeM bid listings for matches associated with **Osmanabad / Dharashiv, Maharashtra** and emails newly detected bids to `sanketharwale0078@gmail.com`.

## How it works

- Checks GeM's public ongoing-bids listing for the search terms Osmanabad, Dharashiv, and Maharashtra.
- Filters the returned public bid records for Osmanabad/Dharashiv references.
- Tracks previously seen bid numbers in `seen_bids.json`.
- Emails only newly detected matches.
- GitHub Actions is scheduled every 3 hours (UTC cron; GitHub may delay scheduled jobs).

Official portal: https://bidplus.gem.gov.in/all-bids

## Required GitHub Actions secrets

Open **Settings → Secrets and variables → Actions → New repository secret** and add:

- `EMAIL_SENDER`: the Gmail address used to send alerts (usually the same Gmail inbox).
- `EMAIL_APP_PASSWORD`: a Gmail App Password, not your normal Gmail password.

Do not put passwords in code, commit them to the repository, or share them in chat. Gmail App Passwords require 2-Step Verification to be enabled on the Google account.

## Run it manually

Open **Actions → GeM Tender Alert → Run workflow**. Check the run logs for the result.

## Important limitations

- This uses public portal search results, not an official GeM API. GeM may change the endpoint or response format, so runs can fail and need maintenance.
- Public search results may be delayed or incomplete. The bot only sees up to three result pages per search term by default.
- Location matching relies on the text returned in public bid records. A bid whose district is only mentioned inside an attached PDF may not be detected.
- Verify bid number, buyer, eligibility, documents, and deadline on the official GeM portal before acting.
- This repository is not affiliated with or endorsed by GeM or the Government of India.
- Requests are intentionally spaced out; this bot does not attempt to bypass CAPTCHA, login, or access controls.
