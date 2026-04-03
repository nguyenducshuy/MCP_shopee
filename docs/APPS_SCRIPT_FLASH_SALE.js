/**
 * SHOPEE FLASH SALE — Google Apps Script v4
 *
 * Tab "FS": cột cố định theo thứ tự A→R (xem const COL).
 *   Tối thiểu cần: cột A (Shop), N (Mã SP Shopee), P (GIÁ SET FS), L (Tồn kho).
 * Tab "Setting": không dùng trong luồng chính — shop list lấy từ MCP (list_shops).
 *
 * Luồng chính:
 *   showShopPicker() → dialog chọn shop + nhập ngày (DD-MM-YYYY) → 2 nút
 *   Tạo FS → runCreateFS(shopString, targetDate) → callTool("plan_flash_sale") → writeCreateResults_()
 *   Xoá FS → runDeleteFS(shopString, targetDate) → callTool("delete_flash_sale_by_date")
 */

// ═══════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════
const CONFIG = {
  MCP_URL:           "https://incommunicable-inexplicably-jayden.ngrok-free.dev/mcp",
  MCP_API_KEY:       "",
  MAX_ITEMS_PER_SLOT: 10,
};

// ═══════════════════════════════════════════════════════════════
// CỘT CỐ ĐỊNH — thứ tự A→R (index 0-based)
// A  Shop | B  Mã SP | C  Tên SP | D  SKU SP | E  Mã PLH | F  Tên PLH
// G  SKU PLH | H  Giá gốc | I  Giá giảm | J  Giới hạn | K  Giá vốn
// L  Tồn kho | M  Lượt bán | N  Mã SP (Shopee) | O  Mã PLH (Shopee)
// P  GIÁ SET FS | Q  Kết quả | R  Tại sao
// ═══════════════════════════════════════════════════════════════
const COL = {
  shop:           0,   // A
  item_name:      2,   // C
  model_name:     5,   // F
  limit:          9,   // J
  stock:          11,  // L
  sales_velocity: 12,  // M
  item_id:        13,  // N — Shopee item ID
  model_id:       14,  // O — Shopee model ID
  fs_price:       15,  // P
  result:         16,  // Q
  reason:         17,  // R
};

// ═══════════════════════════════════════════════════════════════
// MENU
// ═══════════════════════════════════════════════════════════════
function onOpen() {
  try {
    SpreadsheetApp.getUi()
      .createMenu("Shopee FlashSale")
      .addItem("Chay Flash Sale...", "showShopPicker")
      .addToUi();
  } catch (_) {}
}

