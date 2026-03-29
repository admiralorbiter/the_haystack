import os
import sys
import pandas as pd

# Ensure we can import app and models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from models import db, Occupation

def run():
    csv_path = os.path.join("data", "raw", "bright_outlook", "All_Bright_Outlook_Occupations.csv")
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print("Reading O*NET Bright Outlook data...")
    df = pd.read_csv(csv_path)
    
    # Clean the O*NET SOC code (e.g. '13-2011.00' -> '13-2011')
    df['soc'] = df['Code'].astype(str).str.strip().str[:7]
    bright_socs = set(df['soc'].unique())

    app = create_app()
    with app.app_context():
        print("Updating occupations with Bright Outlook status...")
        
        # First reset all to False to ensure idempotency
        db.session.query(Occupation).update({"bright_outlook": False})
        
        # Then update the flagged ones
        matched = 0
        occs = Occupation.query.all()
        for occ in occs:
            if occ.soc in bright_socs:
                occ.bright_outlook = True
                matched += 1
                
        db.session.commit()
        print(f"Flagged {matched} occupations with Bright Outlook status.")

if __name__ == "__main__":
    run()
