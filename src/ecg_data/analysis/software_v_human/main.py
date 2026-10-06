import json
import numpy as np
from pathlib import Path
from ecg_data.preprocess.config.load import get_config

def read_reports(data_path, data_name):
    if data_name == "agh":
        for path in sorted(Path(data_path).glob("*.json")):
            for instance in json.loads(path.read_text()):
                yield (
                    "agh",
                    instance.get("OriginalDiagnosis"),
                    instance.get("Diagnosis"),
                )
        return

    if data_name == "heedb":
        for path in sorted(Path(data_path).glob("*/*.npy")):
            instance = np.load(path, allow_pickle=True).item()
            physician = instance.get("reports_physician")
            yield "heedb_old", instance.get("reports_software_old"), physician
            yield "heedb_new", instance.get("reports_software_new"), physician
        return

    raise ValueError(f"Unknown dataset: {data_name}")

if __name__ == "__main__":
    cfg = get_config()
    for source, software_report, physician_report in read_reports(cfg["data_path"],
                                                                  cfg["data_name"]):
        print(source)
        print(software_report)
        print(physician_report)
        input()

'''
(ecg-data) bash-4.4$ bash scripts/software_v_human.sh 
agh
['Normal sinus rhythm', 'Inferior infarct', ', age undetermined', 'Abnormal ECG', 'No previous ECGs available']
['Normal sinus rhythm', 'INFERO-APICAL INFARCT', ', age undetermined', 'Abnormal ECG', 'No previous ECGs available']

heedb_old
['atrial fibrillation', 'with rapid ventricular response', 'with premature ventricular or aberrantly conducted complexes', 'with qrs widening', 'marked st abnormality, possible anterolateral subendocardial injury', 'marked st abnormality, possible inferolateral subendocardial injury', 'marked st abnormality, possible anteroseptal subendocardial injury', 'marked st abnormality, possible anterior subendocardial injury', 'marked st abnormality, possible inferior subendocardial injury', 'marked st abnormality, possible lateral subendocardial injury', 'marked st abnormality, possible septal subendocardial injury', 'st &', 'possible', 'abnormal ecg', 'when compared with ecg of', '.', 'has replaced', 'sinus rhythm', 'has increased', 'st more depressed in', 'lateral leads']
['manual comparison required for analog tracing', 'atrial fibrillation', 'with rapid ventricular response', 'left axis deviation', 'st &', 'nonspecific st and t wave abnormality', 'nonspecific st abnormality', 'left ventricular hypertrophy', 'with', 'when compared with ecg of', '.', 'deep q wave in lead v6,', 'in lead', 'in leads', 'low heart rate, verify av conduction', 'has increased']

heedb_new
['*** poor data quality, interpretation may be adversely affected', 'undetermined rhythm', 'left axis deviation', 'left ventricular hypertrophy', 'with qrs widening and repolarization abnormality', '(', 'r in avl', ',', 'sokolow-lyon', 'cornell product', ')', 'abnormal ecg']
['manual comparison required for analog tracing', 'atrial fibrillation', 'with rapid ventricular response', 'left axis deviation', 'st &', 'nonspecific st and t wave abnormality', 'nonspecific st abnormality', 'left ventricular hypertrophy', 'with', 'when compared with ecg of', '.', 'deep q wave in lead v6,', 'in lead', 'in leads', 'low heart rate, verify av conduction', 'has increased']
'''