// ═══════════════════════════════════════════════════════════════
// DIALOG — chọn shop + nhập ngày + 2 nút
// ═══════════════════════════════════════════════════════════════
function showShopPicker() {
  // Đọc danh sách shop trực tiếp từ tab FS — không cần tab Setting.
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var fsSheet = ss.getSheetByName("FS");
  if (!fsSheet) { alert("Chưa có tab FS."); return; }

  // Chỉ đọc đến dòng cuối cùng thực sự có dữ liệu theo cột Shop (COL.shop = cột A), tránh ARRAYFORMULA kéo quá xa.
  var lastRow = getEffectiveLastRow_(fsSheet, COL.shop + 1);
  if (lastRow < 2) { SpreadsheetApp.getUi().alert("Tab FS trống."); return; }
  var lastCol = Math.max(fsSheet.getLastColumn(), COL.reason + 1);
  var allData = fsSheet.getRange(1, 1, lastRow, lastCol).getValues();

  // Single-pass: collect unique shop names theo thứ tự xuất hiện + thống kê
  var shopOrder = [];
  var shopStats = {};
  for (var i = 1; i < allData.length; i++) {
    var shopName = String(allData[i][COL.shop] || "").trim();
    if (!shopName) continue;
    if (!shopStats[shopName]) {
      shopStats[shopName] = { total: 0, eligible: 0 };
      shopOrder.push(shopName);
    }
    shopStats[shopName].total++;
    var stock   = toInt_(allData[i][COL.stock]);
    var fsPrice = toPrice_(allData[i][COL.fs_price]);
    var minStock = getMinStockRequired_(shopName);
    var stockOk = (stock !== null && stock >= minStock);
    if (fsPrice !== null && fsPrice > 0 && stockOk) {
      shopStats[shopName].eligible++;
    }
  }

  if (shopOrder.length === 0) { SpreadsheetApp.getUi().alert("Tab FS không có dòng nào có tên Shop."); return; }
  var shopNames = shopOrder;

  // Ngày mặc định = ngày mai DD-MM-YYYY
  var tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  var dd   = ("0" + tomorrow.getDate()).slice(-2);
  var mm   = ("0" + (tomorrow.getMonth() + 1)).slice(-2);
  var yyyy = tomorrow.getFullYear();
  var defaultDate = dd + "-" + mm + "-" + yyyy;

  var html = '<style>'
    + 'body{font-family:Arial,sans-serif;margin:0;padding:14px;background:#f8f9fa}'
    + 'h3{margin:0 0 10px;color:#1a73e8;font-size:15px}'
    + '.date-row{display:flex;align-items:center;gap:8px;margin-bottom:10px}'
    + '.date-row label{font-size:13px;font-weight:600;color:#333;white-space:nowrap}'
    + '.date-row input{flex:1;padding:7px 10px;border:2px solid #ddd;border-radius:6px;font-size:13px}'
    + '.date-row input:focus{border-color:#1a73e8;outline:none}'
    + '.shop-list{max-height:300px;overflow-y:auto}'
    + '.shop-btn{display:flex;align-items:center;justify-content:space-between;width:100%;padding:9px 12px;margin:3px 0;border:2px solid #ddd;border-radius:7px;background:white;cursor:pointer;font-size:13px;text-align:left;box-sizing:border-box}'
    + '.shop-btn:hover{border-color:#1a73e8}.shop-btn.selected{border-color:#1a73e8;background:#d2e3fc}'
    + '.sn{font-weight:600;color:#333;flex:1}'
    + '.badge{font-size:11px;padding:2px 7px;border-radius:10px;margin-left:6px;white-space:nowrap}'
    + '.b-ok{background:#e6f4ea;color:#137333}.b-no{background:#fce8e6;color:#c5221f}'
    + '.ck{margin-right:7px;font-size:15px;visibility:hidden}.selected .ck{visibility:visible}'
    + '.btn-group{position:sticky;bottom:0;background:#f8f9fa;padding-top:8px;border-top:1px solid #eee;margin-top:6px}'
    + '.sel-ct{font-size:12px;color:#1a73e8;text-align:center;margin-bottom:4px}'
    + '.abtn{width:100%;padding:11px;margin-top:5px;border:none;border-radius:7px;color:white;cursor:pointer;font-size:14px;font-weight:600}'
    + '.abtn:disabled{opacity:.5;cursor:not-allowed}'
    + '.btn-cr{background:#1a73e8}.btn-cr:hover:not(:disabled){background:#1557b0}'
    + '.btn-dl{background:#d93025}.btn-dl:hover:not(:disabled){background:#b3261e}'
    + '.sbtn{flex:1;padding:7px;border:1px solid #ddd;border-radius:6px;background:white;cursor:pointer;font-size:12px;color:#444}'
    + '.sbtn:hover{border-color:#1a73e8;color:#1a73e8}'
    + '</style><h3>Shopee Flash Sale</h3>'
    + '<div class="date-row"><label>Ngày FS:</label>'
    + '<input type="text" id="dt" value="' + defaultDate + '" placeholder="vd: ' + defaultDate + '"></div>'
    + '<div class="shop-list">';

  var btnParts = [];
  for (var j = 0; j < shopNames.length; j++) {
    var nm = shopNames[j];
    var st = shopStats[nm];
    btnParts.push('<button class="shop-btn" data-shop="' + escapeHtml_(nm) + '" onclick="toggle(this)">'
      + '<span class="ck">&#10003;</span>'
      + '<span class="sn">' + (j + 1) + '. ' + escapeHtml_(nm) + '</span>'
      + '<span class="badge ' + (st.eligible > 0 ? 'b-ok' : 'b-no') + '">'
      + st.eligible + '/' + st.total + '</span></button>');
  }
  html += btnParts.join('');

  html += '</div><div class="btn-group">'
    + '<div style="display:flex;gap:6px;margin-bottom:6px">'
    +   '<button class="sbtn" onclick="selAll()">Chọn tất cả</button>'
    +   '<button class="sbtn" onclick="deselAll()">Bỏ chọn tất cả</button>'
    + '</div>'
    + '<div class="sel-ct" id="ct">Chưa chọn shop</div>'
    + '<button class="abtn btn-cr" id="bc" disabled onclick="run(\'create\')">Đăng ký Flash Sale</button>'
    + '<button class="abtn btn-dl" id="bd" disabled onclick="run(\'delete\')">Xoá Flash Sale</button>'
    + '</div><script>'
    + 'var sel={};'
    + 'function toggle(e){var n=e.getAttribute("data-shop");'
    +   'if(sel[n]){delete sel[n];e.classList.remove("selected")}else{sel[n]=true;e.classList.add("selected")}upd()}'
    + 'function selAll(){var bs=document.querySelectorAll(".shop-btn");'
    +   'for(var i=0;i<bs.length;i++){sel[bs[i].getAttribute("data-shop")]=true;bs[i].classList.add("selected")}upd()}'
    + 'function deselAll(){sel={};var bs=document.querySelectorAll(".shop-btn");'
    +   'for(var i=0;i<bs.length;i++){bs[i].classList.remove("selected")}upd()}'
    + 'function upd(){var n=Object.keys(sel).length;'
    +   'document.getElementById("ct").textContent=n>0?"Đã chọn "+n+" shop":"Chưa chọn shop";'
    +   'document.getElementById("bc").disabled=!n;document.getElementById("bd").disabled=!n}'
    + 'function gs(){return Object.keys(sel).join("|||")}'
    + 'function gd(){var v=document.getElementById("dt").value.trim().replace(/[\\s\\/]/g,"-");'
    +   'if(!v){alert("Vui lòng nhập ngày.");return ""}'
    +   'if(!/^\\d{2}-\\d{2}-\\d{4}$/.test(v)){alert("Ngày phải có dạng DD-MM-YYYY (vd: 05-04-2026)");return ""}'
    +   'return v}'
    + 'function lock(m){document.getElementById("bc").disabled=true;document.getElementById("bd").disabled=true;'
    +   'var ct=document.getElementById("ct");ct.textContent=m;ct.style.color="#d93025"}'
    + 'function run(t){var d=gd();if(!d)return;var s=gs();'
    +   'lock("Đang xử lý...");'
    +   'if(t==="create"){'
    +     'google.script.run.withSuccessHandler(function(){google.script.host.close()})'
    +       '.withFailureHandler(function(e){lock("Lỗi: "+e.message)}).runCreateFS(s,d)'
    +   '}else{'
    +     'google.script.run.withSuccessHandler(function(){google.script.host.close()})'
    +       '.withFailureHandler(function(e){lock("Lỗi: "+e.message)}).runDeleteFS(s,d)'
    +   '}}'
    + '</script>';

  SpreadsheetApp.getUi().showModalDialog(
    HtmlService.createHtmlOutput(html).setWidth(460).setHeight(580),
    "Shopee Flash Sale"
  );
}

