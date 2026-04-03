/**
 * Shopee Ads AI Decision Engine — Google Apps Script
 * ─────────────────────────────────────────────────────────────────
 * Đọc 2 tab:  "ADS BIGSELLER ..." + "1.0 OVERVIEW PRODUCT E-COM"
 * Tra bảng:   "MAP_SHOP_NGANH" (tự động, không cần sửa code khi thêm shop)
 * Ghi ra tab: "DUYỆT CAMPAIN"
 *
 * Cách dùng:
 *   1. Mở Google Sheets → Extensions → Apps Script
 *   2. Xoá nội dung cũ, paste toàn bộ file này → Lưu (Ctrl+S)
 *   3. Chạy buildAIDecisionTab() hoặc dùng menu "Shopee Campain"
 *
 * Version: 3.0 · 2026-03-30
 * Changelog v3:
 *   [R1] STOCKOUT: PAUSE ngay khi kho ≤ 0 và đang tiêu tiền
 *   [R2] Phát hiện TRÙNG ITEM_ID: nhiều camp cùng 1 SP → bid chống nhau
 *   [R3] Phân biệt "không cắn tiền" — 3 case khác nhau (Target cao / Sản phẩm yếu / Quá sớm)
 *   [R4] CHẠY MỚI guard: chỉ đề xuất khi tồn kho đủ ≥ 7 ngày
 *   [R5] Cập nhật roas_max thực tế theo data: giay_dep 5→20, thiet_bi 10→18
 *   [R6] ROAS TARGET QUÁ CAO: cảnh báo khi target > roas_max×2 mà spend gần 0
 */

// ══════════════════════════════════════════════════════════════════
// CONFIG
// ══════════════════════════════════════════════════════════════════
const CONFIG = {
  CAMPAIGN_SHEET:  'ADS BIGSELLER',
  PRODUCT_SHEET:   '1.0 OVERVIEW PRODUCT',
  MAP_SHOP_SHEET:  'MAP_SHOP_NGANH',
  DECISION_SHEET:  'DUYỆT CAMPAIN',
  HIDE_OK:         true,
  MAX_LAUNCH:      20,
};

// ══════════════════════════════════════════════════════════════════
// NHÓM SẢN PHẨM & NGƯỠNG
// ─────────────────────────────────────────────────────────────────
// roas_min  : ROAS tối thiểu để hoà vốn QC — dưới mức này → PAUSE
// roas_max  : Ngưỡng thực tế từ data (v3 cập nhật)
//             Nếu ROAS thực > roas_max → Shopee đang bid quá conservative
//             → giảm ROAS target để mở rộng phân phối
// acos_target: ACOS mục tiêu (%) — dùng tính CPA = acos% × giá bán
// ══════════════════════════════════════════════════════════════════
const PRODUCT_GROUPS = {
  // [R5] roas_max cập nhật theo data thực tế:
  //   Giày dép  thực tế 11–27x → roas_max 20 (không đề xuất giảm target khi ROAS < 20x)
  //   TB làm đẹp thực tế 10–18x → roas_max 18
  thiet_bi_lam_dep: { name: 'Thiết bị làm đẹp', roas_min: 5,  roas_max: 18, net_margin: 15, acos_target: 8  },
  giay_dep:         { name: 'Giày dép',          roas_min: 5,  roas_max: 20, net_margin: 5,  acos_target: 5  },
  do_choi:          { name: 'Đồ chơi',           roas_min: 10, roas_max: 25, net_margin: 0,  acos_target: 10 },
  do_ngu:           { name: 'Đồ ngủ',            roas_min: 10, roas_max: 20, net_margin: 0,  acos_target: 10 },
};

// Chuẩn hoá giá trị cột NGÀNH trong MAP_SHOP_NGANH → group key
const NGANH_TO_KEY = {
  'DO CHOI':          'do_choi',
  'GIAY DEP':         'giay_dep',
  'TBCSSD':           'thiet_bi_lam_dep',
  'THIET BI LAM DEP': 'thiet_bi_lam_dep',
  'DO NGU':           'do_ngu',
  'SEXY':             'do_ngu',
};

// Dự phòng cứng — shop chưa có trong MAP_SHOP_NGANH
const SHOP_FALLBACK = {
  'Allienia Sexy Fasshion':         'do_ngu',
  'Luccia Store - Đồ ngủ cosplay':  'do_ngu',
  'Claudia Beauty':                 'thiet_bi_lam_dep',
  'Olivia Beauty Care':             'thiet_bi_lam_dep',
  'beauty store 1811':              'thiet_bi_lam_dep',
  'Babychill VN':                   'do_choi',
  'TB - Lazada - Claudia Beauty - 200210598145':                'thiet_bi_lam_dep',
  'TB - Lazada - Olivia Beauty Care - 200200464254':            'thiet_bi_lam_dep',
  'TB - Lazada - Royal Spa - 200557728981':                     'thiet_bi_lam_dep',
  'TB - Lazada - beauty store 1811 - 200557216279':             'thiet_bi_lam_dep',
  'DC - TIKTOK - VN - Babychill VN - 7494165771759879270':      'do_choi',
  'SEXY - Shopee - Allienia Sexy Fasshion - 799755173':         'do_ngu',
  'SEXY - Shopee - Luccia Store - Do ngu cosplay - 876035401':  'do_ngu',
};

