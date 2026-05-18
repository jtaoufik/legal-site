#!/usr/bin/env python3
"""Bloom metadata-only update: create v1.28, repoint privacy/support URLs to
Hetzner, attach the existing latest build, submit for review."""
import jwt, time, requests, sys, json

KEY_ID = "5M266KQ46M"
ISSUER = "0f329102-99f5-4d60-9da0-f2b86441abf8"
KEY_PATH = "/Users/taoufikjabbari/.appstoreconnect/private_keys/AuthKey_5M266KQ46M.p8"
APP_ID = "6768495662"
NEW_VERSION = "1.28"

OLD_HOST = "https://legal-site-iota-smoky.vercel.app"
NEW_HOST = "https://legal.62-238-17-135.sslip.io"

def token():
    key = open(KEY_PATH).read()
    now = int(time.time())
    return jwt.encode({"iss": ISSUER, "iat": now, "exp": now + 1200,
                       "aud": "appstoreconnect-v1"},
                      key, algorithm="ES256", headers={"kid": KEY_ID, "typ": "JWT"})

def H():
    return {"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}

API = "https://api.appstoreconnect.apple.com"

def get(p, **params):
    return requests.get(f"{API}{p}", headers=H(), params=params or None).json()

def post(p, body):
    r = requests.post(f"{API}{p}", headers=H(), json=body)
    if r.status_code >= 400: print(f"POST {p} → {r.status_code} {r.text[:500]}")
    return r

def patch(p, body):
    r = requests.patch(f"{API}{p}", headers=H(), json=body)
    if r.status_code >= 400: print(f"PATCH {p} → {r.status_code} {r.text[:500]}")
    return r

def repoint(s):
    return s.replace(OLD_HOST, NEW_HOST) if s else s

# 0. find the most recent live version to copy its content from
versions = get(f"/v1/apps/{APP_ID}/appStoreVersions", **{"limit": 5})["data"]
live = next((v for v in versions if v["attributes"]["appStoreState"] == "READY_FOR_SALE"), None)
print(f"latest live: v{live['attributes']['versionString']}")

# check if 1.28 already exists (re-run safety)
existing = next((v for v in versions if v["attributes"]["versionString"] == NEW_VERSION), None)
if existing:
    NEW_VID = existing["id"]
    print(f"v{NEW_VERSION} already exists ({NEW_VID}) — reusing  state={existing['attributes']['appStoreState']}")
else:
    # 1. create the new metadata-only version
    r = post("/v1/appStoreVersions", {
        "data": {"type": "appStoreVersions",
                 "attributes": {"platform": "IOS",
                                "versionString": NEW_VERSION,
                                "releaseType": "AFTER_APPROVAL",
                                "copyright": "© 2026 Taoufik Jabbari"},
                 "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}
    })
    if r.status_code >= 400: sys.exit(1)
    NEW_VID = r.json()["data"]["id"]
    print(f"created v{NEW_VERSION} = {NEW_VID}")

# 2. attach the latest VALID build
builds = get("/v1/builds", **{"filter[app]": APP_ID, "sort": "-uploadedDate", "limit": 5})["data"]
latest = next((b for b in builds if b["attributes"]["processingState"] == "VALID"), None)
if latest:
    BID = latest["id"]
    print(f"attaching build {latest['attributes']['version']}  ({BID})")
    patch(f"/v1/appStoreVersions/{NEW_VID}/relationships/build", {
        "data": {"type": "builds", "id": BID}
    })

# 3. patch every appStoreVersionLocalization on the new version with the new URLs
#    (Apple auto-copies the previous live version's locs over when a new version is created)
new_vlocs = get(f"/v1/appStoreVersions/{NEW_VID}/appStoreVersionLocalizations")["data"]
print(f"\nfound {len(new_vlocs)} version localizations on v{NEW_VERSION}")
for l in new_vlocs:
    a = l["attributes"]
    new = {}
    for k in ("supportUrl", "marketingUrl"):
        cur = a.get(k)
        if cur:
            updated = repoint(cur)
            if updated != cur:
                new[k] = updated
    # Also bump whatsNew so Apple shows something to reviewers — required for new versions.
    new["whatsNew"] = "Bug fixes and privacy URL update." if a["locale"] == "en-US" else \
                      "Corrections de bugs et mise à jour de l'URL de confidentialité." if a["locale"] == "fr-FR" else \
                      "バグ修正とプライバシーURLの更新。" if a["locale"] == "ja" else \
                      "Correcciones y actualización de la URL de privacidad." if a["locale"] == "es-ES" else \
                      "Correções e atualização da URL de privacidade." if a["locale"] == "pt-BR" else \
                      "更新"
    patch(f"/v1/appStoreVersionLocalizations/{l['id']}", {
        "data": {"type": "appStoreVersionLocalizations", "id": l["id"], "attributes": new}
    })
    print(f"  versionLoc {a['locale']:>8}: {list(new.keys())}")

# 4. app-level privacyPolicyUrl — find the appInfo associated with this new version
app_infos = get(f"/v1/apps/{APP_ID}/appInfos")["data"]
ed = next((a for a in app_infos if a["attributes"].get("appStoreState") in
           ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED",
            "WAITING_FOR_REVIEW", "READY_FOR_REVIEW")), None)
if ed:
    AI_ID = ed["id"]
    print(f"\neditable appInfo: {AI_ID}  state={ed['attributes']['appStoreState']}")
    inf_locs = get(f"/v1/appInfos/{AI_ID}/appInfoLocalizations")["data"]
    for l in inf_locs:
        a = l["attributes"]
        cur = a.get("privacyPolicyUrl")
        if cur:
            updated = repoint(cur)
            if updated != cur:
                patch(f"/v1/appInfoLocalizations/{l['id']}", {
                    "data": {"type": "appInfoLocalizations", "id": l["id"],
                             "attributes": {"privacyPolicyUrl": updated}}
                })
                print(f"  privacyPolicyUrl {a['locale']:>8} → {updated}")

# 5. submit for review (reuse existing reviewSubmissions if any in READY/WAITING)
subs = get("/v1/reviewSubmissions", **{"filter[app]": APP_ID, "limit": 10})["data"]
SUB_ID = None
for s in subs:
    if s["attributes"]["state"] in ("READY_FOR_REVIEW", "WAITING_FOR_REVIEW"):
        SUB_ID = s["id"]; break
if not SUB_ID:
    r = post("/v1/reviewSubmissions", {
        "data": {"type": "reviewSubmissions", "attributes": {"platform": "IOS"},
                 "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}
    })
    if r.status_code >= 400: sys.exit(2)
    SUB_ID = r.json()["data"]["id"]
print(f"\nreviewSubmission: {SUB_ID}")

# attach the version to the submission
existing_items = get(f"/v1/reviewSubmissions/{SUB_ID}/items")["data"]
if not any(i["relationships"]["appStoreVersion"]["data"]["id"] == NEW_VID for i in existing_items):
    r = post("/v1/reviewSubmissionItems", {
        "data": {"type": "reviewSubmissionItems",
                 "relationships": {
                     "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": SUB_ID}},
                     "appStoreVersion":  {"data": {"type": "appStoreVersions", "id": NEW_VID}}}}
    })
    if r.status_code >= 400:
        print(f"attach: {r.status_code}  {r.text[:400]}")

# submit
r = patch(f"/v1/reviewSubmissions/{SUB_ID}", {
    "data": {"type": "reviewSubmissions", "id": SUB_ID, "attributes": {"submitted": True}}
})
print(f"submit: {r.status_code}")
final = get(f"/v1/reviewSubmissions/{SUB_ID}")
print(f">>> State: {final['data']['attributes']['state']}  submitted={final['data']['attributes'].get('submittedDate')}")