function escapeHtml_(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ═══════════════════════════════════════════════════════════════
// SERVER-SIDE HANDLERS
// ═══════════════════════════════════════════════════════════════

/**
 * Tạo Flash Sale cho nhiều shop trên cùng 1 ngày.
 * Gọi MCP tool "plan_flash_sale", nhận về kết quả và ghi vào sheet.
 */
function runCreateFS(shopString, targetDate) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var fsSheet = ss.getSheetByName("FS");
  if (!fsSheet) { alert("Chưa có tab FS."); return; }

  // Đọc đến dòng cuối thực sự có dữ liệu theo cột A (Shop), tránh ARRAYFORMULA kéo quá xa.
  var lastRow = getEffectiveLastRow_(fsSheet, COL.shop + 1);
  if (lastRow < 2) { alert("Tab FS không có dữ liệu."); return; }
  var lastCol = Math.max(fsSheet.getLastColumn(), COL.reason + 1);
  var allData = fsSheet.getRange(1, 1, lastRow, lastCol).getValues();

  // Registry từ MCP (gọi 1 lần, không cần tab Setting)
  var registry = loadShopRegistry_();
  var shopSet  = parseShopSet_(shopString);  // luôn non-null vì dialog gửi tên tường minh
  var shopsInSet = shopSet || {};

  // Lọc + dedupe + sort rows
  var seenKeys = {};
  var eligible = [];
  for (var i = 1; i < allData.length; i++) {
    var row = allData[i];
    var shopName = String(row[COL.shop] || "").trim();
    if (!shopName || !shopsInSet[shopName]) continue;

    var itemId = toInt_(row[COL.item_id]);
    if (itemId === null) continue;

    var fsPrice = toPrice_(row[COL.fs_price]);
    if (fsPrice === null || fsPrice <= 0) continue;

    var stock = toInt_(row[COL.stock]);  // null = #N/A hoặc rỗng → bỏ qua
    var minStock = getMinStockRequired_(shopName);
    if (stock === null || stock < minStock) continue;

    var modelId = toInt_(row[COL.model_id]);
    // Dedupe theo (shopName, item_id, model_id)
    var dedupeKey = shopName + "|" + itemId + "|" + (modelId || 0);
    if (seenKeys[dedupeKey]) continue;
    seenKeys[dedupeKey] = true;

    eligible.push({
      rowNum: i + 1,
      shopName: shopName,
      itemId: itemId,
      modelId: modelId,
      itemName:      String(row[COL.item_name]      || ""),
      modelName:     String(row[COL.model_name]     || ""),
      stock:         stock,
      salesVelocity: (toInt_(row[COL.sales_velocity]) || 0),
      fsPrice:       fsPrice,
      limit:         (toInt_(row[COL.limit]) || 0),
    });
  }

  if (eligible.length === 0) {
    alert("Không có dòng nào đủ điều kiện (cần Giá FS > 0, shop thường Tồn kho ≥ 3, shop ĐC Tồn kho ≥ 2).");
    return;
  }

  // Resolve shop_code từ MCP registry cho từng shop duy nhất trong eligible
  var seenShops = {};
  var shopsArr = [];
  eligible.forEach(function(e) {
    if (seenShops[e.shopName] !== undefined) return;
    var info = resolveShopInfo_(e.shopName, registry);
    seenShops[e.shopName] = info || null;
    if (info) shopsArr.push(info);
    else Logger.log("runCreateFS: khong resolve duoc shop '%s'", e.shopName);
  });
  eligible = eligible.filter(function(e) { return !!seenShops[e.shopName]; });

  if (shopsArr.length === 0) { alert("Không tìm được thông tin shop từ MCP registry."); return; }

  // Sort theo sales_velocity giảm dần
  eligible.sort(function(a, b) { return b.salesVelocity - a.salesVelocity; });

  var rows = eligible.map(function(e) {
    return {
      row_index:      e.rowNum,
      shop:           seenShops[e.shopName].shop_name,  // tên từ registry để MCP match chính xác
      item_id:        e.itemId,
      model_id:       e.modelId || 0,
      item_name:      e.itemName,
      model_name:     e.modelName,
      stock:          e.stock || 0,
      sales_velocity: e.salesVelocity,
      fs_price:       e.fsPrice,
      limit:          e.limit,
    };
  });

  var resp = unwrapResponse_(callTool("plan_flash_sale", {
    target_date: targetDate,
    shops:       shopsArr,
    rows:        rows,
  }));

  var errMsg = checkResp_(resp);
  if (errMsg) { alert("Lỗi MCP:\n" + errMsg); return; }

  writeCreateResults_(fsSheet, resp);
  flushMCPLogs_(resp.logs);

  var okCnt   = (resp && resp.selected_rows ? resp.selected_rows.length : 0);
  var skipCnt = (resp && resp.skipped_rows  ? resp.skipped_rows.length  : 0);
  alert("Kết quả:\nThành công: " + okCnt + " sản phẩm\nBỏ qua / Lỗi: " + skipCnt + " sản phẩm");
}

