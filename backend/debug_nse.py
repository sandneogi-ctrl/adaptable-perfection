from nsepython import nse_get_index_quote
import json

result = nse_get_index_quote("NIFTY 50")
print("Type:", type(result))
if isinstance(result, dict):
    print("Keys:", list(result.keys()))
    # Print first item of any list values
    for k, v in result.items():
        if isinstance(v, list) and len(v) > 0:
            print(f"\n{k}[0]:", json.dumps(v[0], indent=2))
            break
        else:
            print(f"{k}:", v)
elif isinstance(result, list):
    print("List length:", len(result))
    print("First item:", json.dumps(result[0], indent=2))
else:
    print("Value:", result)
