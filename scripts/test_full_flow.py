"""Test full Flash Sale flow: create -> add item 25932347665 -> enable -> disable -> delete."""
import sys, io, json, httpx, time
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = 'http://localhost:8000/mcp'
H = {'Content-Type': 'application/json', 'Accept': 'text/event-stream, application/json'}
TZ = timezone(timedelta(hours=7))
SC = '7265fd2365780c5e65ea9ec4a7e76db8'  # Kid Center production
ITEM_ID = 25932347665

def mc(method, params=None, sid=None):
    h = dict(H)
    if sid: h['Mcp-Session-Id'] = sid
    with httpx.stream('POST', BASE, json={'jsonrpc':'2.0','method':method,'params':params or {},'id':1}, headers=h, timeout=30) as resp:
        sid = resp.headers.get('mcp-session-id', sid)
        res = []
        for line in resp.iter_lines():
            if line.strip().startswith('data: '):
                try: res.append(json.loads(line.strip()[6:]))
                except: pass
        return res, sid

def tool(name, args, sid):
    r, sid = mc('tools/call', {'name': name, 'arguments': args}, sid)
    for item in r:
        if 'result' in item:
            for c in item['result'].get('content', []):
                if c.get('type') == 'text':
                    try: return json.loads(c['text']), sid
                    except: return c['text'], sid
        if 'error' in item: return item['error'], sid
    return None, sid

def p(r):
    if isinstance(r, str):
        print(f'  {r[:400]}')
    else:
        print(f'  {json.dumps(r, ensure_ascii=False, indent=2)[:500]}')