/**
 * Xoá tất cả phiên Flash Sale của các shop đã chọn trong ngày targetDate.
 */
function runDeleteFS(shopString, targetDate) {
  var registry  = loadShopRegistry_();
  var shopSet   = parseShopSet_(shopString);  // luôn non-null vì dialog gửi tên tường minh
  var shopNames = shopSet ? Object.keys(shopSet) : [];

  var shops = [];
  shopNames.forEach(function(name) {
    var info = resolveShopInfo_(name, registry);
    if (info) shops.push(info);
    else Logger.log("runDeleteFS: khong resolve duoc shop '%s'", name);
  });

  if (shops.length === 0) { alert("Không tìm được thông tin shop từ MCP registry."); return; }

  var resp = unwrapResponse_(callTool("delete_flash_sale_by_date", {
    target_date: targetDate,
    shops:       shops,
  }));

  var errMsg = checkResp_(resp);
  if (errMsg) { alert("Lỗi MCP:\n" + errMsg); return; }

  flushMCPLogs_(resp.logs);

  var deleted = resp && resp.deleted_sessions ? resp.deleted_sessions.length : 0;
  var failed  = resp && resp.failed_sessions  ? resp.failed_sessions.length  : 0;
  alert("Kết quả xóa:\nĐã xóa: " + deleted + " phiên\nLỗi: " + failed + " phiên");
}

