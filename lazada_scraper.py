import random, os, dotenv, json, time, logging, warnings
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from curl_cffi import requests
from requests import HTTPError


# Steps
# 1. create loop to get x number links to products (goal: 1000)
# 2. create loop to scrape every product
#       a. identify details to obtain
# 3. store in file db
#       a. identify schema

DELAY_MEAN = 2
DELAY_SD = 0.1
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
        "accept": "application/json, text/plain, */*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9,id;q=0.8",
        "dnt": "1",
        "priority": "u=1, i",
        "referer": "https://www.lazada.com.ph/",
        "sec-ch-ua": "\"Google Chrome\";v=\"129\", \"Not=A?Brand\";v=\"8\", \"Chromium\";v=\"129\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": user_agent
    }

def get_proxy_endpoint():
    yield from PROXIES

def get_cookies_headers(url: str, proxy: str, user: str, passw: str) -> list:
    logger.debug(f'Getting browser data from {url} through proxy {proxy}')
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.firefox.launch(proxy={'server': proxy, 'username': user, 'password': passw}, headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT)
        page.goto(url)
        page.pause()
        csrf_locator = page.locator('#X-CSRF-TOKEN')
        for i in range(csrf_locator.count()):
            csrf_token = csrf_locator.nth(i).get_attribute('content')
            if csrf_token: break
        cookies = context.cookies()
        context.close()
    cookiejar = {}
    for cookie in cookies:
        cookiejar[cookie['name']] = str(cookie['value'])
    return {'cookiejar': cookiejar, 'csrf_token': csrf_token}

def get_new_session(session_url: str, proxy_settings: dict) -> requests.Session:
    proxy = proxy_settings.get('proxy_url')
    if callable(proxy):
        proxy = next(proxy())
    logger.info(f'Opening browser... Answer any CAPTCHAs that may appear during this time. Press "Resume" in Playwright inspector to continue execution after answering CAPTCHA')
    browser_data = get_cookies_headers(session_url, proxy, proxy_settings.get('proxy_user'), proxy_settings.get('proxy_passw'))
    headers = rotate_header()
    headers['X-CSRF-TOKEN'] = browser_data['csrf_token']
    logger.debug(f'Obtained new cookies and new header = {headers}')
    new_session = requests.Session()
    logger.debug(f'Obtained new session')
    new_session.cookies.update(browser_data['cookiejar'])
    new_session.proxies = {'https': proxy}
    new_session.headers = headers
    
    return new_session

def run_page_scraper(item: str, proxy_settings: dict, pagination: int | None = 1) -> list:
    """proxy_settings should be dict of form {proxy_url: <str> | <generator>, proxy_user: <str>, proxy_passw: <str>}"""

    start_time = time.time()
    if item.find(' ') > -1:
        tag_search = item.replace(' ', '-')
        query_search = item.replace(' ', '%20')
    else:
        tag_search = query_search = item
    
    html_url = f'https://www.lazada.com.ph/tag/{tag_search}/?spm=a2o4l.homepage.search.d_go&q={query_search}&catalog_redirect_tag=true'
    scrape_data = []
    noMorePages: bool = False
    newSession: bool = False
    totalPages = None

    while not noMorePages:
        api_url = f'https://www.lazada.com.ph/tag/{tag_search}/?ajax=true&catalog_redirect_tag=true&page={pagination}&q={query_search}&spm=a2o4l.homepage.search.d_go'
        
        if not newSession:
            curr_session = get_new_session(html_url, proxy_settings)
            newSession = True

        try:
            random_delay()
            response = curr_session.request('GET', api_url, impersonate='chrome')
            response.raise_for_status()
        except HTTPError as error:
            logger.error(f'Failed to get from API with due to {error}', exc_info=True)
        
        response_json = response.json()
        random_delay()
        try:
            noMorePages = response_json['mainInfo'].get('noMorePages')
            if totalPages is None:
                totalPages = response_json['mainInfo'].get('totalResults') / response_json['mainInfo'].get('pageSize')
        except KeyError:
            logger.error(f'Response JSON has no key "mainInfo". Possible that scraper is detected. Renewing session...')
            curr_session.close()
            newSession = False
            continue
        scrape_data.append(response_json)
        
        logger.info(f'Successfully scraped data from API in page {pagination} out of {totalPages:.0f} pages')
        pagination += 1
    
    
    with open('page_data.txt', 'w') as output:
        output.write(json.dumps(scrape_data))
    end_time = time.time()
    logger.info(f'Done scraping data for query in {end_time - start_time} seconds')

    return scrape_data




proxy_settings = {'proxy_url': get_proxy_endpoint, 'proxy_user': PROXY_USER, 'proxy_passw': PROXY_PASS}
run_page_scraper('face cleanser', proxy_settings)