// ══════════════════════════════════════════════════════════════════
// DECISION RULES
// ══════════════════════════════════════════════════════════════════
const RULES = {
  // ── PAUSE ───────────────────────────────────────────────────────
  pause_spend_pct_of_price:   0.10,   // P1: đã tiêu ≥ 10% giá bán mà 0 đơn
  pause_p2_min_spend:         20000,  // P2a: spend tối thiểu để kết luận thất bại
  pause_zero_order_days:      14,     // P2a/CVR: ngày tối thiểu
  pause_long_run_days:        30,     // P2b: 30+ ngày 0 đơn
  pause_roas_p3:              5,      // P3: ROAS < 5x → đang lỗ
  // ── SCALE UP ────────────────────────────────────────────────────
  acos_warning_fallback:      10,
  scale_roas_multiplier:      1.5,    // ROAS ≥ roas_min × 1.5 → scale thường
  scale_high_roas_multiplier: 3,      // ROAS ≥ roas_min × 3   → scale mạnh
  scale_min_conversions:      2,
  scale_min_spend:            30000,  // [v3] giảm từ 50k→30k: giày dép giá thấp đủ data sớm hơn
  scale_high_roas_min_conv:   1,
  scale_high_roas_min_spend:  10000,
  scale_min_stock_days:       14,
  // ── CTR / CVR ───────────────────────────────────────────────────
  ctr_bad:        1.2,  ctr_ok:  2.0,
  cvr_bad:        2.5,  cvr_ok:  5.0,
  cvr_min_clicks: 10,
  // ── ROAS TARGET ADJUSTMENT ─────────────────────────────────────
  roas_adj_increase:  0.5,
  roas_adj_decrease:  0.5,
  giam_roas_min_days: 3,
  // ── [R6] ROAS TARGET QUÁ CAO ───────────────────────────────────
  // Khi roas_target > roas_max × high_target_multiplier VÀ spend gần 0 → cảnh báo đặt target sai
  high_target_multiplier: 2,       // target > roas_max × 2 = quá cao
  near_zero_spend:        5000,    // spend < 5.000đ sau nhiều ngày = "gần như không phân phối"
  high_target_min_days:   7,       // đã chạy ≥ 7 ngày mới cảnh báo
};

// ══════════════════════════════════════════════════════════════════
// MENU
// ══════════════════════════════════════════════════════════════════
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Shopee Campain')
    .addItem('📊  Tính toán & Duyệt', 'buildAIDecisionTab')
    .addItem('🗑  Xoá bảng duyệt',    'clearDecisionTab')
    .addSeparator()
    .addItem('ℹ  Hướng dẫn',          'showHelp')
    .addToUi();
}

// ══════════════════════════════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════════════════════════════
function buildAIDecisionTab() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  const campSheet    = findSheetByKeyword(ss, CONFIG.CAMPAIGN_SHEET);
  const productSheet = findSheetByKeyword(ss, CONFIG.PRODUCT_SHEET);
  if (!campSheet || !productSheet) {
    ui.alert('❌ Không tìm thấy sheet!\nCần tab chứa "' + CONFIG.CAMPAIGN_SHEET + '" và "' + CONFIG.PRODUCT_SHEET + '"');
    return;
  }

  const shopMaps   = buildShopMaps(ss);
  const campRaw    = campSheet.getDataRange().getValues();
  const productRaw = productSheet.getDataRange().getValues();
  const campCol    = buildColIndex(campRaw[0]);
  const prodHdrIdx = findHeaderRow(productRaw, 'MÃ SẢN PHẨM - SÀN');
  const productCol = buildColIndex(productRaw[prodHdrIdx]);

  const campAgg    = aggregateCampaigns(campRaw, campCol);   // [R2] bao gồm flag trùng item_id
  const productMap = buildProductMap(productRaw, productCol, shopMaps);
  const rows       = buildDecisionRows(campAgg, productMap, shopMaps);
  addLaunchCandidates(rows, productMap, campAgg);             // [R4] guard tồn kho
  writeDecisionTab(ss, rows);

  const pauseCount = rows.filter(r => r.ai_action === 'PAUSE').length;
  const scaleCount = rows.filter(r => r.ai_action === 'SCALE_UP').length;
  ui.alert(
    '✅ Hoàn tất! ' + rows.length + ' dòng đã phân tích.\n\n' +
    '🔴 PAUSE: ' + pauseCount + ' camp cần tắt\n' +
    '🟢 SCALE_UP: ' + scaleCount + ' camp cần đẩy ngân sách\n\n' +
    'Mở tab "' + CONFIG.DECISION_SHEET + '" để xem chi tiết.'
  );
}

// ══════════════════════════════════════════════════════════════════
// ĐỌC MAP_SHOP_NGANH → shortName + fullName lookup
// ══════════════════════════════════════════════════════════════════
function buildShopMaps(ss) {
  const fullMap  = Object.assign({}, SHOP_FALLBACK);
  const shortMap = Object.assign({}, SHOP_FALLBACK);

  const mapSheet = ss.getSheetByName(CONFIG.MAP_SHOP_SHEET);
  if (!mapSheet) return { fullName: fullMap, shortName: shortMap };

  const data = mapSheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    const fullRaw  = String(data[i][0] || '').trim();
    const nganhRaw = String(data[i][1] || '').trim();
    if (!fullRaw || !nganhRaw) continue;

    const nganhNorm = nganhRaw.toUpperCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/\u0111/gi, 'd').replace(/Đ/gi, 'D');

    let groupKey = null;
    for (const [k, v] of Object.entries(NGANH_TO_KEY)) {
      if (nganhNorm === k || nganhNorm.startsWith(k)) { groupKey = v; break; }
    }
    if (!groupKey) continue;

    fullMap[fullRaw] = groupKey;

    // Trích tên ngắn: "PREFIX - PLATFORM - TÊN - ID_SỐ"
    const parts = fullRaw.split(' - ');
    if (parts.length >= 4) {
      const isId  = /^\d+$/.test(parts[parts.length - 1].trim());
      const short = (isId ? parts.slice(2, -1) : parts.slice(2)).join(' - ').trim();
      if (short) shortMap[short] = groupKey;
    } else if (parts.length === 3) {
      shortMap[parts[2].trim()] = groupKey;
    }
  }
  return { fullName: fullMap, shortName: shortMap };
}

