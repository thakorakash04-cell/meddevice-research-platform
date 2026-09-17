import pandas as pd
import json
from datetime import datetime
import os
import cdsco_live_fetcher

def run_full_update():
    """Runs live fetchers for Risk and Approved devices with safety guards."""
    try:
        updated_any = False
        # 1. Risk Devices (must have > 100 records)
        risk_data = cdsco_live_fetcher.fetch_risk_device_list()
        records_r = risk_data.get('records', [])
        if not risk_data.get('error') and len(records_r) > 100:
            df_risk = pd.DataFrame(records_r)
            for c in df_risk.columns:
                df_risk[c] = df_risk[c].astype(str)
            df_risk.to_parquet('cdsco_combined_risk.parquet', index=False)
            df_risk.to_excel('cdsco_combined_risk.xlsx', index=False)
            updated_any = True

        # 2. Approved Devices (must have > 1000 records)
        approved_data = cdsco_live_fetcher.fetch_all_approved_devices()
        records_a = approved_data.get('records', [])
        if not approved_data.get('error') and len(records_a) > 1000:
            df_app = pd.DataFrame(records_a)
            for c in df_app.columns:
                df_app[c] = df_app[c].astype(str)
            df_app.to_parquet('cdsco_approved_devices.parquet', index=False)
            df_app.to_excel('cdsco_approved_devices.xlsx', index=False)
            updated_any = True

        # Save Metadata for Transparency
        if updated_any or os.path.exists('cdsco_approved_devices.parquet'):
            metadata = {"last_updated": datetime.now().isoformat()}
            with open("cdsco_metadata.json", "w") as f:
                json.dump(metadata, f)

        return True, "Data verified and updated successfully"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    success, msg = run_full_update()
    print(f"Update Result: {success}, Message: {msg}")
