import pandas as pd
import glob

class HEEDB:
    def __init__(self, data_name: str, data_root_path: str):
        self.data_name = data_name
        self.data_root_path = data_root_path
        # diagnoses_dictionary.csv in I0001 and I0006 are identical when only comparing codes and diagnoses columns
        diagnoses_dic = pd.read_csv(f"{self.data_root_path}/I0006/12SL_diagnoses/diagnoses_dictionary.csv")
        # diagnoses_v241 = pd.read_csv(f"{self.groups[0]}/12SL_diagnoses/diagnoses_v24.csv")
        # print(diagnoses_v241.head())
        # diagnoses_v242 = pd.read_csv(f"{self.groups[1]}/12SL_diagnoses/diagnoses_v24.csv")
        # print(diagnoses_v242.head())

    def prepare_df(self,):
        groups = sorted(glob.glob(f"{self.data_root_path}/I*"))
        for group in groups:
            metadata = pd.read_csv(f"{group}/metadata/metadata.csv")
            print(metadata.head())
            print(metadata.columns)
            print(len(metadata))
            diagnoses_v24 = pd.read_csv(f"{group}/12SL_diagnoses/diagnoses_v24.csv")
            print(diagnoses_v24.head())
            print(diagnoses_v24.columns)
            print(len(diagnoses_v24))
            diagnoses_acquisition = pd.read_csv(f"{group}/12SL_diagnoses/diagnoses_acquisition.csv")
            print(diagnoses_acquisition.head())
            print(diagnoses_acquisition.columns)
            print(len(diagnoses_acquisition))


'''
ecg-data) bash-4.4$ bash scripts/prepare_base.sh 
{'seed': 0, 'developement': False, 'toy_dataset_fraction': None, 'data_name': 'heedb', 'data_root_path': '/p01/whan/data/HEED'}
<class 'dict'>
<ecg_data.preprocess.ecg_datasets.base_datasets.base.BaseDataset objectat 0x7f639f773b50>
/p01/whan/ECG-Data/src/ecg_data/preprocess/ecg_datasets/base_datasets/heedb/heedb.py:18: DtypeWarning: Columns (11: PrimaryCauseOfDeathUNOS, 12: FirstContributoryCauseOfDeathDSC, 13: FirstContributoryCauseOfDeathUNOS, 14: SecondContributoryCauseOfDeathDSC, 15: SecondContributoryCauseOfDeathUNOS) have mixed types. Specify dtype option on import or set low_memory=False.
  metadata = pd.read_csv(f"{group}/metadata/metadata.csv")
   BDSPPatientID  ... AgeAtLastVisit
0      114877230  ...         5230.0
1      114877230  ...         5230.0
2      112062478  ...        21570.0
3      112062478  ...        21570.0
4      112062478  ...        21570.0

[5 rows x 28 columns]
Index(['BDSPPatientID', 'FileName', 'FileID', 'PatientRace', 'EthnicGroupDSC',
       'MaritalStatusDSC', 'ReligionDSC', 'LanguageDSC', 'VeteranStatusDSC',
       'SexDSC', 'PrimaryCauseOfDeathDSC', 'PrimaryCauseOfDeathUNOS',
       'FirstContributoryCauseOfDeathDSC', 'FirstContributoryCauseOfDeathUNOS',
       'SecondContributoryCauseOfDeathDSC',
       'SecondContributoryCauseOfDeathUNOS', 'EducationLevelDSC',
       'GenderIdentityDSC', 'SexAssignedAtBirthDSC', 'DateOfDeath',
       'DateOfDeathMARegistryData', 'LastKnownVisitDate', 'ECGAcquisitionTime',
       'DateOfBirth', 'AgeAtAcquisition', 'AgeAtDeath', 'AgeAtDeathMA',
       'AgeAtLastVisit'],
      dtype='str')
10608417
                                            FileName        codes
0  ./S0001/1988/04/de_111188448_19900713093800_19...  299, 390, 410, 1100, 1161, 1699
1  ./S0001/1988/04/de_111188448_19900714101100_19...        299, 390, 410, 1160, 1699
2  ./S0001/1988/04/de_111188448_19900715113400_19...        299, 390, 410, 1161, 1699
3  ./S0001/1988/04/de_111188448_19900720101200_19...    19, 177, 244, 410, 1145, 1699
4  ./S0001/1988/04/de_111188853_19840308103300_19...   1673, 22, 380, 411, 1140, 1699
Index(['FileName', 'codes'], dtype='str')
10471531
                                            FileName  ... jaccard_index
0  /S0004/2019/02/de_120072567_19810310175300_198...  ...      0.000000
1  /S0004/2019/02/de_118349698_19801127112700_198...  ...      0.400000
2  /S0004/2019/02/de_119754081_19820302181400_198...  ...      0.000000
3  /S0004/2019/02/de_119823124_19811103164400_198...  ...      0.076923
4  /S0004/2019/02/de_117001538_19810103150000_198...  ...      0.076923

[5 rows x 4 columns]
Index(['FileName', 'codes_software', 'codes_physician', 'jaccard_index'], dtype='str')
10608415
/p01/whan/ECG-Data/src/ecg_data/preprocess/ecg_datasets/base_datasets/heedb/heedb.py:18: DtypeWarning: Columns (7: LastKnownVisitDate, 8: DateOfDeath) have mixed types. Specify dtype option on import or set low_memory=False.
  metadata = pd.read_csv(f"{group}/metadata/metadata.csv")
   BDSPPatientID  ... AgeAtDeath
0    179020000.0  ...        NaN
1    179020000.0  ...        NaN
2    179020000.0  ...        NaN
3    179020000.0  ...        NaN
4    179020001.0  ...        NaN

[5 rows x 12 columns]
Index(['BDSPPatientID', 'FileName', 'FileID', 'PatientRace', 'Sex',
       'ECGAcquisitionTime', 'DateOfBirth', 'LastKnownVisitDate',
       'DateOfDeath', 'AgeAtAcquisition', 'AgeAtLastVisit', 'AgeAtDeath'],
      dtype='str')
998844
                               FileName                                codes
0  WFDB/2010/MUSE_20191206_105123_71000  22, 1680, 360, 780, 831, 1160,1699
1  WFDB/2010/MUSE_20191205_131333_61000                             22,1684
2  WFDB/2010/MUSE_20191205_115836_94000                             22,1684
3  WFDB/2010/MUSE_20191204_110019_91000        23, 410, 1682, 740, 831,1699
4  WFDB/2010/MUSE_20191205_143457_94000                             22,1684
Index(['FileName', 'codes'], dtype='str')
974172
                               FileName  ... jaccard_index
0  WFDB/2010/MUSE_20191206_094318_74000  ...      0.800000
1  WFDB/2010/MUSE_20191204_094318_64000  ...      1.000000
2  WFDB/2010/MUSE_20191204_094454_98000  ...      0.666667
3  WFDB/2010/MUSE_20191204_095454_18000  ...      1.000000
4  WFDB/2010/MUSE_20191204_101029_19000  ...      0.333333

[5 rows x 4 columns]
Index(['FileName', 'codes_software', 'codes_physician', 'jaccard_index'], dtype='str')
998844
'''