from appwrite.client import Client
from appwrite.services.users import Users
from appwrite.exception import AppwriteException
import os
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

    # Because of your logs, we know context.req.body is already a dict
    raw_body = context.req.body

    lat = raw_body.get("lat")
    lng = raw_body.get("lng")
    searchTerm = raw_body.get("searchTerm")
    targetGbp = (raw_body.get("targetGbp") or "").strip()

    # Minimal change: added ?num=50 so it returns up to 50 results
    from requests.utils import quote
    encodedSearchTerm = quote(searchTerm)
    url = f"https://www.google.com/maps/search/{encodedSearchTerm}/@{lat},{lng},14.00z/?num=50&brd_json=1"

    # Bright Data proxy credentials
    proxy_host = "brd.superproxy.io"
    proxy_port = "33335"
    proxy_user = "brd-customer-hl_6bd3d4c8-zone-serp_api1"
    proxy_pass = "flo4tpqytqm5"

    # Generate UULE
    def generate_uule(lat, lng):
        raw_string = f"w+CAIQICI{lat},{lng}:ChI"
        encoded = base64.urlsafe_b64encode(raw_string.encode()).decode()
        return encoded

    uule_value = generate_uule(lat, lng)

    proxies = {
        "http":  f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}",
        "https": f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
    }

    headers = {
        "accept-language": "en-US,en;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "cookie": f"CONSENT=YES+; UULE={uule_value}",
        "x-geo": f"{lat},{lng}"
    }

    # Retry loop up to 5 times for potential proxy failure
    max_retries = 5
    response = None
    attempt = 0

    while attempt < max_retries:
        try:
            response = requests.get(url, proxies=proxies, headers=headers, verify=False)
            break  # If successful, exit the loop
        except Exception as e:
            attempt += 1
            if attempt == max_retries:
                # All 5 attempts failed
                context.log({
                    "error": f"Request failed after {max_retries} attempts: {str(e)}"
                })
                return context.res.json({
                    "error": f"Request failed after {max_retries} attempts: {str(e)}"
                })

    # If we reach here, response should be valid
    try:
        data = response.json()
    except:
        context.log({
            "error": "Response not valid JSON",
            "raw": response.text
        })
        return context.res.json({
            "error": "Response not valid JSON",
            "raw": response.text
        })

    # We now track total count of GBP listings
    total_count = 0
    found_rank = "Not in the list"

    if "organic" in data and isinstance(data["organic"], list):
        total_count = len(data["organic"])
        target_lower = targetGbp.lower()
        
        for item in data["organic"]:
            title = (item.get("title") or "").strip().lower()
            orig_title = (item.get("original_title") or "").strip().lower()
            if title == target_lower or orig_title == target_lower:
                if "rank" in item:
                    found_rank = item["rank"]
                else:
                    found_rank = "N/A"
                break

    context.log({
        "lat": lat,
        "lng": lng,
        "searchTerm": searchTerm,
        "targetGbp": targetGbp,
        "totalCount": total_count,
        "rank": found_rank
    })
    return context.res.json({
        "lat": lat,
        "lng": lng,
        "searchTerm": searchTerm,
        "targetGbp": targetGbp,
        "totalCount": total_count,
        "rank": found_rank
    })
