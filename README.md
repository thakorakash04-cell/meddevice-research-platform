# ⚕️ MedDevice Research Platform (Dual Jurisdiction: US FDA & CDSCO India)

A high-transparency regulatory intelligence platform for medical device research across **US FDA 510(k)** and **CDSCO (India)** government databases.

---

## 🌟 Key Features

1. **🇺🇸 US FDA 510(k) Premarket Clearances**:
   - Live query integration with openFDA CDRH API.
   - Applicant-centric device grouping with registered address & regulatory contacts.
   - Clickable direct links to official **FDA PMN Web Records** and **Summary PDFs**.
   - Instant export to Excel (`.xlsx`).

2. **🇮🇳 CDSCO India Intelligence**:
   - **Step 1 (Risk Classification Lookup)**: 3,665 official classified devices across 24 medical device domains combining `ListOfApprovedRiskDevice` and `Approved Device Class A (NSNM) Details (ListOfApprovedRiskNSSMDevice)`.
   - **Step 2 (Available Manufacturers & Importers)**: 104,451 official registrations (78,962 Domestic Manufacturers + 25,489 Importers) with real license numbers, entity addresses, and issuing authorities.
   - Role filters (Both, Manufacturer Only, Importer Only) & Category multi-select.

3. **🤖 In-Built AI Smart Search & Regulatory Synonyms**:
   - AI-assisted semantic query expansion (e.g. *Stent ➔ Scaffold/Endoprosthesis/Graft*, *Ablation ➔ Radiofrequency/Cryo/Microwave*, *Bandage ➔ Dressing/Gauze/Tape*).
   - Sidebar toggle between AI Smart Search and Strict Exact Keyword matching.

4. **🛡️ Data Provenance & Transparency**:
   - Real-time SHA-256 cryptographic payload & database checksums.
   - Automated weekly synchronization timestamp badge.
   - Official source portal URL attribution for every record.

5. **📥 Excel & PDF Reports**:
   - Direct download of filtered search results for FDA and CDSCO to `.xlsx`.
   - Download full official databases (Risk List & Approved Devices).

---

## 🚀 Local Setup & Running

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd "Market Summary"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch Streamlit
streamlit run app.py
```

---

## ☁️ Deploying to Streamlit Community Cloud (Streamlit Web)

1. Push this repository to **GitHub**:
   ```bash
   git add .
   git commit -m "Initial commit of MedDevice Research Platform"
   git remote add origin https://github.com/<your-username>/<your-repo-name>.git
   git branch -M main
   git push -u origin main
   ```
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and log in with GitHub.
3. Click **"New app"** and select:
   - **Repository**: `<your-username>/<your-repo-name>`
   - **Branch**: `main`
   - **Main file path**: `app.py`
4. Click **"Deploy!"** — your app will be live on a public URL like `https://<your-app-name>.streamlit.app`!
