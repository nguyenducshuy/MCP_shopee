"""Test toàn bộ 11 Flash Sale tools trên production → xóa sạch cuối cùng."""
import sys, io, json, httpx, time
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = 'http://localhost:8000/mcp'
H = {'Content-Type': 'application/json', 'Accept': 'text/event-stream, application/json'}
TZ = timezone(timedelta(hours=7))

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
        print(f'  ERROR: {r[:300]}')
    else:
        print(f'  {json.dumps(r, ensure_ascii=False)[:400]}')

# Init
r, sid = mc('initialize', {'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'t','version':'1'}})
httpx.post(BASE, json={'jsonrpc':'2.0','method':'notifications/initialized'}, headers={**H, 'Mcp-Session-Id': sid})

SC = '7265fd2365780c5e65ea9ec4a7e76db8'  # Kid Center production
now = int(time.time())

print('=' * 60)
print('FULL FLASH SALE TEST — Kid Center (PRODUCTION)')
print('=' * 60)

# 1. get_item_criteria
print('\n[1/11] get_item_criteria')
r, sid = tool('get_item_criteria', {'shop_code': SC}, sid)
p(r)

# 2. get_time_slot_id
print('\n[2/11] get_time_slot_id')
r, sid = tool('get_time_slot_id', {'shop_code': SC, 'start_time': now + 60, 'end_time': now + 7*86400}, sid)
p(r)
slots = []
if isinstance(r, dict) and r.get('time_slot_list'):
    slots = r['time_slot_list']
    chosen = slots[-1]  # slot xa nhất
    slot_id = chosen['timeslot_id']
    st = datetime.fromtimestamp(chosen['start_time'], TZ).strftime('%d/%m %H:%M')
    et = datetime.fromtimestamp(chosen['end_time'], TZ).strftime('%H:%M')
    print(f'  -> {len(slots)} slots. Chon slot cuoi: {slot_id} | {st}-{et}')
if not slots:
    print('  KHONG CO SLOT -> dung'); sys.exit(0)

# 3. create_shop_flash_sale
print('\n[3/11] create_shop_flash_sale')
r, sid = tool('create_shop_flash_sale', {'shop_code': SC, 'timeslot_id': slot_id}, sid)
p(r)
fs_id = r.get('flash_sale_id') if isinstance(r, dict) else None
if fs_id:
    print(f'  -> flash_sale_id = {fs_id}, status = {r.get("status")}')
else:
    print('  KHONG TAO DUOC -> dung'); sys.exit(0)

# 4. get_shop_flash_sale
print(f'\n[4/11] get_shop_flash_sale (id={fs_id})')
r, sid = tool('get_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
p(r)

# 5. get_shop_flash_sale_list
print('\n[5/11] get_shop_flash_sale_list (type=1 upcoming)')
r, sid = tool('get_shop_flash_sale_list', {'shop_code': SC, 'type': 1, 'offset': 0, 'limit': 10}, sid)
p(r)

# Lay 1 item_id that tu shop
print('\n  -> Lay item_id that tu shop...')
items_r, sid = tool('get_item_list', {'shop_code': SC, 'offset': 0, 'page_size': 5, 'item_status': 'NORMAL'}, sid)
test_item_id = None
test_model_id = None
if isinstance(items_r, dict):
    item_list = items_r.get('item', [])
    if item_list:
        test_item_id = item_list[0].get('item_id')
        print(f'  -> item_id = {test_item_id}')
        base_r, sid = tool('get_item_base_info', {'shop_code': SC, 'item_id_list': str(test_item_id)}, sid)
        if isinstance(base_r, dict):
            il = base_r.get('item_list', [])
            if il and il[0].get('model'):
                test_model_id = il[0]['model'][0].get('model_id')
                print(f'  -> model_id = {test_model_id}')

if test_item_id:
    # 6. add_shop_flash_sale_items
    print(f'\n[6/11] add_shop_flash_sale_items')
    if test_model_id:
        add_items = [{'item_id': test_item_id, 'purchase_limit': 0,
                       'models': [{'model_id': test_model_id, 'input_promo_price': 1000, 'stock': 5}]}]
    else:
        add_items = [{'item_id': test_item_id, 'purchase_limit': 0,
                       'item_input_promo_price': 1000, 'item_stock': 5}]
    r, sid = tool('add_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'items': add_items}, sid)
    p(r)

    # 7. get_shop_flash_sale_items
    print(f'\n[7/11] get_shop_flash_sale_items')
    r, sid = tool('get_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
    p(r)

    # 8. update_shop_flash_sale (enable)
    print(f'\n[8/11] update_shop_flash_sale (enable, status=1)')
    r, sid = tool('update_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id, 'status': 1}, sid)
    p(r)

    # 9. update_shop_flash_sale_items
    if test_model_id:
        print(f'\n[9a/11] update_shop_flash_sale_items (disable model)')
        upd = [{'item_id': test_item_id, 'models': [{'model_id': test_model_id, 'status': 0}]}]
        r, sid = tool('update_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'items': upd}, sid)
        p(r)

        print(f'\n[9b/11] update_shop_flash_sale_items (doi gia + enable lai)')
        upd2 = [{'item_id': test_item_id, 'models': [{'model_id': test_model_id, 'status': 1, 'input_promo_price': 900, 'stock': 3}]}]
        r, sid = tool('update_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'items': upd2}, sid)
        p(r)

    # 10. delete_shop_flash_sale_items
    print(f'\n[10/11] delete_shop_flash_sale_items')
    r, sid = tool('delete_shop_flash_sale_items', {'shop_code': SC, 'flash_sale_id': fs_id, 'item_ids': [test_item_id]}, sid)
    p(r)
else:
    print('  KHONG TIM DUOC ITEM -> bo qua buoc 6-10')

# 11. delete_shop_flash_sale
print(f'\n[11a] update_shop_flash_sale (disable truoc khi xoa)')
r, sid = tool('update_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id, 'status': 2}, sid)
p(r)

print(f'\n[11b] delete_shop_flash_sale (xoa phien test)')
r, sid = tool('delete_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
p(r)

# Verify
print(f'\n[VERIFY] get_shop_flash_sale (confirm deleted)')
r, sid = tool('get_shop_flash_sale', {'shop_code': SC, 'flash_sale_id': fs_id}, sid)
p(r)

print('\n' + '=' * 60)
print('TEST HOAN TAT — Phien Flash Sale test da duoc xoa sach')
print('=' * 60)
