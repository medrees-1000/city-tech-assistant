"""Test: can we read the City Tech catalog API without logging in?

Run:  python test_catalog_api.py
Needs only Python 3.9+ (standard library). Makes 2 requests.
"""
import json
import urllib.request

UA = "CityTechAssistantBot/0.1 (student portfolio project; contact: YOUR_EMAIL_HERE)"
BASE = "https://app.coursedog.com/api/v1"
CATALOG_ID = "qPpQUgUy149umoKU2soi"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://citytech.catalog.cuny.edu",
    "Referer": "https://citytech.catalog.cuny.edu/",
    "x-requested-with": "catalog",
    "User-Agent": UA,
}

# Same body the catalog website sends (copied from DevTools).
BODY = {
    "condition": "AND",
    "filters": [
        {
            "id": "K87u6eND",
            "condition": "and",
            "filters": [
                {"id": "status-course", "condition": "field", "name": "status",
                 "inputType": "select", "group": "course", "type": "is",
                 "value": "Active", "customField": False},
                {"id": "catalogPrint-course", "condition": "field", "name": "catalogPrint",
                 "inputType": "boolean", "group": "course", "type": "is",
                 "value": True, "customField": False},
            ],
        }
    ],
}

COLUMNS = "code,name,description,departments,requirementGroup,credits,status"


def call(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS,
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


# Test 1: list 5 courses
url = (f"{BASE}/cm/nyt01/courses/search/%24filters?catalogId={CATALOG_ID}"
       f"&skip=0&limit=5&orderBy=code&columns={COLUMNS}"
       "&effectiveDatesRange=2026-08-28%2C2026-08-28&ignoreEffectiveDating=false")
result = call(url, BODY)
print("Total courses:", result.get("listLength"))
for c in result["data"]:
    depts = [d["id"] for d in c.get("departments", [])]
    print(" ", c["code"], "|", c["name"], "|", depts, "| rule:", c.get("requirementGroup"))

# Test 2: look up one prerequisite rule
rule_id = result["data"][0].get("requirementGroup")
if rule_id:
    rule = call(f"{BASE}/nyt01/requirementGroups/{rule_id}?returnFields=code,descriptionLong")
    print("Rule", rule_id, "->", rule["data"][rule_id]["descriptionLong"])