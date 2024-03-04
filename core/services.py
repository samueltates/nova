import os
import requests
from tools.debug import eZprint, eZprint_anything
import json

def get_media_from_request(payload):
    # takes initial input, sends to endpoint, returns media
    eZprint(payload, ['MEDIA'], message = 'media payload')
    headers = {'content-type': 'application/json'}
    r = requests.post(os.getenv('MEDIA_URL') + 'transform', data=json.dumps(payload), headers=headers )
    eZprint_anything(r, ['MEDIA'], message = 'media response')
    return r.json()
