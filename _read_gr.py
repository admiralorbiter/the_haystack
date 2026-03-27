import pandas as pd
df = pd.read_excel('data/raw/ipeds/2024/gr2024.xlsx', sheet_name='Frequencies')
grtypes = df[df['varname'] == 'GRTYPE'][['codevalue', 'valuelabel']]
for _, row in grtypes.iterrows():
    print(f"{row['codevalue']}: {row['valuelabel']}")
