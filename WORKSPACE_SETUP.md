# Authenticated workspace

Deploy `app.py` on Streamlit Cloud with Python 3.12. Set `ADMIN_USERNAME`, `ADMIN_PASSWORD` (12+ characters) and a persistent PostgreSQL `DATABASE_URL` under Settings → Secrets. Use your own private values; never commit them. See `secrets.example.toml` for syntax. The app has no default password and requires configuration before showing any data.

Sign in as administrator and switch on **Manage users** in the sidebar to create viewers, reset passwords, and disable/enable accounts. Passwords are salted PBKDF2 hashes, repeated login failures lock the account temporarily, and disabled/reset sessions are revoked. Each app uses separate database tables, so it can safely use the same PostgreSQL database as Stock-Planning without replacing its accounts or workbook. Viewer IDs must be created in each app; this is not single sign-on.

Tables reuse Stock-Planning's React grid: per-column text/value/numeric filters, sorting, optional totals across filtered rows, hide/unhide columns, 20-record pagination, full-screen tables, and full-window row details. Filters run locally without rerunning a search or calculation. Escape exits details/full-screen. FDA source links appear in full-window row details. Column visibility and totals are remembered per table in this browser. Totals add numeric values; select columns with compatible units.

Viewers have no file download buttons or data export toolbar. Visible information can still be copied or captured. Administrators retain existing app downloads. The prebuilt `workspace_dist` directory is included, so Streamlit needs no Node build step. To rebuild after frontend changes: `cd workspace_frontend`, `npm install`, `npm run check`, `npm run build`.

BOE only: administrator uploads, manual entry and calculation remain available. Each successful calculation saves the latest shared result to PostgreSQL for viewers and after restarts. Excel generation stays admin-only. Research searches remain available to both roles; existing FDA/CDSCO loading and matching rules remain unchanged. The optional research API/Zoho integration keeps its existing separate authentication.

Research tabs use a shared result-card layout. Filter results directly in column headers; there is no separate Filter Controls panel. Next/Previous navigate all loaded matches without limiting the search to the first 20. Source metadata and unfiltered administrator Excel downloads are under Source details. For filtered exports, use Export filtered CSV in the table toolbar.

Validation: `python -m unittest discover -s tests -v`; frontend: `cd workspace_frontend` then `npm test`, `npm run check`, `npm run build`. DOM tests exercise pagination, cross-page filters/totals, full-window details, and role restrictions; live browser layout needs separate inspection.

Startup imports now use an app-specific account package. After deployment, reboot the Streamlit app once to clear legacy helper modules. Existing Secrets, accounts and PostgreSQL table names are unchanged. Root workspace_auth/workspace_store modules remain compatibility imports.
