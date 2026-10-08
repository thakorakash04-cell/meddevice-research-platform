# MedDevice Research bot for Zoho Cliq

This is a command-based research bot, without an LLM or AI subscription.
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
  Generate locally with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- `STREAMLIT_APP_URL`: your existing HTTPS Streamlit app URL (optional).

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

Queries use all-word matching, without synonym expansion. FDA and CDSCO
are separate commands. Natural-language interpretation and asynchronous
full-result export are future features; neither is implemented here.

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
