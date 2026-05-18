#!/usr/bin/env python3
"""Repoint privacyPolicyUrl + supportUrl + marketingUrl on EVERY localization of
every app currently using legal-site (Maze Glass, Bloom, Wakewise) from the
Vercel host to the new Hetzner/Coolify host."""
import jwt, time, requests

KEY_ID = "5M266KQ46M"
ISSUER = "0f329102-99f5-4d60-9da0-f2b86441abf8"
KEY_PATH = "/Users/taoufikjabbari/.appstoreconnect/private_keys/AuthKey_5M266KQ46M.p8"

OLD_HOST = "https://legal-site-iota-smoky.vercel.app"
NEW_HOST = "https://legal.62-238-17-135.sslip.io"

APPS = [
    ("6769779804", "maze-glass", "Maze Glass"),
    ("6768495662", "bloom",      "Bloom"),
    ("6769271030", "wakewise",   "WakeWise"),
]

def token():
    key = open(KEY_PATH).read()
    now = int(time.time())
    return jwt.encode({"iss": ISSUER, "iat": now, "exp": now + 1200,
                       "aud": "appstoreconnect-v1"},
                      key, algorithm="ES256",
                      headers={"kid": KEY_ID, "typ": "JWT"})

def H():
    return {"Authorization": f"Bearer {token()}", "Content-Type": "application/json"}

API = "https://api.appstoreconnect.apple.com"

def get(p, **params):
    return requests.get(f"{API}{p}", headers=H(), params=params or None).json()

def patch(p, body):
    r = requests.patch(f"{API}{p}", headers=H(), json=body)
    if r.status_code >= 400:
        print(f"    PATCH {p} → {r.status_code} {r.text[:300]}")
    return r

def repoint(s):
    if not s: return s
    return s.replace(OLD_HOST, NEW_HOST)

for app_id, slug, name in APPS:
    print(f"\n=== {name} ({app_id}) ===")
    # 1) app-level: appInfoLocalizations.privacyPolicyUrl
    app_infos = get(f"/v1/apps/{app_id}/appInfos")["data"]
    for ai in app_infos:
        AI_ID = ai["id"]
        locs = get(f"/v1/appInfos/{AI_ID}/appInfoLocalizations")["data"]
        for loc in locs:
            attrs = loc["attributes"]
            new_url = repoint(attrs.get("privacyPolicyUrl"))
            if new_url and new_url != attrs.get("privacyPolicyUrl"):
                patch(f"/v1/appInfoLocalizations/{loc['id']}", {
                    "data": {"type": "appInfoLocalizations", "id": loc["id"],
                             "attributes": {"privacyPolicyUrl": new_url}}
                })
                print(f"  privacyPolicyUrl  {attrs['locale']:>6} → {new_url}")

    # 2) version-level: appStoreVersionLocalizations.{supportUrl,marketingUrl}
    versions = get(f"/v1/apps/{app_id}/appStoreVersions")["data"]
    for v in versions:
        VID = v["id"]
        state = v["attributes"]["appStoreState"]
        # Skip versions that are no longer editable
        if state in ("READY_FOR_SALE", "REPLACED_WITH_NEW_VERSION", "REMOVED_FROM_SALE",
                     "DEVELOPER_REMOVED_FROM_SALE", "REJECTED"):
            continue
        locs = get(f"/v1/appStoreVersions/{VID}/appStoreVersionLocalizations")["data"]
        for loc in locs:
            attrs = loc["attributes"]
            new = {}
            for k in ("supportUrl", "marketingUrl"):
                if attrs.get(k):
                    new_url = repoint(attrs[k])
                    if new_url != attrs[k]:
                        new[k] = new_url
            if new:
                patch(f"/v1/appStoreVersionLocalizations/{loc['id']}", {
                    "data": {"type": "appStoreVersionLocalizations", "id": loc["id"],
                             "attributes": new}
                })
                print(f"  v{v['attributes']['versionString']} {attrs['locale']:>6} → {list(new.keys())}")

print("\nDone.")
