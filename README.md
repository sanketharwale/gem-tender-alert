# GeM Tender Alert

An independent alert bot that checks the publicly accessible GeM **All Bids** page and emails detected listings.

Official portal: https://bidplus.gem.gov.in/all-bids

## Current behaviour

- Requests the public All Bids page and extracts bid-like links from the returned HTML.
- On the first successful run, when there is no saved `seen_bids.json` state, emails all listings it can extract from that page.
- After a successful email, saves detected bid identifiers to `seen_bids.json` so later runs email only newly detected listings.
- Runs daily at **08:00 India Standard Time (IST)** using GitHub Actions (02:30 UTC). GitHub may delay scheduled jobs.
- Can also be started manually from **Actions → GeM Tender Alert → Run workflow**.

## Configure email secrets

In the repository, open **Settings → Secrets and variables → Actions → New repository secret**.

Add these secrets:

1. `EMAIL_SENDER` — Gmail address used to send alerts.
2. `EMAIL_APP_PASSWORD` — Gmail App Password, not your normal Gmail password.
3. `ALERT_TO_EMAIL` — recipient address for alerts. It can be the same Gmail address as `EMAIL_SENDER`.

Gmail App Passwords require 2-Step Verification. Keep these values in GitHub Secrets only; never commit or share them in code or chat.

## First run note

The first run can email **all listings successfully extracted from the page**, not necessarily every bid available on GeM. Review the email volume before relying on it. After the email is sent successfully, the workflow commits the seen-bid state so future runs can send only new listings.

## Important limitations

- This is a basic HTML scraper, not an official GeM API integration. It depends on the HTML returned to GitHub Actions and can break if GeM changes the page or loads results with JavaScript.
- It may not retrieve all pages or every bid; a successful run is not proof of complete coverage of all government tenders.
- If no bid-like records are extracted, the script intentionally fails instead of silently reporting success.
- Verify bid number, buyer, eligibility, documents, and deadline on the official GeM portal before acting.
- This repository is independent and is not affiliated with or endorsed by GeM or the Government of India.
- The bot does not attempt to bypass CAPTCHA, login, or access controls.
