import csv
from pathlib import Path

def export_metrics_csv(rows, path):
    path=Path(path)
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['metric','value']); w.writeheader(); w.writerows(rows)
    return str(path)
