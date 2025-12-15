from core.d2o_reader import D2OReader
import os

d2o_path = "dofus_data/common/Items.d2o"
if os.path.exists(d2o_path):
    reader = D2OReader(d2o_path)
    details = reader.get_details(22417)
    print(f"Details for 22417: {details}")
else:
    print("Items.d2o not found")
