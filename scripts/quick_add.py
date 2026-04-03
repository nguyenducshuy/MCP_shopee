"""Quick add shop — chạy liên tục, paste shop info vào stdin."""
import sys, io, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')

BASE = 'http://localhost:8000/mcp'
H = {'Content-Type': 'application/json', 'Accept': 'text/event-stream, application/json'}
SID = None

def mc(m, p=None):
    global SID
    h = dict(H)
    if SID: h['Mcp-Session-Id'] = SID
    with httpx.stream('POST', BASE, json={'jsonrpc':'2.0','method':m,'params':p or{},'id':1}, headers=h, timeout=30) as r:
        SID = r.headers.get('mcp-session-id', SID)
        res = []
        for l in r.iter_lines():
            if l.strip().startswith('data: '):
                try: res.append(json.loads(l.strip()[6:]))
                except: pass
        return res

def tool(n, a):
    r = mc('tools/call', {'name': n, 'arguments': a})
    for i in r:
        if 'result' in i:
            for c in i['result'].get('content', []):
                if c.get('type') == 'text':
                    try: return json.loads(c['text'])
                    except: return c['text']
        if 'error' in i: return i['error']
    return None

# Init MCP
mc('initialize', {'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'t','version':'1'}})
httpx.post(BASE, json={'jsonrpc':'2.0','method':'notifications/initialized'}, headers={**H, 'Mcp-Session-Id': SID})
print("MCP connected. Paste: name - shop_id - code (hoac 'q' de thoat)\n")

while True:
    try:
        line = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not line or line.lower() == 'q':
        break

    parts = [p.strip() for p in line.split(' - ')]
    if len(parts) < 3:
        # Try: code only (for existing shop needing re-exchange)
        parts2 = [p.strip() for p in line.split('-')]
        if len(parts2) < 3:
            print("  Format: name - shop_id - code")
            continue
        parts = [' - '.join(parts2[:-2]), parts2[-2].strip(), parts2[-1].strip()]

    name = parts[0]
    try:
        shop_id = int(parts[1])
    except:
        print(f"  shop_id khong hop le: {parts[1]}")
        continue
    code = parts[2]

    # Check if shop exists
    shops = tool('list_shops', {})
    existing = None
    if isinstance(shops, dict):
        for s in shops.get('shops', []):
            if str(shop_id) in s.get('shop_name', '') or s.get('shop_name', '') in name:
                existing = s['shop_code']
                break

    if not existing:
        r = tool('add_shop', {'shop_id': shop_id, 'shop_name': name, 'region': 'VN', 'environment': 'production', 'oauth_code': code})
        sc = r.get('shop_code') if isinstance(r, dict) else None
        if not sc:
            print(f"  ADD FAIL: {r}")
            continue
        print(f"  Added: {sc[:16]}...")
    else:
        sc = existing
        print(f"  Exists: {sc[:16]}...")

    r = tool('exchange_token', {'shop_code': sc, 'code': code})
    if isinstance(r, dict) and r.get('ok'):
        print(f"  TOKEN OK: {r.get('access_token_tail')} ({r.get('expires_in_human')})")
    else:
        print(f"  TOKEN FAIL: {json.dumps(r, ensure_ascii=False)[:150]}")
