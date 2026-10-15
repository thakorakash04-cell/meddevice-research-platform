# Unified Zoho Cliq bot

This app is connected through the shared standalone backend in [Stock-Planning/zoho_bot](https://github.com/thakorakash04-cell/Stock-Planning/tree/main/zoho_bot).

Deploy that backend once, create one Cliq bot, and use its Message Handler. Do not deploy another Streamlit process for the bot. Follow the shared guide for private environment settings and admin-approved Cliq-to-app account mappings. The service loads this app at a pinned commit and checks its existing active account, session version and use_tools permission on each request. It logs successful tool access in this app's existing access log.

The shared backend supports stock tables, BOE saved results/calculations, FDA/CDSCO searches, AWC catalogue lookups and explicitly clinician-confirmed structured assessments. Image review remains in AWC's dashboard. Streamlit UI, app credentials and data storage are unchanged.