// ═══════════════════════════════════════════════════════════════
// WRITE RESULTS — batch read→update→write (2 sheet calls per cột)
// ═══════════════════════════════════════════════════════════════

/**
 * Ghi kết quả từ plan_flash_sale vào cột "Kết quả" và "Tại sao".
 * Format:
 *   Thành công → Kết quả = "OK | DD-MM-YYYY | HH:mm | FS#..." | Tại sao = ""
 *   Thất bại   → Kết quả = "FAIL"                             | Tại sao = lý do lỗi
 * Dùng batch: đọc toàn bộ cột → cập nhật trong memory → ghi lại 1 lần.
 */
function writeCreateResults_(fsSheet, resp) {
  if (!resp) return;

  var updates = {};  // rowNum (1-based) → [resultText, reasonText]

  (resp.selected_rows || []).forEach(function(r) {
    var parts = ["OK"];
    if (r.slot_date) parts.push(r.slot_date);
    if (r.slot_time) parts.push(r.slot_time);
    parts.push("FS#" + r.flash_sale_id);
    updates[r.row_index] = [parts.join(" | "), ""];
  });

  (resp.skipped_rows || []).forEach(function(r) {
    updates[r.row_index] = ["FAIL", r.reason || ""];
  });

  if (Object.keys(updates).length === 0) return;

  var lastRow = fsSheet.getLastRow();
  if (lastRow < 2) return;
  var numDataRows = lastRow - 1;

  function batchWriteCol_(colIdx0, valIdx) {
    var range = fsSheet.getRange(2, colIdx0 + 1, numDataRows, 1);
    var vals = range.getValues();
    Object.keys(updates).forEach(function(rn) {
      var idx = Number(rn) - 2;
      if (idx >= 0 && idx < vals.length) vals[idx][0] = updates[rn][valIdx];
    });
    range.setValues(vals);
  }

  batchWriteCol_(COL.result, 0);
  batchWriteCol_(COL.reason, 1);
}


/**
 * Ghi resp.logs từ MCP vào tab "Log" — batch, không setValue từng ô.
 * Tự tạo tab nếu chưa có.
 */
function flushMCPLogs_(logs) {
  if (!logs || logs.length === 0) return;
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("Log");
  var hdr = ["Thoi gian", "Shop", "Item ID", "Model ID", "Action", "Status", "Message"];
  if (!sheet) {
    sheet = ss.insertSheet("Log");
    sheet.getRange(1, 1, 1, hdr.length)
         .setValues([hdr])
         .setFontWeight("bold")
         .setBackground("#2E75B6")
         .setFontColor("#FFF");
  }
  var now = Utilities.formatDate(new Date(), "Asia/Ho_Chi_Minh", "dd/MM/yyyy HH:mm:ss");
  var rows = logs.map(function(log) {
    return [
      now,
      log.shop     || "",
      log.item_id  || "",
      log.model_id || "",
      log.action   || "",
      log.status   || "",
      log.message  || "",
    ];
  });
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, hdr.length).setValues(rows);
}


// ═══════════════════════════════════════════════════════════════
// SHOP REGISTRY — từ MCP (không cần tab Setting)
// ═══════════════════════════════════════════════════════════════

/**
 * Gọi MCP list_shops → registry nhiều lớp để resolve shop bền hơn.
 */
function loadShopRegistry_() {
  var r = unwrapResponse_(callTool("list_shops", {}));
  var shops = (r && Array.isArray(r.shops)) ? r.shops : [];
  var byName = {}, byLower = {}, byId = {}, byNorm = {}, normPairs = [];

  shops.forEach(function(s) {
    if (!s || !s.shop_code) return;
    var info = { shop_code: s.shop_code, shop_name: s.shop_name, shop_id: s.shop_id };
    var name = String(s.shop_name || "").trim();
    if (name) {
      byName[name] = info;
      byLower[name.toLowerCase()] = info;
      var norm = normalizeShopName_(name);
      if (norm && !byNorm[norm]) byNorm[norm] = info;
      if (norm) normPairs.push({ norm: norm, info: info });
    }
    if (s.shop_id !== null && s.shop_id !== undefined && s.shop_id !== "") {
      byId[String(s.shop_id)] = info;
    }
  });

  return { byName: byName, byLower: byLower, byId: byId, byNorm: byNorm, normPairs: normPairs };
}

