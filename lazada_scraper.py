import random, os, requests, dotenv, json, bs4, time, logging, playwright.sync_api as psa
import requests.cookies
import requests.utils


# Steps
# 1. create loop to get x number links to products (goal: 1000)
# 2. create loop to scrape every product
#       a. identify details to obtain
# 3. store in file db
#       a. identify schema

DELAY_MEAN = 1
DELAY_SD = 0.5
ITEM_SEARCH = 'cleanser'
page_num = 1

logger = logging.getLogger(__name__)
logging.basicConfig()
logger.setLevel(logging.DEBUG)
dotenv.load_dotenv()
with open('user_agents.json', 'r') as agents:
    agents_list = json.loads(agents.read())


def random_delay():
    if random.random() > 0.5:
        time.sleep(abs(random.gauss(DELAY_MEAN, DELAY_SD)) * random.random())
    else:
        time.sleep(abs(random.gauss(DELAY_MEAN, DELAY_SD)) + random.random())

def rotate_agent():
    return random.choice(agents_list)

def rotate_header():
    return {
        "User-Agent": rotate_agent(),
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    }

def get_proxy_endpoint():
    yield from json.loads(os.getenv('PROXY'))

# https://www.lazada.com.ph/catalog/?ajax=true&page=3&q=cleanser&spm=a2o4l.homepage.search.d_go
# .ant-pagination-next
# recaptchav2

proxy_generator = get_proxy_endpoint()

def get_cookies(url, proxy):
    logger.debug(f'Getting cookies from {url} through proxy {proxy}')
    with psa.sync_playwright() as p:
        browser = p.firefox.launch(proxy={'server': proxy})
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)
        cookies = context.cookies()
        context.close()
    cookiejar = {}
    for cookie in cookies:
        cookiejar[cookie['name']] = str(cookie['value'])
    return cookiejar

url = 'https://www.lazada.com.ph/catalog/?page=1&q=cleanser&spm=a2o4l.homepage.search.d_go'
headers = rotate_header()
proxy = next(proxy_generator)
proxy = next(proxy_generator)
with requests.Session() as session:
    session.cookies.update(get_cookies('https://www.lazada.com.ph/', proxy))
    session.proxies = {'https': proxy}
    session.headers = headers
    logger.debug(f'GET request with headers {headers}')
    logger.debug(f'GET request with cookies {session.cookies}')
    response = session.get(url)
    
    with open('testfile.html', 'w', encoding=response.encoding) as out:
        out.write(response.text)

# If timeout then new proxy