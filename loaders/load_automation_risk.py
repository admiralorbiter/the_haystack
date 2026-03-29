import os
import sys
import pandas as pd

# Ensure we can import app and models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from models import db, Occupation

def run():
    csv_path = os.path.join("data", "raw", "automation", "automation_data_by_state.csv")
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    print("Reading Frey & Osborne Automation Risk data...")
    # Use latin1 due to special characters in state/city names
    df = pd.read_csv(csv_path, encoding='latin1')
    
    # We only care about the national probability for the SOC
    df = df[['SOC', 'Probability']].dropna(subset=['SOC', 'Probability'])
    df['SOC'] = df['SOC'].astype(str).str.strip()
    
    risk_dict = dict(zip(df['SOC'], df['Probability']))

    app = create_app()
    with app.app_context():
        print("Updating occupations with automation risk...")
        
        matched = 0
        missing = 0
        occs = Occupation.query.all()
        for occ in occs:
            if occ.soc in risk_dict:
                occ.automation_risk = float(risk_dict[occ.soc])
                matched += 1
            else:
                occ.automation_risk = None
                missing += 1
                
        db.session.commit()
        print(f"Matched automation risk for {matched} occupations. ({missing} without data).")

if __name__ == "__main__":
    run()