// ══════════════════════════════════════════════════════════════════
// BƯỚC 1 — Tổng hợp campaign
// ══════════════════════════════════════════════════════════════════
function aggregateCampaigns(data, col) {
  const today = new Date();
  today.setHours(23, 59, 59, 0);
  const agg = {};

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const status = String(row[col['Trạng thái']] || '').trim();
    if (status.toLowerCase() !== 'đang diễn ra') continue;

    const itemId = String(row[col['Item ID sản phẩm']] || '').trim();
    if (!itemId || !/^\d{5,}$/.test(itemId)) continue;

    const campId   = String(row[col['ID Quảng cáo']]    || '').trim();
    const tenSp    = String(row[col['Tên sản phẩm']]    || '').trim();
    const gianHang = String(row[col['Gian hàng']]       || '').trim();
    const roasTgt  = toNum(row[col['Mục tiêu ROAS']]);
    const key      = campId || itemId;

    if (!agg[key]) {
      const thoiGian = String(row[col['Thời gian diễn ra']] || '');
      const rawStart = thoiGian.split('~')[0].trim();
      const startDt  = parseDate(rawStart);
      const ngayChay = startDt ? Math.ceil((today - startDt) / 86400000) : 0;
      agg[key] = {
        item_id: itemId, camp_id: campId, ten_sp_camp: tenSp,
        gian_hang: gianHang, roas_target: roasTgt,
        chi_phi: 0, doanh_thu: 0,
        luot_xem: 0, luot_click: 0,
        chuyen_doi: 0, don_hang: 0,
        ngay_chay: ngayChay,
        has_duplicate: false,   // [R2] flag trùng item_id
      };
    }

    const a = agg[key];
    a.chi_phi    += toNum(row[col['Chi phí quảng cáo']]);
    a.doanh_thu  += toNum(row[col['Doanh thu bán hàng']]);
    a.luot_xem   += toNum(row[col['Số lượt xem']]);
    a.luot_click += toNum(row[col['Số lượt click']]);
    a.chuyen_doi += toNum(row[col['Chuyển đổi']]);
    const spBan   = row[col['Sản phẩm đã bán']];
    a.don_hang   += (spBan !== undefined && spBan !== null && spBan !== '')
      ? toNum(spBan) : toNum(row[col['Chuyển đổi']]);
  }

  // Tính chỉ số phái sinh
  Object.values(agg).forEach(a => {
    a.roas_7d = a.chi_phi    > 0 ? round2(a.doanh_thu  / a.chi_phi)       : 0;
    a.acos_7d = a.doanh_thu  > 0 ? round2(a.chi_phi    / a.doanh_thu * 100) : 999;
    a.ctr_7d  = a.luot_xem   > 0 ? round2(a.luot_click / a.luot_xem  * 100) : 0;
    a.cvr_7d  = a.luot_click > 0 ? round2(a.chuyen_doi / a.luot_click* 100) : 0;
  });

  // [R2] Đánh dấu các item_id xuất hiện nhiều hơn 1 campaign
  const itemIdCount = {};
  Object.values(agg).forEach(a => {
    itemIdCount[a.item_id] = (itemIdCount[a.item_id] || 0) + 1;
  });
  Object.values(agg).forEach(a => {
    if (itemIdCount[a.item_id] > 1) a.has_duplicate = true;
  });

  return agg;
}

// ══════════════════════════════════════════════════════════════════
// BƯỚC 2 — Build product map
// ══════════════════════════════════════════════════════════════════
function buildProductMap(data, col, shopMaps) {
  const map = {};
  for (let i = 1; i < data.length; i++) {
    const row    = data[i];
    const itemId = String(row[col['MÃ SẢN PHẨM - SÀN']] || '').trim();
    if (!itemId || !/^\d{5,}$/.test(itemId)) continue;

    const tenShop = String(row[col['TÊN SHOP']] || '').trim();
    let nhomSp = shopMaps.fullName[tenShop] || null;
    if (!nhomSp && col['NHÓM SP'] !== undefined) {
      const v = String(row[col['NHÓM SP']] || '').trim();
      if (v && PRODUCT_GROUPS[v]) nhomSp = v;
    }
    if (!nhomSp) nhomSp = detectGroupFromName(String(row[col['TÊN SẢN PHẨM']] || ''), tenShop);

    const order = toNum(row[col['Order\n(sau hủy)']] || row[col['Order (sau hủy)']] || 0);
    const nr    = toNum(row[col['NR (doanh thu thuần sau huỷ)']] || 0);
    const gv    = toNum(row[col['GIÁ VỐN\n(1 SP)']] || row[col['GIÁ VỐN (1 SP)']] || row[col['GIÁ VỐN']] || 0);
    let giaBan  = 0;
    if (order > 0 && nr > 0) giaBan = round0(nr / order);
    else if (gv > 0)         giaBan = round0(gv / 0.80);

    const tocDo  = toNum(row[col['TỐC ĐỘ BÁN 30 NGÀY SAU HỦY']] || row[col['TỐC ĐỘ BÁN']] || 0);
    const profit = toNum(row[col['Profit (sau cùng)']] || row[col['Profit']] || 0);
    const tonKho = toNum(row[col['TỒN KHO']] || 0);

    map[itemId] = {
      item_id: itemId, ten_sp: String(row[col['TÊN SẢN PHẨM']] || ''),
      ten_shop: tenShop, gia_von: gv, gia_ban: giaBan,
      ton_kho: tonKho, toc_do_ban: tocDo,
      profit: profit,
      roi: toNum(row[col['ROI (NR / tổng cost)']] || row[col['ROI']] || 0),
      nr: nr, order: order, nhom_sp: nhomSp,
    };
  }
  return map;
}