/**
 * Resolve shop info từ tên shop:
 * 1. Exact match (case-sensitive)
 * 2. Exact match (case-insensitive)
 * 3. Extract shopId từ cuối tên shop → byId lookup
 * 4. Normalized exact match
 * 5. Normalized match sau khi bỏ suffix shopId
 * 6. Unique contains match (chỉ khi ra đúng 1 kết quả)
 */
function resolveShopInfo_(shopName, registry) {
  var raw = String(shopName || "").trim();
  if (!raw) return null;

  if (registry.byName[raw]) return registry.byName[raw];
  var lower = raw.toLowerCase();
  if (registry.byLower[lower]) return registry.byLower[lower];

  var sid = extractShopId_(raw);
  if (sid && registry.byId[sid]) return registry.byId[sid];

  var norm = normalizeShopName_(raw);
  if (norm && registry.byNorm[norm]) return registry.byNorm[norm];

  var noId = stripShopIdSuffix_(raw);
  var normNoId = normalizeShopName_(noId);
  if (normNoId && registry.byNorm[normNoId]) return registry.byNorm[normNoId];

  var matches = [];
  var target = normNoId || norm;
  if (target) {
    for (var i = 0; i < registry.normPairs.length; i++) {
      var p = registry.normPairs[i];
      if (p.norm === target) return p.info;
      if (p.norm.indexOf(target) !== -1 || target.indexOf(p.norm) !== -1) {
        matches.push(p.info);
      }
    }
  }
  if (matches.length === 1) return matches[0];
  return null;
}

/**
 * Extract số 6+ chữ số ở cuối tên shop phân tách bởi dấu gạch/khoảng trắng.
 * Vd "TB - Shop - 847753176" → "847753176"
 */
function extractShopId_(name) {
  var parts = String(name).split(/[-–\s]+/);
  for (var i = parts.length - 1; i >= 0; i--) {
    var p = parts[i].trim();
    if (/^\d{6,}$/.test(p)) return p;
  }
  return null;
}

function stripShopIdSuffix_(name) {
  return String(name || "").replace(/\s*[-–]?\s*\d{6,}\s*$/, "").trim();
}

function normalizeShopName_(name) {
  return stripShopIdSuffix_(String(name || ""))
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/[^a-z0-9]+/g, "");
}

/** Parse shopString → Set object (null = tất cả). */
function isDCShop_(shopName) {
  shopName = String(shopName || "").trim().toUpperCase();
  return shopName.indexOf("ĐC") === 0;
}

function getMinStockRequired_(shopName) {
  return isDCShop_(shopName) ? 2 : 3;
}

function parseShopSet_(shopString) {
  if (!shopString || shopString === "__ALL__") return null;
  var set = {};
  shopString.split("|||").forEach(function(s) { var t = s.trim(); if (t) set[t] = true; });
  return Object.keys(set).length > 0 ? set : null;
}

/**
 * Dò dòng cuối cùng thực sự có dữ liệu theo 1 cột lõi (1-based), tránh đọc thừa do ARRAYFORMULA.
 */
function getEffectiveLastRow_(sheet, keyCol1Based) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return lastRow;
  var values = sheet.getRange(2, keyCol1Based, lastRow - 1, 1).getDisplayValues();
  for (var i = values.length - 1; i >= 0; i--) {
    if (String(values[i][0] || "").trim() !== "") return i + 2;
  }
  return 1;
}

// ═══════════════════════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════════════════════

function unwrapResponse_(r) {
  if (r && typeof r === "object" && !Array.isArray(r) && r.response !== undefined) return r.response;
  return r;
}

function checkResp_(r) {
  r = unwrapResponse_(r);
  if (r === null || r === undefined) return "null / timeout";
  if (typeof r === "string") return r.substring(0, 200);
  if (r && r.error) return summarizeError_(r);
  return null;
}

function summarizeError_(r) {
  r = unwrapResponse_(r);
  if (!r) return "null";
  if (r.error) return typeof r.error === "string" ? r.error.substring(0, 200) : JSON.stringify(r.error).substring(0, 200);
  if (r.message) return String(r.message).substring(0, 200);
  return JSON.stringify(r).substring(0, 200);
}