# Init
r, sid = mc('initialize', {'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'t','version':'1'}})
httpx.post(BASE, json={'jsonrpc':'2.0','method':'notifications/initialized'}, headers={**H, 'Mcp-Session-Id': sid})

now = int(time.time())
print('=' * 60)
print(f'FULL FLOW TEST - item_id={ITEM_ID}')
print(f'Shop: Kid Center | Time: {datetime.now(TZ).strftime("%d/%m/%Y %H:%M")}')
print('=' * 60)

# 1. get_item_criteria
print('\n[1] get_item_criteria')
r, sid = tool('get_item_criteria', {'shop_code': SC}, sid)
p(r)

# 2. get_time_slot_id
print('\n[2] get_time_slot_id')
r, sid = tool('get_time_slot_id', {'shop_code': SC, 'start_time': now + 3600, 'end_time': now + 7*86400}, sid)
slots = r.get('time_slot_list', []) if isinstance(r, dict) else []
print(f'  {len(slots)} slots')
if not slots:
    print('  KHONG CO SLOT -> dung'); sys.exit(0)
chosen = slots[-1]
slot_id = chosen['timeslot_id']
st = datetime.fromtimestamp(chosen['start_time'], TZ).strftime('%d/%m %H:%M')
et = datetime.fromtimestamp(chosen['end_time'], TZ).strftime('%H:%M')
print(f'  Chon: {slot_id} | {st}-{et}')

# 3. create_shop_flash_sale
print('\n[3] create_shop_flash_sale')
r, sid = tool('create_shop_flash_sale', {'shop_code': SC, 'timeslot_id': slot_id}, sid)
p(r)
fs_id = r.get('flash_sale_id') if isinstance(r, dict) else None
if not fs_id:
    print('  KHONG TAO DUOC -> dung'); sys.exit(0)
print(f'  -> flash_sale_id = {fs_id}')

# 4. get_shop_flash_sale (xem chi tiet)
print(f'\n[4] get_shop_flash_sale')
r, sid = tool('get_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
p(r)

# 5. Lay model info cho item 25932347665
print(f'\n[5] Lay model info cho item {ITEM_ID}')
r, sid = tool('get_item_base_info', {'shop_code': SC, 'item_id_list': str(ITEM_ID)}, sid)
models = []
if isinstance(r, dict):
    il = r.get('item_list', [])
    if il:
        item_info = il[0]
        item_name = item_info.get('item_name', '?')
        models = item_info.get('model', [])
        print(f'  Ten SP: {item_name}')
        print(f'  So model: {len(models)}')
        for m in models[:5]:
            mid = m.get('model_id')
            price = m.get('price_info', {})
            if isinstance(price, list) and price:
                price = price[0]
            cur_price = price.get('current_price', '?') if isinstance(price, dict) else '?'
            print(f'    model_id={mid} | price={cur_price}')
else:
    print(f'  {str(r)[:200]}')

# 6. add_shop_flash_sale_items
print(f'\n[6] add_shop_flash_sale_items')
if models:
    # SP co bien the -> dung models[]
    first_model = models[0]
    mid = first_model.get('model_id')
    price_info = first_model.get('price_info', {})
    if isinstance(price_info, list) and price_info:
        price_info = price_info[0]
    orig_price = price_info.get('original_price', 100000) if isinstance(price_info, dict) else 100000
    promo_price = orig_price * 0.8  # giam 20%
    add_items = [{
        'item_id': ITEM_ID,
        'purchase_limit': 5,
        'models': [{'model_id': mid, 'input_promo_price': promo_price, 'stock': 10}]
    }]
    print(f'  Co bien the: model_id={mid}, promo_price={promo_price}, stock=10')
else:
    # SP khong bien the
    promo_price = 80000
    add_items = [{
        'item_id': ITEM_ID,
        'purchase_limit': 5,
        'item_input_promo_price': promo_price,
        'item_stock': 10
    }]
    print(f'  Khong bien the: promo_price={promo_price}, stock=10')

r, sid = tool('add_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'items': add_items}, sid)
p(r)
failed = r.get('failed_items', []) if isinstance(r, dict) else []
if failed:
    print(f'  !! FAILED: {json.dumps(failed, ensure_ascii=False)[:300]}')

# 7. get_shop_flash_sale_items
print(f'\n[7] get_shop_flash_sale_items')
r, sid = tool('get_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
p(r)

# 8. update_shop_flash_sale (enable)
print(f'\n[8] update_shop_flash_sale (enable)')
r, sid = tool('update_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id, 'status': 1}, sid)
p(r)

# 9. update_shop_flash_sale_items (disable -> doi gia -> enable)
if models:
    mid = models[0].get('model_id')
    new_price = promo_price * 0.9  # giam them 10%

    print(f'\n[9a] update_shop_flash_sale_items (disable model)')
    upd = [{'item_id': ITEM_ID, 'models': [{'model_id': mid, 'status': 0}]}]
    r, sid = tool('update_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'items': upd}, sid)
    p(r)

    print(f'\n[9b] update_shop_flash_sale_items (doi gia {promo_price} -> {new_price} + enable)')
    upd2 = [{'item_id': ITEM_ID, 'models': [{'model_id': mid, 'status': 1, 'input_promo_price': new_price, 'stock': 8}]}]
    r, sid = tool('update_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'items': upd2}, sid)
    p(r)

# 10. get_shop_flash_sale_items (xac nhan gia moi)
print(f'\n[10] get_shop_flash_sale_items (xac nhan)')
r, sid = tool('get_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
p(r)

# 11. delete_shop_flash_sale_items
print(f'\n[11] delete_shop_flash_sale_items')
r, sid = tool('delete_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'item_ids': [ITEM_ID]}, sid)
p(r)

# 12. disable + delete flash sale
print(f'\n[12a] update_shop_flash_sale (disable)')
r, sid = tool('update_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id, 'status': 2}, sid)
p(r)

print(f'\n[12b] delete_shop_flash_sale')
r, sid = tool('delete_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
p(r)

# Verify
print(f'\n[VERIFY] get_shop_flash_sale')
r, sid = tool('get_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
status = r.get('status', '?') if isinstance(r, dict) else '?'
print(f'  status = {status} (0=deleted)')

print('\n' + '=' * 60)
print('DONE - Phien test da xoa sach')
print('=' * 60)