// ══════════════════════════════════════════════════════════════════
// BƯỚC 3 — Tạo decision rows
// ══════════════════════════════════════════════════════════════════
function buildDecisionRows(campAgg, productMap, shopMaps) {
  const rows = [];

  Object.values(campAgg).forEach(camp => {
    const prod   = productMap[camp.item_id] || {};
    const nhomKey = prod.nhom_sp || shopMaps.shortName[camp.gian_hang] || null;
    const unknown = !nhomKey || !PRODUCT_GROUPS[nhomKey];
    const group   = PRODUCT_GROUPS[nhomKey] || PRODUCT_GROUPS['thiet_bi_lam_dep'];
    const giaBan  = prod.gia_ban || 0;
    const roasHV  = group.net_margin > 0 ? round2(100 / group.net_margin) : null;
    const tonKho  = (prod.ton_kho !== undefined && prod.ton_kho !== null) ? prod.ton_kho : null;

    const dec = classifyCampaign({
      roas_7d: camp.roas_7d, acos_7d: camp.acos_7d,
      ctr_7d:  camp.ctr_7d,  cvr_7d:  camp.cvr_7d,
      luot_click: camp.luot_click, luot_xem: camp.luot_xem,
      don_hang_7d: camp.don_hang, chuyen_doi_total: camp.chuyen_doi,
      chi_phi_7d: camp.chi_phi, chi_phi_total: camp.chi_phi,
      doanh_thu_7d: camp.doanh_thu, ngay_chay: camp.ngay_chay,
      gia_ban: giaBan, group: group,
      roas_target: camp.roas_target,
      ton_kho: tonKho !== null ? tonKho : -999,  // -999 = không có data
      toc_do_ban: prod.toc_do_ban || 0,
      has_duplicate: camp.has_duplicate,           // [R2]
    });

    const nhomDisp = unknown ? ('⚠️ ' + group.name + '?') : group.name;
    let reason = dec.reason;
    let detail = dec.detail || '';
    if (unknown) {
      reason = '⚠️ [Nhóm SP chưa xác định — dùng ngưỡng TB làm đẹp] ' + reason;
      detail = detail + '\n📌 Thêm "' + camp.gian_hang + '" vào tab MAP_SHOP_NGANH.';
    }

    rows.push({
      item_id: camp.item_id, ten_sp: prod.ten_sp || camp.ten_sp_camp,
      nhom_sp: nhomDisp, gian_hang: camp.gian_hang,
      gia_ban_est: giaBan || '',
      gia_von: prod.gia_von || '',
      ton_kho: tonKho !== null ? tonKho : '',
      profit: prod.profit || '', roi: prod.roi || '',
      camp_id: camp.camp_id,
      roas_target_now: camp.roas_target,
      roas_target_nen: group.roas_min + '–' + group.roas_max,
      chi_phi: camp.chi_phi, doanh_thu: camp.doanh_thu,
      roas_7d: camp.roas_7d, acos_7d: camp.acos_7d,
      luot_xem: camp.luot_xem, luot_click: camp.luot_click,
      ctr_7d: camp.ctr_7d, chuyen_doi: camp.chuyen_doi,
      cvr_7d: camp.cvr_7d, ngay_chay: camp.ngay_chay,
      roas_hoa_von: roasHV,
      ai_action: dec.action, ai_urgency: dec.urgency,
      ai_reason: reason, ai_detail: detail,
      phe_duyet: 'CHỜ XEM', da_thuc_thi: false, ghi_chu_kd: '',
    });
  });

  const filtered = CONFIG.HIDE_OK
    ? rows.filter(r => r.ai_action !== 'GIỮ NGUYÊN' && r.ai_action !== 'THEO DÕI')
    : rows;

  const urgOrd = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  filtered.sort((a, b) => (urgOrd[a.ai_urgency] || 2) - (urgOrd[b.ai_urgency] || 2));
  return filtered;
}

// ══════════════════════════════════════════════════════════════════
// BƯỚC 4 — CHẠY MỚI [R4 guard tồn kho]
// ══════════════════════════════════════════════════════════════════
function addLaunchCandidates(rows, productMap, campAgg) {
  const existingIds = new Set(Object.values(campAgg).map(c => c.item_id));
  const candidates  = Object.values(productMap)
    .filter(p => !existingIds.has(p.item_id) && typeof p.profit === 'number' && p.profit > 0)
    .sort((a, b) => (b.profit || 0) - (a.profit || 0))
    .slice(0, CONFIG.MAX_LAUNCH);

  candidates.forEach(prod => {
    const unknown  = !prod.nhom_sp || !PRODUCT_GROUPS[prod.nhom_sp];
    const group    = PRODUCT_GROUPS[prod.nhom_sp] || PRODUCT_GROUPS['thiet_bi_lam_dep'];
    const giaBan   = prod.gia_ban || 0;
    const acosPct  = group.acos_target || 10;
    const testBud  = giaBan > 0 ? round0(giaBan * acosPct / 100) : 0;
    const daily    = Math.max(100000, testBud);
    const rHV      = group.net_margin > 0 ? round2(100 / group.net_margin) : null;

    // [R4] Kiểm tra tồn kho tối thiểu = 7 ngày bán
    const minStockNeeded = prod.toc_do_ban > 0
      ? Math.ceil(prod.toc_do_ban * 7 / 30)
      : 3; // fallback: cần ít nhất 3 đơn trong kho
    const stockInsufficient = prod.ton_kho !== undefined && prod.ton_kho < minStockNeeded;

    if (stockInsufficient) {
      // Không đủ hàng → đề xuất bổ sung kho trước
      rows.push({
        item_id: prod.item_id, ten_sp: prod.ten_sp,
        nhom_sp: unknown ? ('⚠️ ' + group.name + '?') : group.name,
        gian_hang: prod.ten_shop,
        gia_ban_est: giaBan || '', gia_von: prod.gia_von,
        ton_kho: prod.ton_kho, profit: prod.profit, roi: prod.roi,
        camp_id: '', roas_target_now: '', roas_target_nen: group.roas_min + '–' + group.roas_max,
        chi_phi: 0, doanh_thu: 0, roas_7d: 0, acos_7d: 0,
        luot_xem: 0, luot_click: 0, ctr_7d: 0, chuyen_doi: 0, cvr_7d: 0, ngay_chay: 0,
        roas_hoa_von: rHV,
        ai_action: 'BỔ SUNG KHO', ai_urgency: 'MEDIUM',
        ai_reason: 'Profit = ' + formatVND(prod.profit) + 'đ > 0 nhưng kho chỉ còn ' +
                   prod.ton_kho + ' (cần ≥ ' + minStockNeeded + ' để mở campaign)',
        ai_detail: 'Bổ sung kho trước khi chạy QC. Tốc độ bán: ' + prod.toc_do_ban +
                   ' đơn/tháng → cần ≥ ' + minStockNeeded + ' đơn trong kho để đủ 7 ngày đầu chạy.',
        phe_duyet: 'CHỜ XEM', da_thuc_thi: false, ghi_chu_kd: '',
      });
      return;
    }

    rows.push({
      item_id: prod.item_id, ten_sp: prod.ten_sp,
      nhom_sp: unknown ? ('⚠️ ' + group.name + '?') : group.name,
      gian_hang: prod.ten_shop,
      gia_ban_est: giaBan || '', gia_von: prod.gia_von,
      ton_kho: prod.ton_kho, profit: prod.profit, roi: prod.roi,
      camp_id: '', roas_target_now: '', roas_target_nen: group.roas_min + '–' + group.roas_max,
      chi_phi: 0, doanh_thu: 0, roas_7d: 0, acos_7d: 0,
      luot_xem: 0, luot_click: 0, ctr_7d: 0, chuyen_doi: 0, cvr_7d: 0, ngay_chay: 0,
      roas_hoa_von: rHV,
      ai_action: 'CHẠY MỚI', ai_urgency: 'MEDIUM',
      ai_reason: (unknown ? '⚠️ [Nhóm SP chưa xác định] ' : '') +
                 'Profit = ' + formatVND(prod.profit) + 'đ > 0, chưa có campaign',
      ai_detail: 'Ngân sách thử = ' + acosPct + '% × ' + formatVND(giaBan) + 'đ = ' +
                 formatVND(testBud) + 'đ/đơn. Ngân sách ngày Shopee: ' + formatVND(daily) +
                 'đ. ROAS target đặt: ' + group.roas_min,
      phe_duyet: 'CHỜ XEM', da_thuc_thi: false, ghi_chu_kd: '',
    });
  });
}

