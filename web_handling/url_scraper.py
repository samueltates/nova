


# The 'get_text' Command
import requests
from bs4 import BeautifulSoup as BS
from tools.debug import eZprint
from unstructured.partition.html import partition_html
from unstructured.staging.base import convert_to_dict

DEBUG_KEYS = ['URL']

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
    SCRAPE_KEYS = DEBUG_KEYS + ['SCRAPE']
    elements = partition_html(url=url)
    eZprint(elements, SCRAPE_KEYS, message = 'unstructured return')

    elements = convert_to_dict(elements)
    eZprint(elements, SCRAPE_KEYS, message = 'converted to dictionary')

    return elements

    res = requests.get(url)
    soup = BS(res.text, 'html.parser')

    for script in soup(["script", "style"]):
        script.decompose()

    


    elements = []

    for tag in soup.find_all(True):
        element = {}
        if tag.name == 'img' and 'src' in tag.attrs and 'alt' in tag.attrs:
            element['image_src'] = tag['src']
            element['image_alt_text'] = tag['alt']
        elif tag.name == 'a' and tag.string and 'href' in tag.attrs:
            element['link_text'] = tag.string
            element['url'] = tag['href']
        elif tag.string:
            element['text'] = tag.string

        if element:
            elements.append(element)



    document_json = {
        'type':'doc',
        'content':elements
        }

    return document_json