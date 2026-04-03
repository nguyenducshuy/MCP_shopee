"""Add + exchange token cho nhiều shop cùng lúc."""
import sys, io, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://localhost:8000/mcp'
H = {'Content-Type': 'application/json', 'Accept': 'text/event-stream, application/json'}
SID = None

def mc(method, params=None):
    global SID
    h = dict(H)
    if SID: h['Mcp-Session-Id'] = SID
    with httpx.stream('POST', BASE, json={'jsonrpc':'2.0','method':method,'params':params or {},'id':1}, headers=h, timeout=30) as resp:
        SID = resp.headers.get('mcp-session-id', SID)
        res = []
        for line in resp.iter_lines():
            if line.strip().startswith('data: '):
                try: res.append(json.loads(line.strip()[6:]))
                except: pass
        return res

def tool(name, args):
    r = mc('tools/call', {'name': name, 'arguments': args})
    for item in r:
        if 'result' in item:
            for c in item['result'].get('content', []):
                if c.get('type') == 'text':
                    try: return json.loads(c['text'])
                    except: return c['text']
        if 'error' in item: return item['error']
    return None

# Init
mc('initialize', {'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'t','version':'1'}})
httpx.post(BASE, json={'jsonrpc':'2.0','method':'notifications/initialized'}, headers={**H, 'Mcp-Session-Id': SID})

shops = [
    ("Camcam.shoes", 1022311327, "434c51635761504a58454d7858786f49"),
    ("Olivia Beautycare Store", 816409857, "5650625954426a6d4d58617357747855"),
    ("Tiem giay cua to", 1354723366, "74476d644d48725042566b49686b594f"),
    ("Gogoback Shoes", 1364808811, "58704170724b4a7043594158746a786a"),
    ("Eling Studio", 1357894898, "61486f6d674a43585a4f6f59546e7279"),
    ("Belle Studio", 1375744205, "6656664e477261634b46714f66617a6c"),
    ("Tachi.shoes", 1131444686, "5a754657534166646a774f7947677669"),
]

for name, shop_id, code in shops:
    print(f'\n{"="*50}')
    print(f'{name} (ID: {shop_id})')

    # Add
    r = tool('add_shop', {
        'shop_id': shop_id, 'shop_name': name,
        'region': 'VN', 'environment': 'production',
        'oauth_code': code,
    })
    sc = r.get('shop_code') if isinstance(r, dict) else None
    if not sc:
        print(f'  ADD FAIL: {r}')
        continue
    print(f'  Added: {sc[:16]}...')

    # Exchange
    r = tool('exchange_token', {'shop_code': sc})
    if isinstance(r, dict) and r.get('ok'):
        print(f'  Token OK: {r.get("access_token_tail")}')
        # Verify
        r2 = tool('get_shop_info', {'shop_code': sc})
        sn = r2.get('shop_name', '?') if isinstance(r2, dict) else '?'
        print(f'  Verified: {sn}')
    else:
        print(f'  TOKEN FAIL: {r}')

# Final list
print(f'\n{"="*50}')
print('ALL SHOPS:')
r = tool('list_shops', {})
if isinstance(r, dict):
    for s in r.get('shops', []):
        print(f'  {s["shop_name"]:30s} | {s["shop_code"][:16]}...')
    print(f'\nTotal: {len(r.get("shops", []))} shops')