// ══════════════════════════════════════════════════════════════════
// BƯỚC 5 — Ghi tab DUYỆT CAMPAIN
// ══════════════════════════════════════════════════════════════════
function writeDecisionTab(ss, rows) {
  let sheet = ss.getSheetByName(CONFIG.DECISION_SHEET);
  if (sheet) {
    const f = sheet.getFilter(); if (f) f.remove();
    sheet.clearContents(); sheet.clearFormats();
  } else {
    sheet = ss.insertSheet(CONFIG.DECISION_SHEET);
  }

  const HEADERS = [
    'item_id','Tên sản phẩm','Nhóm SP','Gian hàng',
    'Giá bán (est)','Giá vốn','Tồn kho','Profit','ROI',
    'Camp ID','ROAS target hiện tại','ROAS target nên đặt',
    'Chi phí (28d)','Doanh thu (28d)','ROAS thực','ACOS (%)',
    'Lượt xem','Lượt click','CTR (%)','Chuyển đổi','CVR (%)','Ngày chạy',
    'ROAS hòa vốn',
    '🤖 Hành động AI','⚡ Mức độ','📋 Lý do','💡 Chi tiết',
    '✅ Phê duyệt','🚀 Đã thực thi','📝 Ghi chú KD',
  ];
  const FIELDS = [
    'item_id','ten_sp','nhom_sp','gian_hang',
    'gia_ban_est','gia_von','ton_kho','profit','roi',
    'camp_id','roas_target_now','roas_target_nen',
    'chi_phi','doanh_thu','roas_7d','acos_7d',
    'luot_xem','luot_click','ctr_7d','chuyen_doi','cvr_7d','ngay_chay',
    'roas_hoa_von',
    'ai_action','ai_urgency','ai_reason','ai_detail',
    'phe_duyet','da_thuc_thi','ghi_chu_kd',
  ];

  const hdr = sheet.getRange(1, 1, 1, HEADERS.length);
  hdr.setValues([HEADERS]);
  hdr.setFontWeight('bold').setBackground('#1F3864').setFontColor('#FFFFFF').setFontSize(10);

  if (rows.length > 0) {
    const mat = rows.map(r => FIELDS.map(f => r[f] === null || r[f] === undefined ? '' : r[f]));
    sheet.getRange(2, 1, mat.length, HEADERS.length).setValues(mat);
  }

  const actionIdx  = FIELDS.indexOf('ai_action')  + 1;
  const reasonIdx  = FIELDS.indexOf('ai_reason')  + 1;
  const detailIdx  = FIELDS.indexOf('ai_detail')  + 1;
  const approvalIdx= FIELDS.indexOf('phe_duyet')  + 1;

  // Thêm cột DUPLICATE ALERT với màu riêng
  const dupColor = '#F3E5F5'; // tím nhạt

  for (let i = 0; i < rows.length; i++) {
    const r  = i + 2;
    const ug = rows[i].ai_urgency;
    const ac = rows[i].ai_action;
    let bg = '#FFFFFF';
    if (ug === 'HIGH')              bg = '#FDECEA'; // đỏ nhạt
    else if (ac === 'GIỮ NGUYÊN')  bg = '#E8F5E9'; // xanh lá
    else if (ac === 'CHẠY MỚI')    bg = '#E3F2FD'; // xanh dương
    else if (ac === 'BỔ SUNG KHO') bg = '#FFF3E0'; // cam
    else if (ug === 'MEDIUM')       bg = '#FFF8E1'; // vàng
    // [R2] trùng item_id → tím nhạt (ghi đè nếu MEDIUM/LOW)
    if (rows[i].ai_detail && rows[i].ai_detail.indexOf('BID CHỐNG NHAU') > -1 && ug !== 'HIGH') {
      bg = dupColor;
    }
    sheet.getRange(r, 1, 1, HEADERS.length).setBackground(bg);
    sheet.getRange(r, actionIdx).setFontWeight('bold');
  }

  if (rows.length > 0) {
    const dv = SpreadsheetApp.newDataValidation()
      .requireValueInList(['CHỜ XEM','DUYỆT','BỎ QUA'], true)
      .setAllowInvalid(false).build();
    sheet.getRange(2, approvalIdx, rows.length, 1).setDataValidation(dv);
  }

  sheet.setFrozenRows(1); sheet.setFrozenColumns(2);
  sheet.getRange(1, reasonIdx, rows.length + 1, 1).setWrap(true);
  sheet.getRange(1, detailIdx, rows.length + 1, 1).setWrap(true);
  sheet.autoResizeColumns(1, HEADERS.length);
  sheet.setColumnWidth(FIELDS.indexOf('ten_sp')    + 1, 200);
  sheet.setColumnWidth(FIELDS.indexOf('gian_hang') + 1, 220);
  sheet.setColumnWidth(reasonIdx, 360);
  sheet.setColumnWidth(detailIdx, 320);

  if (rows.length > 0) {
    sheet.getRange(1, 1, rows.length + 1, HEADERS.length).createFilter();
  }
  ss.setActiveSheet(sheet);
}

