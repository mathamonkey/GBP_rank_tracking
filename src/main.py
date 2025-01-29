from appwrite.client import Client
from appwrite.services.users import Users
from appwrite.exception import AppwriteException
import os
import json
import requests
import base64

def main(context):
    # -- Appwrite Setup (optional, remove if not needed) --
    client = (
        Client()
        .set_endpoint(os.environ["APPWRITE_FUNCTION_API_ENDPOINT"])
        .set_project(os.environ["APPWRITE_FUNCTION_PROJECT_ID"])
        .set_key(context.req.headers["x-appwrite-key"])
    )
    users = Users(client)
    try:
        response = users.list()
        context.log("Total users: " + str(response["total"]))
    except AppwriteException as err:
        context.error("Could not list users: " + repr(err))

    # 1) Parse JSON body for lat, lng, searchTerm
    try:
        body = json.loads(context.req.body)
    except:
        body = {}
    lat = body.get("lat", 12.8917)
    lng = body.get("lng", 77.5838)
    searchTerm = body.get("searchTerm", "dentists near me")

    # 2) Build the Google Maps URL
    #    e.g. https://www.google.com/maps/search/dentists%20near%20me/@12.8917,77.5838,14.00z/?brd_json=1
    from requests.utils import quote
    encodedSearchTerm = quote(searchTerm)
    url = f"https://www.google.com/maps/search/{encodedSearchTerm}/@{lat},{lng},14.00z/?brd_json=1"

    # 3) Bright Data proxy credentials
    proxy_host = "brd.superproxy.io"
    proxy_port = "33335"
    proxy_user = "brd-customer-hl_6bd3d4c8-zone-serp_api1"
    proxy_pass = "flo4tpqytqm5"

    # 4) Generate a UULE from lat/lng
    #    Common formula: "w+CAIQICI" + "{lat},{lng}" + ":ChI"
    #    Then Base64-url-safe encode it
    def generate_uule(lat, lng):
        raw_string = f"w+CAIQICI{lat},{lng}:ChI"
        encoded = base64.urlsafe_b64encode(raw_string.encode()).decode()
        return encoded

    uule_value = generate_uule(lat, lng)

    # 5) Configure the proxies
    proxies = {
        "http":  f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
        "https": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
    }

    # 6) Build headers, embedding the UULE in the cookie
    #    Also can add 'x-geo' or others if you want
    headers = {
        "accept-language": "en-US,en;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        # Insert the generated UULE in the cookie
        "cookie": f"CONSENT=YES+; UULE={uule_value}",
        # Optionally set x-geo if you want to replicate the original cURL
        "x-geo": f"{lat},{lng}"
    }

    # 7) Make the GET request with the proxy, ignoring SSL verification (-k)
    try:
        response = requests.get(url, proxies=proxies, headers=headers, verify=False)
    except Exception as e:
        return context.res.json(
            {"error": f"Request failed: {str(e)}"},
            status=500
        )

    # 8) Parse the returned JSON
    try:
        data = response.json()
    except:
        return context.res.json(
            {"error": "Response not valid JSON", "raw": response.text},
            status=500
        )

    # 9) Extract the 'title' from each item in data["organic"]
    names = []
    if "organic" in data and isinstance(data["organic"], list):
        for item in data["organic"]:
            if "title" in item:
                names.append(item["title"])

    # 10) Return the extracted names + some debug info
    return context.res.json({
        "lat": lat,
        "lng": lng,
        "searchTerm": searchTerm,
        "uuleUsed": uule_value,
        "count": len(names),
        "gbpTitles": names
    })
