import pandas as pd
import json
from datetime import datetime
import os
import cdsco_live_fetcher

def get_record_count(path):
    if not os.path.exists(path): return 0
    if path.endswith('.parquet'):
        return len(pd.read_parquet(path))
    return 0

def run_full_update():
    """Runs live fetchers, calculates deltas, and saves them."""
    try:
        # Get old counts
        old_risk = get_record_count('cdsco_combined_risk.parquet')
        old_app = get_record_count('cdsco_approved_devices.parquet')

        updated_any = False

        # 1. Risk Devices
        risk_data = cdsco_live_fetcher.fetch_risk_device_list()
        records_r = risk_data.get('records', [])
        if not risk_data.get('error') and len(records_r) > 100:
            df_risk = pd.DataFrame(records_r)
            df_risk.to_parquet('cdsco_combined_risk.parquet', index=False)
            df_risk.to_excel('cdsco_combined_risk.xlsx', index=False)
            updated_any = True

        # 2. Approved Devices
        approved_data = cdsco_live_fetcher.fetch_all_approved_devices()
        records_a = approved_data.get('records', [])
        if not approved_data.get('error') and len(records_a) > 1000:
            df_app = pd.DataFrame(records_a)
            df_app.to_parquet('cdsco_approved_devices.parquet', index=False)
            df_app.to_excel('cdsco_approved_devices.xlsx', index=False)
            updated_any = True

        # Calculate deltas
        new_risk = get_record_count('cdsco_combined_risk.parquet')
        new_app = get_record_count('cdsco_approved_devices.parquet')

        metadata = {
            "last_updated": datetime.now().isoformat(),
            "risk_records": new_risk,
            "approved_records": new_app,
            "risk_delta": max(0, new_risk - old_risk),
            "approved_delta": max(0, new_app - old_app)
        }
        with open("cdsco_metadata.json", "w") as f:
            json.dump(metadata, f)

        return True, "Data updated successfully"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    success, msg = run_full_update()
    print(f"Update Result: {success}, Message: {msg}")