// ══════════════════════════════════════════════════════════════════
// DECISION LOGIC v3 — phân loại từng campaign
// ══════════════════════════════════════════════════════════════════
function classifyCampaign(p) {
  const { roas_7d, acos_7d, ctr_7d, cvr_7d, luot_click, luot_xem,
          don_hang_7d, chuyen_doi_total, chi_phi_7d, chi_phi_total,
          doanh_thu_7d, ngay_chay, gia_ban, group,
          roas_target, ton_kho, toc_do_ban, has_duplicate } = p;

  const acos_tgt  = group.acos_target || RULES.acos_warning_fallback;
  const cpa       = gia_ban > 0 ? round0(gia_ban * acos_tgt / 100) : 0;
  const sc_thr    = round2(group.roas_min * RULES.scale_roas_multiplier);
  const hi_thr    = round2(group.roas_min * RULES.scale_high_roas_multiplier);
  const p1        = gia_ban >= 50000
    ? Math.max(round0(gia_ban * RULES.pause_spend_pct_of_price), cpa)
    : null;

  // ─────────────────────────────────────────────────────────────────
  // [R1] STOCKOUT — kho ≤ 0 + đang tiêu tiền → PAUSE ngay
  // Lý do: Shopee không thể giao hàng → hoàn đơn → ảnh hưởng seller metrics
  // ─────────────────────────────────────────────────────────────────
  if (ton_kho !== -999 && ton_kho <= 0 && chi_phi_7d > 0) {
    return { action: 'PAUSE', urgency: 'HIGH',
      reason: '🚫 KHO ÂM/HẾT HÀNG: Tồn kho = ' + ton_kho + ' trong khi camp đang tiêu ' + formatVND(chi_phi_7d) + 'đ',
      detail: 'Tắt camp NGAY. Shopee không thể giao hàng → hoàn đơn → hại seller score.\n' +
              'Bổ sung kho xong mới chạy lại.' };
  }

  // ─────────────────────────────────────────────────────────────────
  // [R2] TRÙNG ITEM_ID — nhiều camp cùng 1 sản phẩm
  // Không PAUSE ngay, chỉ cảnh báo để gộp camp yếu hơn
  // ─────────────────────────────────────────────────────────────────
  // (Sẽ append vào detail bên dưới nếu has_duplicate = true)

  // ─────────────────────────────────────────────────────────────────
  // P1 — Chi phí ≥ 1 CPA nhưng 0 đơn
  // ─────────────────────────────────────────────────────────────────
  if (p1 && don_hang_7d === 0 && chi_phi_total >= p1) {
    const detail = 'Tắt camp. Đã cho đủ 1 CPA budget (' + formatVND(p1) + 'đ) nhưng không có chuyển đổi.' +
      (has_duplicate ? '\n⚠️ BID CHỐNG NHAU: Sản phẩm này có nhiều campaign đang chạy cùng lúc!' : '');
    return { action: 'PAUSE', urgency: 'HIGH',
      reason: 'Chi phí ' + formatVND(chi_phi_total) + 'đ ≥ 1 CPA mục tiêu (' + formatVND(p1) + 'đ), chưa có đơn',
      detail: detail };
  }

  // P2a
  if (ngay_chay >= RULES.pause_zero_order_days && don_hang_7d === 0 && chi_phi_7d >= RULES.pause_p2_min_spend)
    return { action: 'PAUSE', urgency: 'HIGH',
      reason: 'Chạy ' + ngay_chay + ' ngày không có đơn, đã tiêu ' + formatVND(chi_phi_7d) + 'đ',
      detail: 'Tắt campaign, xem lại sản phẩm hoặc creative.' +
              (has_duplicate ? '\n⚠️ BID CHỐNG NHAU: Sản phẩm này có nhiều campaign đang chạy!' : '') };

  // P2b
  if (ngay_chay >= RULES.pause_long_run_days && don_hang_7d === 0 && chi_phi_7d > 0)
    return { action: 'PAUSE', urgency: 'HIGH',
      reason: 'Chạy ' + ngay_chay + ' ngày không có đơn, tổng đã tiêu ' + formatVND(chi_phi_7d) + 'đ',
      detail: 'Camp quá dài không hiệu quả — tắt và xem lại toàn bộ.' };

  // P3
  if (roas_7d > 0 && roas_7d < RULES.pause_roas_p3 && cpa > 0 && chi_phi_7d > cpa)
    return { action: 'PAUSE', urgency: 'HIGH',
      reason: 'ROAS = ' + roas_7d + 'x < ' + RULES.pause_roas_p3 + 'x, chi phí ' + formatVND(chi_phi_7d) + 'đ > CPA mục tiêu ' + formatVND(cpa) + 'đ',
      detail: 'Tắt camp. Thử lại: đặt ROAS target = ' + round2(100 / acos_tgt) + ' (= 100÷' + acos_tgt + '%) và kiểm tra creative/giá' };

  // ─────────────────────────────────────────────────────────────────
  // [R3] KHÔNG CẮN TIỀN — phân biệt 3 case
  // ─────────────────────────────────────────────────────────────────
  if (chi_phi_7d === 0 || chi_phi_7d < RULES.near_zero_spend) {
    // Case A: Quá sớm (< 3 ngày) → chờ thêm
    if (ngay_chay < RULES.giam_roas_min_days) {
      return { action: 'THEO DÕI', urgency: 'LOW',
        reason: 'Camp mới chạy ' + ngay_chay + ' ngày, chưa đủ dữ liệu để kết luận',
        detail: 'Shopee cần 3–7 ngày để tối ưu phân phối ban đầu. Kiểm tra lại sau 1 tuần.' };
    }

    // [R6] Case B: ROAS target quá cao so với nhóm SP
    if (roas_target > 0 && roas_target > group.roas_max * RULES.high_target_multiplier
        && ngay_chay >= RULES.high_target_min_days) {
      const suggestTarget = group.roas_min + Math.round((group.roas_max - group.roas_min) / 2);
      return { action: 'GIẢM ROAS TARGET', urgency: 'HIGH',
        reason: '🔴 ROAS TARGET QUÁ CAO: Target = ' + roas_target + 'x trong khi nhóm ' + group.name + ' chỉ cần ' + group.roas_min + '–' + group.roas_max + 'x',
        detail: 'Shopee không thể đấu thầu với target ' + roas_target + 'x → gần như 0 phân phối sau ' + ngay_chay + ' ngày.\n' +
                'Giảm ROAS target về ' + suggestTarget + '–' + (group.roas_min + 2) + ' (= 1–2 trên roas_min của nhóm).\n' +
                'Sau 2 tuần nếu ROAS thực > ' + group.roas_max + 'x ổn định mới cân nhắc tăng target lại.' };
    }

    // Case C: Target hợp lý nhưng vẫn không spend → xem xét sản phẩm
    if (ngay_chay >= RULES.pause_zero_order_days && luot_xem === 0) {
      return { action: 'GIẢM ROAS TARGET', urgency: 'MEDIUM',
        reason: 'Camp chạy ' + ngay_chay + ' ngày, 0 lượt xem, 0 chi phí — Shopee không đấu thầu được',
        detail: 'Nguyên nhân có thể: (1) Target vẫn còn cao → giảm thêm −' + RULES.roas_adj_decrease + '; ' +
                '(2) Sản phẩm bị ẩn/hết hàng; (3) Listing bị vi phạm chính sách.\n' +
                'Kiểm tra trạng thái listing trên Shopee Seller Center.' };
    }

    // Default: target cao, giảm nhẹ
    if (ngay_chay >= RULES.giam_roas_min_days) {
      return { action: 'GIẢM ROAS TARGET', urgency: 'MEDIUM',
        reason: 'Camp chạy ' + ngay_chay + ' ngày chưa cắn tiền — ROAS target đang đặt quá cao so với thị trường',
        detail: 'Giảm ROAS target −' + RULES.roas_adj_decrease + '. Nếu sau 3 ngày vẫn không phân phối, tiếp tục giảm thêm.\n' +
                'Mục tiêu: target ở mức roas_min + 1–2 của nhóm (' + (group.roas_min + 1) + '–' + (group.roas_min + 2) + 'x)' };
    }
  }

  // Tồn kho check (trước SCALE_UP)
  const stockOk   = (toc_do_ban <= 0 || ton_kho === -999 || ton_kho <= 0) ? true
    : ton_kho >= (toc_do_ban / 30) * RULES.scale_min_stock_days;
  const stockNote = stockOk ? ''
    : ' ⚠️ Kho còn ' + ton_kho + ' (< ' + Math.ceil((toc_do_ban/30)*RULES.scale_min_stock_days) + ' cần cho 14 ngày) — bổ sung kho trước khi scale!';
  const dupNote   = has_duplicate ? '\n⚠️ BID CHỐNG NHAU: Có nhiều campaign cùng SP này — gộp camp yếu hơn để tránh tự bid giá lẫn nhau.' : '';

  // SCALE_UP high ROAS
  if (roas_7d >= hi_thr && chuyen_doi_total >= RULES.scale_high_roas_min_conv && chi_phi_7d >= RULES.scale_high_roas_min_spend)
    return { action: stockOk ? 'SCALE_UP' : 'BỔ SUNG KHO', urgency: 'MEDIUM',
      reason: 'ROAS = ' + roas_7d + 'x ≥ ' + hi_thr + 'x (tín hiệu cực mạnh = ' + RULES.scale_high_roas_multiplier + '× roas_min), ' + don_hang_7d + ' đơn, spend ' + formatVND(chi_phi_7d) + 'đ',
      detail: 'Tăng ngân sách × 2–3 lần. Giảm ROAS target −' + RULES.roas_adj_decrease + ' để mở rộng phân phối.' + stockNote + dupNote };

  // SCALE_UP normal
  if (roas_7d >= sc_thr && chuyen_doi_total >= RULES.scale_min_conversions && chi_phi_7d >= RULES.scale_min_spend)
    return { action: stockOk ? 'SCALE_UP' : 'BỔ SUNG KHO', urgency: 'MEDIUM',
      reason: 'ROAS = ' + roas_7d + 'x ≥ ' + sc_thr + 'x (' + RULES.scale_roas_multiplier + '× roas_min), ' + don_hang_7d + ' đơn, spend ' + formatVND(chi_phi_7d) + 'đ',
      detail: 'Tăng ngân sách +30–50%. Giảm ROAS target −' + RULES.roas_adj_decrease + ' để mở rộng tệp.' + stockNote + dupNote };

  // TĂNG ROAS TARGET (ACOS cao)
  if (doanh_thu_7d > 0 && acos_7d > acos_tgt)
    return { action: 'TĂNG ROAS TARGET', urgency: 'MEDIUM',
      reason: 'ACOS = ' + acos_7d + '% > ' + acos_tgt + '% (breakeven nhóm ' + group.name + ') — đang lỗ quảng cáo',
      detail: 'Tăng ROAS target +' + RULES.roas_adj_increase + '. Shopee sẽ bid thấp hơn → giảm chi tiêu → cải thiện ACOS về dưới ' + acos_tgt + '%.' + dupNote };

  // CTR thấp
  if (ctr_7d > 0 && ctr_7d < RULES.ctr_bad && roas_7d < group.roas_min)
    return { action: 'XEM LẠI CREATIVE', urgency: 'MEDIUM',
      reason: 'CTR = ' + ctr_7d + '% < ' + RULES.ctr_bad + '% — người thấy ads nhưng không click (ROAS ' + roas_7d + 'x < ' + group.roas_min + 'x)',
      detail: 'Cải thiện: (1) Ảnh bìa rõ nét, thấy giá, nổi bật; (2) Tiêu đề keyword + benefit rõ ràng; (3) Giá + voucher cạnh tranh chưa? CTR mục tiêu ≥' + RULES.ctr_ok + '%.' + dupNote };

  // CVR thấp
  if (luot_click >= RULES.cvr_min_clicks && cvr_7d < RULES.cvr_bad
      && ctr_7d >= RULES.ctr_bad && roas_7d < group.roas_min
      && ngay_chay >= RULES.pause_zero_order_days && chi_phi_7d >= RULES.pause_p2_min_spend)
    return { action: 'XEM LẠI TRANG SP', urgency: 'MEDIUM',
      reason: 'CTR = ' + ctr_7d + '% (ổn), ' + luot_click + ' click nhưng CVR = ' + (cvr_7d === 0 ? '0%' : cvr_7d + '%') + ' < ' + RULES.cvr_bad + '%',
      detail: 'Trang SP không thuyết phục. Kiểm tra: ảnh chi tiết đủ góc, mô tả + thông số, rating/đánh giá, giá so đối thủ. CVR mục tiêu ≥' + RULES.cvr_ok + '%.' + dupNote };

  // GIỮ NGUYÊN
  if (roas_7d >= group.roas_min && roas_7d <= group.roas_max) {
    const dupAction = has_duplicate ? 'XEM LẠI CAMP' : 'GIỮ NGUYÊN';
    return { action: dupAction, urgency: has_duplicate ? 'MEDIUM' : 'LOW',
      reason: 'ROAS = ' + roas_7d + 'x trong vùng mục tiêu [' + group.roas_min + '–' + group.roas_max + ']' + (has_duplicate ? ' — nhưng có camp trùng SP!' : ''),
      detail: 'Camp đang đúng mục tiêu. Theo dõi 7 ngày/lần.' + dupNote };
  }

  // GIẢM ROAS TARGET (vượt trần roas_max)
  if (roas_7d > group.roas_max)
    return { action: 'GIẢM ROAS TARGET', urgency: 'LOW',
      reason: 'ROAS = ' + roas_7d + 'x > trần ' + group.roas_max + 'x — Shopee đang bid rất conservative, bỏ lỡ traffic tiềm năng',
      detail: 'Giảm ROAS target −' + RULES.roas_adj_decrease + ' để mở rộng tệp tiếp cận. Camp đang sinh lời tốt — điều chỉnh nhẹ giúp tăng reach mà không giảm lợi nhuận.' + dupNote };

  // THEO DÕI (default)
  return { action: 'THEO DÕI', urgency: 'LOW',
    reason: 'ROAS = ' + roas_7d + 'x dưới mục tiêu ' + group.roas_min + 'x, chưa đủ dữ liệu (' + ngay_chay + ' ngày, ' + formatVND(chi_phi_7d) + 'đ)',
    detail: 'Thêm ' + Math.max(0, RULES.pause_zero_order_days - ngay_chay) + ' ngày hoặc khi spend đạt ' + formatVND(RULES.pause_p2_min_spend) + 'đ sẽ có kết luận rõ hơn.' + dupNote };
}

