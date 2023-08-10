


# The 'get_text' Command
import requests
from bs4 import BeautifulSoup as BS

async def get_text(url):
    res = requests.get(url)
    soup = BS(res.text, 'html.parser')
    text_data = soup.get_text(' ', strip=True)
    return text_data

# The 'read' Command
async def read(text, window_size):
    chunks = [text[i:i+window_size] for i in range(0, len(text), window_size)]
    return chunks

async def advanced_scraper(url):
    res = requests.get(url)
    soup = BS(res.text, 'html.parser')

    texts = soup.get_text(' ', strip=True)
    image_descriptions = [img['alt'] for img in soup.find_all('img') if 'alt' in img.attrs]
    urls = [a['href'] for a in soup.find_all('a', href=True)]

    return texts, image_descriptions, urls