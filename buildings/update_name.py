import glob
import os

weather_mapping = {'USA_MD_Baltimore-Washington.Intl.AP.724060': "4A",
                   'USA_IL_Chicago-OHare.Intl.AP.725300': "5A",
                   'USA_MT_Helena.Rgnl.AP.727720': "6B",
                   'USA_ID_Boise.Air.Terminal.726810': "5B",
                   'USA_AZ_Phoenix-Sky.Harbor.Intl.AP.722780': "2B",
                   'USA_FL_Miami.Intl.AP.722020': "1A",
                   'USA_TX_Houston-Bush.Intercontinental.AP.722430': "2A",
                   'USA_NM_Albuquerque.Intl.AP.723650': "4B",
                   'USA_VT_Burlington.Intl.AP.726170': "6A",
                   'USA_TX_El.Paso.Intl.AP.722700': "3B",
                   'USA_CA_San.Francisco.Intl.AP.724940': "3C",
                   'USA_HI_Honolulu.Intl.AP.911820': "1",
                   'USA_AK_Fairbanks.Intl.AP.702610': "8",
                   'USA_MN_Duluth.Intl.AP.727450': "7",
                   'USA_TN_Memphis.Intl.AP.723340': "3A",
                   'USA_OR_Salem-McNary.Field.726940': "4C"}
heat_mapping = {'gasfurnace': "gas",
                'elecres': "electric",
                'hp': "pump",
                'oilfurnace': "oil"}

base_mapping = {'unheatedbsmt': "unheated",
                'heatedbsmt': "heated",
                'slab': "slab",
                'crawlspace': "crawlspace"}

checker = set()
count = 0

for name in glob.glob("./*.idf"):
    name_part = name[2:].split('+')
    new_name = list()
    new_name.append({"SF": "single", "MF": "multi"}[name_part[0]])
    new_name.append(name_part[1][2:4])
    # new_name.append(weather_mapping[name_part[2]])
    new_name.append(heat_mapping[name_part[3]])
    new_name.append(base_mapping[name_part[4]])
    os.rename(name, f"./{'_'.join(new_name)}.idf")

    # if new_name[1] != new_name[2]:
    #     count += 1
    #     print(entry)
    #     print(new_name)

print(count)