// ══════════════════════════════════════════════════════════════════
// KEYWORD FALLBACK
// ══════════════════════════════════════════════════════════════════
const GROUP_KEYWORDS = [
  { group: 'do_choi',  keywords: ['do choi','đồ chơi','toy','baby chill','bobby kid','kid center','xe điều khiển','lego','xếp hình','búp bê','cầu trượt','súng bắn','đất nặn','montessori'] },
  { group: 'do_ngu',   keywords: ['do ngu','đồ ngủ','váy ngủ','bộ ngủ','quần ngủ','đầm ngủ','pyjama','luccia','allienia','cosplay'] },
  { group: 'giay_dep', keywords: ['giày dép','giay dep','sandal','sneaker','loafer','giày thể thao','giày boot','giày bốt','dép sandal','dép bông','tất nữ','mary jane','belle studio','camcam','tachi','taoladyshoes','dahe','eling','gogoback','tiệm giày'] },
  { group: 'thiet_bi_lam_dep', keywords: ['máy rửa mặt','máy massage','máy sấy tóc','máy uốn tóc','máy cạo lông','bàn chải điện','trắng răng','vi kim','hút mụn','ngâm chân','triệt lông','CSSD','thiết bị làm đẹp','nâng cơ','giác hơi'] },
];

function detectGroupFromName(tenSp, tenShop) {
  const text = (tenSp + ' ' + tenShop).toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
  for (const rule of GROUP_KEYWORDS) {
    for (const kw of rule.keywords) {
      const k = kw.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd');
      if (text.includes(k)) return rule.group;
    }
  }
  return null;
}

