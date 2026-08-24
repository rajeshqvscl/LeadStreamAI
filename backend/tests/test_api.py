import requests

def test():
    # Use user_id = 2 as seen from the previous row test
    headers = {"X-User-Id": "1"} # Let's try 1 then 2 if 1 has nothing
    
    for uid in ["1", "2", None]:
        if uid:
            h = {"X-User-Id": uid}
        else:
            h = {}
        res = requests.get("http://127.0.0.1:8000/api/leads", params={
            "page": 1,
            "per_page": 1000,
            "source": "bulk",
            "exclude_drafted": "true"
        }, headers=h)
        print(f"UID {uid} bulk count:", len(res.json().get("leads", [])) if res.status_code == 200 else res.text)
        
    res2 = requests.get("http://127.0.0.1:8000/api/leads", params={
        "page": 1,
        "per_page": 1000,
        "source": "bulk"
    }, headers={"X-User-Id": "2"})
    print("UID 2 no exclude_drafted count:", len(res2.json().get("leads", [])) if res2.status_code == 200 else res2.text)

if __name__ == '__main__':
    test()
