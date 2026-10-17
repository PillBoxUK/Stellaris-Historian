"""Isolated v0.0.85.1 recording-confirmation contract tests; never reads or edits real user data.
Run from project root: python tests/test_v0_0_85_1.py
"""
import ast
import asyncio
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
s= (ROOT/'app.py').read_text(encoding='utf-8')
tree=ast.parse(s)

class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code=status_code
        self.detail=detail

class FakeDB:
    def __init__(self):
        self.writes=0
    def campaign(self,id):
        return {'id':id,'empire_name':'Fixture Empire'} if id==9 else None
    def unprocessed_count(self,id):
        return 3

class FakeWatcher:
    status='Monitoring selected civilisation'

class FakeRequest:
    def __init__(self, body):
        self.body=body
    async def json(self):
        return self.body

class Logger:
    def __init__(self): self.messages=[]
    def __call__(self,msg):self.messages.append(msg)

class FakeApp:
    def post(self,path):
        self.endpoint=path
        return lambda f:f

async def run():
    test_env={
        'app':FakeApp(),
        'Request':FakeRequest,
        'HTTPException':HttpError,
        'DB':FakeDB(),
        'WATCHER':FakeWatcher(),
        'activity':Logger(),
        'ACTIVE_CAMPAIGN_ID':9,
        'LIVE_HISTORY_ENABLED':False,
        'LIVE_HISTORY_BUSY':False,
        'LIVE_HISTORY_STATUS':'OFF',
        'RECORDING_DECISION':'pending',
    }
    func=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='api_recording_decision')
    exec(compile(ast.Module(body=[func],type_ignores=[]),str(ROOT/'app.py'),'exec'),test_env)
    endpoint=test_env['api_recording_decision']
    yes=await endpoint(FakeRequest({'campaign_id':9,'enabled':True}))
    assert yes['ok'] and yes['enabled'] is True
    assert yes['recording_decision']=='accepted'
    assert yes['queued_saves']==3 and yes['watcher_status']==FakeWatcher.status
    assert test_env['RECORDING_DECISION']=='accepted'
    assert test_env['LIVE_HISTORY_ENABLED'] is True

    no=await endpoint(FakeRequest({'campaign_id':9,'enabled':False}))
    assert no['enabled'] is False and no['recording_decision']=='declined'
    assert test_env['LIVE_HISTORY_ENABLED'] is False

    test_env['RECORDING_DECISION']='pending'
    for payload,code in [({'campaign_id':8,'enabled':True},409),({'campaign_id':9,'enabled':'yes'},400),({'enabled':True},400)]:
        try: await endpoint(FakeRequest(payload))
        except HttpError as ex: assert ex.status_code==code
        else: raise AssertionError(f'Invalid decision unexpectedly accepted: {payload}')
        assert test_env['RECORDING_DECISION']=='pending'
        assert test_env['LIVE_HISTORY_ENABLED'] is False
    assert test_env['DB'].writes==0

    # Selection must always reset choice and Live History to OFF.
    start=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='api_start_campaign')
    source=ast.get_source_segment(s,start)
    assert 'RECORDING_DECISION = "pending"' in source
    assert 'LIVE_HISTORY_ENABLED = False' in source
    assert 'WATCHER.select_campaign(' in source
    get=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='api_active_campaign')
    read=ast.get_source_segment(s,get)
    assert '"recording_confirmation_required": RECORDING_DECISION == "pending"' in read
    assert '"recording_decision": RECORDING_DECISION' in read
    stop=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='api_select_new_campaign')
    assert 'RECORDING_DECISION = "none"' in ast.get_source_segment(s,stop)

    html=(ROOT/'static/campaign.html').read_text(encoding='utf-8')
    js=(ROOT/'static/recording-guard.js').read_text(encoding='utf-8')
    css=(ROOT/'static/recording-guard.css').read_text(encoding='utf-8')
    assert html.count('id="recording-confirm-modal"')==1
    assert html.count('id="recording-guard-yes"')==1
    assert html.count('id="recording-guard-no"')==1
    assert 'role="dialog" aria-modal="true"' in html
    assert 'id="recording-status-banner"' in html
    assert any('/static/campaign.js?v='+v in html for v in ('081','087'))
    assert '/static/recording-guard.js?v=0851' in html
    assert "if (state.recording_confirmation_required === true" in js
    assert "Number(result.campaign_id) !== currentCampaign.id" in js
    assert "case 'pending'" not in js # no hidden fallback dismissal
    assert '.recording-status-banner[data-state="off"]' in css
    assert '[hidden]{display:none!important}' in css
    assert any('__version__ = "'+v+'"' in (ROOT/'historian/__init__.py').read_text() for v in ('0.0.85.1', '0.0.86', '0.0.87', '0.0.87.1', '0.0.87.2','0.0.88','0.0.89','0.0.90'))
    print('v0.0.85.1: YES/NO, stale ID rejection, backend reset, visible warning, dialog controls, no DB writes: PASS')

asyncio.run(run())