function isAlreadyOK_(v) { v = String(v).trim().toUpperCase(); return v === "OK" || v.indexOf("OK |") === 0; }
function toInt_(v)   { if (v === null || v === undefined || v === "" || v instanceof Error) return null; var n = Number(v); return isNaN(n) ? null : Math.floor(n); }
function toPrice_(v) { if (v === null || v === undefined || v === "" || v instanceof Error) return null; var n = Number(v); return isNaN(n) ? null : n; }
function alert(msg) { SpreadsheetApp.getUi().alert(String(msg)); }

// ═══════════════════════════════════════════════════════════════
// MCP CLIENT
// ═══════════════════════════════════════════════════════════════
var _mcpSessionId = null;
var _mcpCallId    = 0;

function callTool(toolName, args) {
  if (!_mcpSessionId) mcpInit_();
  var headers = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream, application/json",
  };
  if (_mcpSessionId) headers["Mcp-Session-Id"] = _mcpSessionId;
  if (CONFIG.MCP_API_KEY) headers["Authorization"] = "Bearer " + CONFIG.MCP_API_KEY;

  var payload = JSON.stringify({
    jsonrpc: "2.0",
    method:  "tools/call",
    params:  { name: toolName, arguments: args },
    id:      ++_mcpCallId,
  });

  for (var attempt = 0; attempt < 2; attempt++) {
    try {
      var resp = UrlFetchApp.fetch(CONFIG.MCP_URL, {
        method:           "post",
        headers:          headers,
        payload:          payload,
        muteHttpExceptions: true,
      });
      var rh = resp.getAllHeaders();
      if (rh["mcp-session-id"]) _mcpSessionId = rh["mcp-session-id"];
      var result = parseSSE_(resp.getContentText());
      if (result !== null) return result;
    } catch (e) {
      if (attempt === 1) return { error: e.message };
    }
  }
  return null;
}

function mcpInit_() {
  var headers = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream, application/json",
  };
  if (CONFIG.MCP_API_KEY) headers["Authorization"] = "Bearer " + CONFIG.MCP_API_KEY;
  try {
    var resp = UrlFetchApp.fetch(CONFIG.MCP_URL, {
      method:           "post",
      headers:          headers,
      muteHttpExceptions: true,
      payload:          JSON.stringify({
        jsonrpc: "2.0",
        method:  "initialize",
        id:      1,
        params:  {
          protocolVersion: "2025-03-26",
          capabilities:   {},
          clientInfo:     { name: "GoogleAppsScript", version: "4.0" },
        },
      }),
    });
    if (resp.getResponseCode() >= 400) throw new Error("MCP HTTP " + resp.getResponseCode());
    var rh = resp.getAllHeaders();
    if (rh["mcp-session-id"]) _mcpSessionId = rh["mcp-session-id"];
    else throw new Error("No session ID in response");
    UrlFetchApp.fetch(CONFIG.MCP_URL, {
      method:           "post",
      muteHttpExceptions: true,
      headers:          Object.assign({}, headers, { "Mcp-Session-Id": _mcpSessionId }),
      payload:          JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
    });
  } catch (e) {
    _mcpSessionId = null;
    throw new Error("MCP connect failed: " + e.message);
  }
}

function parseSSE_(text) {
  // Parse SSE stream: tìm dòng "data: {...}"
  var lines = text.split("\n");
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (line.indexOf("data: ") !== 0) continue;
    try {
      var json = JSON.parse(line.substring(6));
      if (json.result) {
        var isErr   = json.result.isError === true;
        var content = json.result.content || [];
        for (var j = 0; j < content.length; j++) {
          if (content[j].type === "text") {
            if (isErr) return { error: content[j].text, _mcpError: true };
            try { return JSON.parse(content[j].text); } catch (_) { return content[j].text; }
          }
        }
        return json.result;
      }
      if (json.error) return { error: json.error, _mcpError: true };
    } catch (_) {}
  }
  // Fallback: thử parse toàn bộ body
  try {
    var d = JSON.parse(text);
    if (d.result) {
      var ie = d.result.isError === true, c = d.result.content || [];
      for (var k = 0; k < c.length; k++) {
        if (c[k].type === "text") {
          if (ie) return { error: c[k].text, _mcpError: true };
          try { return JSON.parse(c[k].text); } catch (_) { return c[k].text; }
        }
      }
    }
    if (d.error) return { error: d.error, _mcpError: true };
  } catch (_) {}
  return null;
}
