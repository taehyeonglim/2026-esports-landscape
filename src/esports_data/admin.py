"""Loopback-only review UI. Explicit routes; no generic filesystem serving."""
from __future__ import annotations
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from .workbench import Workbench, encoded


def make_server(workbench, port=4188):
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def reply(self,status,payload,content_type='application/json'):
            data=payload.encode() if isinstance(payload,str) else encoded(payload).encode()
            self.send_response(status)
            for key,value in {'Content-Type':content_type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():self.send_header(key,value)
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def authorized(self):
            expected=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=expected:return False
            if self.path.startswith('/api/'):
                return secrets.compare_digest(self.headers.get('X-Review-Token',''),token) and self.headers.get('Origin') in (None,f'http://{expected}') and self.headers.get('Sec-Fetch-Site','same-origin') in ('same-origin','none')
            return True
        def do_GET(self):
            if not self.authorized():return self.reply(403,{'error':'unauthorized'})
            if self.path=='/api/state':
                try:return self.reply(200,workbench.state())
                except (ValueError,RuntimeError):return self.reply(409,{'error':'state_conflict'})
            paths={'/':('index.html','text/html; charset=utf-8'),'/admin.js':('admin.js','text/javascript; charset=utf-8'),'/admin.css':('admin.css','text/css; charset=utf-8')}
            if self.path not in paths:return self.reply(404,{'error':'not_found'})
            path,mime=paths[self.path];return self.reply(200,(workbench.root/'admin'/path).read_text(),mime)
        def do_POST(self):
            if not self.authorized():return self.reply(403,{'error':'unauthorized'})
            if self.path not in {'/api/command','/api/export','/api/inspect','/api/followup'}:return self.reply(404,{'error':'not_found'})
            if self.headers.get('Origin')!=f'http://127.0.0.1:{self.server.server_port}':return self.reply(403,{'error':'origin_required'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=64000 or self.headers.get('Content-Type')!='application/json':raise ValueError('Invalid request')
                body=json.loads(self.rfile.read(length))
                if self.path=='/api/followup':
                    import tomllib
                    from urllib.parse import urlsplit
                    from .followup import official_followup
                    rows=[]
                    for filename in ['sources.toml','discovery-sources.toml']:
                        rows.extend(tomllib.loads((workbench.root/'config'/filename).read_text()).get('source',[]))
                    hosts={urlsplit(r['endpoint']).hostname for r in rows if r.get('kind')!='rss'}
                    return self.reply(200,official_followup(body['url'],hosts))
                if self.path=='/api/inspect':
                    from .recheck import inspect_url
                    return self.reply(200,inspect_url(body['url']))
                result=workbench.export() if self.path=='/api/export' else workbench.command(body)
                return self.reply(200,result)
            except (ValueError,KeyError,TypeError,RuntimeError):return self.reply(409,{'error':'rejected','message':'입력·근거 또는 버전 충돌을 확인하고 목록을 새로고침하세요.'})
    server=HTTPServer(('127.0.0.1',port),Handler)
    server.review_token=token
    return server


def run(args):
    root=Path(args.root).resolve()
    workbench=Workbench(root,root/'artifacts/workbench/reviews.sqlite3',args.reviewer)
    server=make_server(workbench,args.port)
    print(f'Local review: http://127.0.0.1:{server.server_port}/#token={server.review_token}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();workbench.db.close()
    return 0
