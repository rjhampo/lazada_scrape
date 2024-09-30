import random, os, dotenv, json, time, logging, urllib.parse as urlparse, playwright.sync_api as psa, playwright_stealth as stealth
from curl_cffi import requests
from requests import HTTPError


# Steps
# 1. create loop to get x number links to products (goal: 1000)
# 2. create loop to scrape every product
#       a. identify details to obtain
# 3. store in file db
#       a. identify schema

DELAY_MEAN = 1
DELAY_SD = 0.5
ITEM_SEARCH = 'cleanser'
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')

logger = logging.getLogger(__name__)
logging.basicConfig()
logger.setLevel(logging.DEBUG)
dotenv.load_dotenv()
with open('user_agents.json', 'r') as agents:
    agents_list = json.loads(agents.read())
with open(os.getenv('PROXY'), 'r') as input:
    PROXIES = [proxy.strip() for proxy in input]


def random_delay():
    if random.random() > 0.5:
        time.sleep(abs(random.gauss(DELAY_MEAN, DELAY_SD)) * random.uniform(0.5,1.5))
    else:
        time.sleep(abs(random.gauss(DELAY_MEAN, DELAY_SD)) + random.random())

def rotate_header():
    user_agent = random.choice(agents_list)
    logger.debug(f'Getting new header with agent {user_agent}')
    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept": "application/json, text/plain, */*",
        "Host": "www.lazada.com.ph",
        "Referer": "https://www.lazada.com.ph/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Priority": "u=0, i",
        "TE": "trailers"
    }

def get_proxy_endpoint():
    yield from PROXIES

def get_cookies(url: str, proxy: str, user: str, passw: str):
    logger.debug(f'Getting cookies from {url} through proxy {proxy}')
    with psa.sync_playwright() as p:
        browser = p.chromium.launch(proxy={'server': proxy, 'username': user, 'password': passw}, headless=False)
        context = browser.new_context()
        page = context.new_page()
        stealth.stealth_sync(page)
        page.goto(url)
        cookies = context.cookies()
        context.close()
    cookiejar = {}
    for cookie in cookies:
        cookiejar[cookie['name']] = str(cookie['value'])
    return cookiejar

# https://www.lazada.com.ph/tag/cream-of-tartar/?q=cream%20of%20tartar&catalog_redirect_tag=true
# .ant-pagination-next
# recaptchav2
# nomorepages

req_url = 'https://www.lazada.com.ph/catalog/?page=1&q=cleanser'
req_url2 = 'https://www.lazada.com.ph/catalog/?ajax=true&page=1&q=cleanser'
headers = rotate_header()
proxy = next(get_proxy_endpoint())



# proxy_settings of form {proxy_url: <str>, proxy_user: <str>, proxy_passw: <str>}
def run_scraper(item: str, proxy_settings: dict, pagination: int | None = 1) -> None:
    if item.find(' ') > -1:
        tag_search = item.replace(' ', '-')
        query_search = item.replace(' ', '%20')
    else:
        tag_search = item
        query_search = item
    
    front_url = f'https://www.lazada.com.ph/tag/{tag_search}/?q={query_search}&page={pagination}'
    api_url = front_url + '&ajax=true'
    noMorePages = False
    newCookies = False
    newSession = False

    while not noMorePages:
        if not newCookies:
            cookie_jar = get_cookies(front_url, proxy_settings.get('proxy_url'), proxy_settings.get('proxy_user'), proxy_settings.get('proxy_passw'))
            headers = rotate_header()
            logger.debug(f'Obtained new cookies and new header = {headers}')
        if not newSession:
            curr_session = requests.Session()
            logger.debug(f'Obtained new session')
        
        curr_session.cookies.update(cookie_jar)
        curr_session.proxies = {'https': proxy_settings.get('proxy_url')}
        curr_session.headers = headers
        try:
            response = curr_session.request('GET', api_url, impersonate='chrome')
            response.raise_for_status()
        except HTTPError:
            pass

        # If timeout then new proxy