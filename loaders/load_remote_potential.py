import os
import sys
import pandas as pd

# Ensure we can import app and models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from models import db, Occupation

def run():
    csv_path = os.path.join("data", "raw", "telework", "occupations_workathome.csv")
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print("Reading Dingel & Neiman Remote Work Potential data...")
    df = pd.read_csv(csv_path)
    
    # Clean the O*NET SOC code (e.g. '11-1011.00' -> '11-1011')
    df['soc'] = df['onetsoccode'].astype(str).str.strip().str[:7]
    
    # Keep the max true if multiple O*NET SOCs collapse into one SOC
    tele_dict = df.groupby('soc')['teleworkable'].max().to_dict()

    app = create_app()
    with app.app_context():
        print("Updating occupations with remote work potential...")
        
        matched = 0
        missing = 0
        occs = Occupation.query.all()
        for occ in occs:
            if occ.soc in tele_dict:
                occ.remote_capable = bool(tele_dict[occ.soc] == 1)
                matched += 1
            else:
                occ.remote_capable = None
                missing += 1
                
        db.session.commit()
        print(f"Matched remote-work potential for {matched} occupations. ({missing} without data).")

if __name__ == "__main__":
    run()
