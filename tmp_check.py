import zipfile
import csv
import sys
import io

def check_qcew():
    try:
        with zipfile.ZipFile('data/raw/qcew/2024_qtrly_by_area.zip') as z:
            jackson = [n for n in z.namelist() if '29095' in n][0]
            with z.open(jackson) as f:
                # Read first line as text
                text_content = io.TextIOWrapper(f, encoding='utf-8')
                reader = csv.reader(text_content)
                header = next(reader)
                print("COLUMNS:")
                for i, col in enumerate(header):
                    print(f"{i}: {col}")
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    check_qcew()
