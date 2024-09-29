import random, os, dotenv, json, bs4, time, logging, playwright.sync_api as psa, playwright_stealth as stealth
from curl_cffi import requests


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

def get_cookies(url, proxy, user, passw):
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

# https://www.lazada.com.ph/catalog/?ajax=true&page=3&q=cleanser&spm=a2o4l.homepage.search.d_go
# .ant-pagination-next
# recaptchav2
# nomorepages

req_url = 'https://www.lazada.com.ph/catalog/?page=1&q=maple'
req_url2 = 'https://www.lazada.com.ph/catalog/?ajax=true&page=1&q=cleanser'
headers = rotate_header()
proxy = next(get_proxy_endpoint())


def run_scraper(url, **kwargs):
    pagination = kwargs.get('pagination', 1)
    


with requests.Session() as session:
    session.cookies.update(get_cookies(req_url, proxy, PROXY_USER, PROXY_PASS))
    session.proxies = {'https': proxy}
    session.headers = headers
    logger.debug(f'GET request with headers {session.headers}')
    response = session.request('GET', req_url2, impersonate='chrome')

    with open('testfile.txt', 'w') as out:
        out.write(json.dumps(response.json()))

# If timeout then new proxy