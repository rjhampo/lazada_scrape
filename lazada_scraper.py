import random, os, dotenv, json, time, logging, warnings, playwright.sync_api as psa, playwright_stealth as stealth
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
DEFAULT_TIMEOUT = 60000
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')

warnings.filterwarnings('ignore', r'Make sure*', RuntimeWarning, module='curl_cffi')
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
        "Connection": "keep-alive",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept": "application/json, text/plain, */*",
        "Host": "www.lazada.com.ph",
        "Referer": "https://www.lazada.com.ph/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers"
    }

def get_proxy_endpoint():
    yield from PROXIES

def get_cookies_headers(url: str, proxy: str, user: str, passw: str) -> list:
    logger.debug(f'Getting browser data from {url} through proxy {proxy}')
    with psa.sync_playwright() as p:
        browser = p.firefox.launch(proxy={'server': proxy, 'username': user, 'password': passw}, headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)
        stealth.stealth_sync(page)
        page.goto(url)
        page.pause()
        locator = page.locator('#X-CSRF-TOKEN')
        csrf_token = locator.first.get_attribute('content')
        cookies = context.cookies()
        context.close()
    cookiejar = {}
    for cookie in cookies:
        cookiejar[cookie['name']] = str(cookie['value'])
    return {'cookiejar': cookiejar, 'csrf_token': csrf_token}


# proxy_settings of form {proxy_url: <str> | gen, proxy_user: <str>, proxy_passw: <str>}
def run_scraper(item: str, proxy_settings: dict, pagination: int | None = 1) -> None:
    if item.find(' ') > -1:
        tag_search = item.replace(' ', '-')
        query_search = item.replace(' ', '%20')
    else:
        tag_search = query_search = item
    
    html_url = f'https://www.lazada.com.ph/tag/{tag_search}/?spm=a2o4l.homepage.search.d_go&q={query_search}'
    scrape_data = []
    noMorePages = False
    newSession = False

    while not noMorePages:
        api_url = f'https://www.lazada.com.ph/tag/{tag_search}/?ajax=true&page={pagination}&q={query_search}&spm=a2o4l.homepage.search.d_go'
        
        if not newSession:
            proxy = proxy_settings.get('proxy_url')
            if callable(proxy):
                proxy = next(proxy())
            browser_data = get_cookies_headers(html_url, proxy, proxy_settings.get('proxy_user'), proxy_settings.get('proxy_passw'))
            headers = rotate_header()
            headers['X-CSRF-TOKEN'] = browser_data['csrf_token']
            logger.debug(f'Obtained new cookies and new header = {headers}')
            curr_session = requests.Session()
            logger.debug(f'Obtained new session')
            curr_session.cookies.update(browser_data['cookiejar'])
            curr_session.proxies = {'https': proxy}
            curr_session.headers = headers
            newSession = True

        try:
            random_delay()
            response = curr_session.request('GET', api_url, impersonate='chrome')
            response.raise_for_status()
        except HTTPError as e:
            logger.error(f'Failed to get from API with due to {e.strerror}', exc_info=True)
        
        response_json = response.json()
        random_delay()
        scrape_data.append(response_json)
        
        noMorePages = response_json['mainInfo'].get('noMorePages')
        pagination += 1
    
    with open('data.txt', 'w') as output:
        output.write(json.dumps(scrape_data))

    # If timeout then new proxy

proxy_settings = {'proxy_url': get_proxy_endpoint, 'proxy_user': PROXY_USER, 'proxy_passw': PROXY_PASS}
run_scraper('ketchup', proxy_settings)