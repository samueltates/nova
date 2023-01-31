from .nova import *
from http.server import BaseHTTPRequestHandler
import json


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        print("gettingPrompts")
        print(self.rfile.read)
        content_len = int(self.headers['content-length'])
        post_body = self.rfile.read(content_len)
        post_body_py = json.loads(post_body)
        print(post_body_py)
        parseCartridgeAction(post_body_py)

        # gets body from message, needs length of file and reads that length
        # not sure why this is so it doesn't go forever I guess
        prompts = json.dumps(runningPrompts[post_body_py["UUID"]])
        print('printing prompts pulled from running??')
        print(prompts)
        content = bytes(prompts, 'utf-8')

        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)
        return