// ══════════════════════════════════════════════════════════════════
// UTILITY
// ══════════════════════════════════════════════════════════════════
function findSheetByKeyword(ss, keyword) {
  const kw = keyword.toLowerCase();
  return ss.getSheets().find(s => s.getName().toLowerCase().includes(kw)) || null;
}

function buildColIndex(headerRow) {
  const idx = {};
  headerRow.forEach((h, i) => { if (h) idx[String(h).trim()] = i; });
  return idx;
}

function findHeaderRow(data, marker) {
  for (let i = 0; i < Math.min(data.length, 8); i++) {
    if (data[i].some(c => String(c || '').trim() === marker)) return i;
  }
  return 0;
}

function toNum(v) {
  if (v === null || v === undefined || v === '') return 0;
  if (typeof v === 'number') return isNaN(v) ? 0 : v;
  const n = parseFloat(String(v).replace(/,/g, '').replace(/%/g, '').trim());
  return isNaN(n) ? 0 : n;
}

function parseDate(v) {
  if (!v) return null;
  if (v instanceof Date) return v;
  const s = String(v).trim();
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2]-1, +m[3]);
  const m2 = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (m2) return new Date(+m2[3], +m2[2]-1, +m2[1]);
  const d = new Date(s); return isNaN(d.getTime()) ? null : d;
}

function round2(n) { return Math.round(n * 100) / 100; }
function round0(n) { return Math.round(n); }
function formatVND(n) { return Math.round(n || 0).toLocaleString('vi-VN'); }

// ══════════════════════════════════════════════════════════════════
// CLEAR & HELP
// ══════════════════════════════════════════════════════════════════
function clearDecisionTab() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.DECISION_SHEET);
  if (sheet) { sheet.clearContents(); SpreadsheetApp.getUi().alert('✅ Đã xoá tab ' + CONFIG.DECISION_SHEET); }
  else SpreadsheetApp.getUi().alert('Tab không tồn tại.');
}

function showHelp() {
  SpreadsheetApp.getUi().alert(
    'Shopee Campain v3 — Hướng dẫn\n\n' +
    'File cần đủ 3 tab:\n' +
    '  • ADS BIGSELLER ... (export từ Shopee)\n' +
    '  • 1.0 OVERVIEW PRODUCT E-COM\n' +
    '  • MAP_SHOP_NGANH\n\n' +
    'Chạy: menu Shopee Campain → 📊 Tính toán & Duyệt\n\n' +
    'Màu:\n' +
    '  🔴 Đỏ    = PAUSE (cần tắt ngay)\n' +
    '  🟡 Vàng  = Điều chỉnh (target, creative, trang SP)\n' +
    '  🔵 Xanh  = CHẠY MỚI\n' +
    '  🟠 Cam   = BỔ SUNG KHO\n' +
    '  🟣 Tím   = Trùng campaign (bid chống nhau)\n\n' +
    'v3 mới:\n' +
    '  [R1] Cảnh báo kho âm/hết hàng → PAUSE ngay\n' +
    '  [R2] Phát hiện nhiều camp cùng 1 SP\n' +
    '  [R3] Phân biệt "không cắn tiền" — target cao / SP yếu / quá sớm\n' +
    '  [R4] CHẠY MỚI chỉ khi tồn kho đủ 7 ngày\n' +
    '  [R5] roas_max cập nhật thực tế: giày 20x, TB làm đẹp 18x\n' +
    '  [R6] Cảnh báo ROAS target > 2× roas_max của nhóm\n\n' +
    'MAP_SHOP_NGANH — Cột NGÀNH nhận: ĐỒ CHƠI | GIÀY DÉP | TBCSSD | ĐỒ NGỦ'
  );
}
