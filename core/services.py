import os
import requests
from tools.debug import eZprint

def get_media_from_request(payload):
    # takes initial input, sends to endpoint, returns media
    eZprint(payload, ['MEDIA'], message = 'media payload')
    r = requests.post(os.getenv('MEDIA_URL'), data=payload)
    eZprint(r.json(), ['MEDIA'], message = 'media response')
    return r.json()
