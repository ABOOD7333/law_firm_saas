import inspect
import sys
sys.path.append('.')
from database.models import LawCases, LawClients, LawHearings, LawTasks

for model in [LawCases, LawClients, LawHearings, LawTasks]:
    print(f"=== {model.__name__} ===")
    for attr, val in inspect.getmembers(model):
        if not attr.startswith('_') and not callable(val):
            print(f"  {attr}: {val}")
