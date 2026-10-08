# MedDevice Research bot for Zoho Cliq

This bot supports natural-language research with Gemini, plus keyword commands.
The existing Streamlit website continues to load all matching FDA results.
The bot intentionally retrieves at most five FDA records in one request,
and returns the total hit count. CDSCO queries use the repository's Parquet
snapshots. These are matching records, not independently verified regulatory
advice; the manufacturer/importer commands reflect the recorded applicant role.

## 1. Deploy the API

Create a Render Web Service and connect this GitHub repository.
Use the branch containing these files and the repository root directory.

- Runtime: Python
- Build command: `pip install -r requirements-api.txt`
- Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Set environment variables in the hosting dashboard:

- `CLIQ_API_KEY`: generate a long random secret; use the same value in Cliq.
  A password-manager generator can create it entirely in your browser.
- `STREAMLIT_APP_URL`: your existing HTTPS Streamlit app URL (optional).
- `GEMINI_API_KEY`: your Gemini API key. Keep it in Render only, never GitHub or Cliq.
- `GEMINI_MODEL`: optional model override. Default: `gemini-3.5-flash-lite`.
  Choose a generateContent model available to your key if the default is unavailable.

Use an always-on instance for dependable chat responses. Sleeping services
can take too long to start for Zoho's synchronous invokeURL limit (40 seconds).
Do not deploy this API using Streamlit's start command.
The two CDSCO Parquet files must be present at the repository root.
Database snapshots are cached until process restart. After daily GitHub data
updates, redeploy/restart this service to load the latest files; enable automatic
deployment on commits if supported. `/health` checks process health only.

## 2. Test the hosted service

Open `https://YOUR_API_HOST/health`: expect `{"status":"ok"}`.
POST JSON `{"message":"help"}` to `/chat`, with `Content-Type: application/json`
and `X-API-Key: YOUR_SECRET`. Expect a `text` field listing commands.
Missing or wrong keys return 401; a missing server key returns 503.
Test `risk laser` to confirm the CDSCO files are included in the deployment.

## 3. Connect Zoho Cliq

Open Cliq's developer platform (Bots & Tools), create a bot called
MedDevice Research Bot, and open its Message Handler.
Paste the contents of `cliq_message_handler.deluge`.
Replace `https://YOUR_API_HOST/chat` with your deployed URL, and replace
`REPLACE_WITH_YOUR_SECRET_KEY` with the exact `CLIQ_API_KEY` value.
Save, subscribe to the bot, and message it directly with `help`.
Keep the real secret out of GitHub. For production, use a Zoho Connection
configured to send the X-API-Key header and update invokeurl to use that connection.

## Commands

| Message | Search |
| --- | --- |
| `fda photodynamic` | FDA 510(k) devices, newest first |
| `fda catheter | Abbott` | Device and applicant filter |
| `risk laser` | CDSCO risk classification records |
| `manufacturer catheter` | Manufacturer registrations |
| `importer catheter` | Importer registrations |

Keyword searches use all-word matching. Gemini translates natural-language requests
into the same supported searches and summarizes only the displayed records.

## Upgrade an existing Render/Cliq deployment (browser only)

1. In Render Environment, add GEMINI_API_KEY. Keep CLIQ_API_KEY unchanged.
2. Optionally set GEMINI_MODEL to a generateContent model available for your key.
3. Save and deploy the latest main commit (Manual Deploy if auto-deploy is off).
4. Replace the Cliq Message Handler with the updated cliq_message_handler.deluge.
   Restore your existing Render /chat URL and the existing CLIQ_API_KEY secret.
5. Test "Find FDA-cleared photodynamic devices", then "Only Abbott".
   Also test "What is the CDSCO risk class of a diode laser?".
6. Send "reset" to clear the previous search.

Natural-language requests send question text and the previous search parameters to
Google Gemini. Summaries send the displayed research records. User/chat IDs stay
on this API server; they are not sent to Gemini. Follow-up memory is isolated by
both user ID and chat ID, lasts 30 minutes, and disappears on service restart or
redeploy. Use one API worker/instance for this memory design. Older handlers without
IDs still support independent questions but do not retain follow-up context.

Supported follow-ups include changing the company, changing to importer/manufacturer,
and explaining/comparing the last displayed sample. This is not full transcript memory.
Date/class filters, multi-source combined searches, full-result chat exports, and
unrelated tasks are not supported; Gemini is instructed to explain or clarify scope.
The website still provides complete results and downloads. Classifications are not
independently inferred from AI knowledge. Gemini summaries are interpretations;
raw source records are included for checking. No live web browsing by Gemini is enabled.

A natural-language search can use two Gemini requests (interpretation and summary).
Keyword commands do not use Gemini. Gemini quota/access failures return useful
messages; summary failure falls back to raw records. API calls use short timeouts
for Cliq, but cold starts or slow searches can still time out. Gemini charges/quotas
are governed by your Google account.


## Validation and troubleshooting

Run `python -m unittest discover -s tests` locally after installing
`requirements-api.txt` and `httpx`. Tests mock FDA, so do not hit live services.
If Cliq cannot respond, first test the hosted `/chat` endpoint with the key.
503 on CDSCO searches means a required snapshot or column is missing.
FDA service errors return a retry message; no matches are reported separately.

Official references:
- https://render.com/docs/deploy-fastapi
- https://www.zoho.com/cliq/help/platform/bot-messagehandler.html
- https://www.zoho.com/deluge/help/webhook/invokeurl-api-task.html
