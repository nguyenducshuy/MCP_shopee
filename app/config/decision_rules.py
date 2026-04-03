"""
Decision Rules — Ngưỡng ra quyết định cho AI quản lý campaign Shopee.

Nguồn: Bảng khảo sát phòng kinh doanh (Huệ điền + xác nhận lần 2).
Cập nhật: 2026-03-28

⚠️  LƯU Ý QUAN TRỌNG:
- Shop dùng Shopee AUTO-BID (tự động đấu thầu)
  → AI KHÔNG chỉnh bid thủ công
  → AI chỉ điều chỉnh "ROAS mục tiêu" (số nhân) trong Shopee Ads
- ROAS = số nhân (VD: ROAS=10 → 10đ doanh thu / 1đ chi phí)
- ACOS = Chi phí / Doanh thu × 100 (%)
- ROAS ↔ ACOS: ROAS = 100 / ACOS

📋 CHANGELOG:
  v1 (28/03): Khảo sát lần đầu
  v2 (28/03): Huệ xác nhận — thêm CTR/CVR threshold, ROAS targets (multiplier),
              rule scale by giảm ROAS nhẹ, báo cáo thủ công
"""

from dataclasses import dataclass, field
from typing import Optional


# ══════════════════════════════════════════════════════════════════
# 1. PHÂN NHÓM SẢN PHẨM & BIÊN LỢI NHUẬN
# ══════════════════════════════════════════════════════════════════

@dataclass
class ProductGroupRule:
    """Ngưỡng cho từng nhóm sản phẩm."""
    name: str
    gross_margin_pct: float   # Biên LN gộp = (Giá bán - Giá vốn) / Giá bán
    net_margin_pct: float     # Biên LN thực sau tất cả chi phí (chưa tính ads)
    roas_target_min: float    # ROAS mục tiêu thấp nhất (số nhân)
    roas_target_max: float    # ROAS mục tiêu cao nhất (số nhân)
    is_clearance: bool = False  # True = hàng xả, chấp nhận lỗ ads để thu hồi vốn

    @property
    def roas_target(self) -> float:
        """ROAS mục tiêu trung bình."""
        return round((self.roas_target_min + self.roas_target_max) / 2, 1)

    @property
    def roas_breakeven(self) -> Optional[float]:
        """ROAS tối thiểu để không lỗ (chưa tính ads). None nếu hàng xả."""
        if self.net_margin_pct <= 0:
            return None
        return round(100 / self.net_margin_pct, 2)

    @property
    def acos_target_min_pct(self) -> float:
        """ACOS thấp nhất tương ứng ROAS target max."""
        return round(100 / self.roas_target_max, 1)

    @property
    def acos_target_max_pct(self) -> float:
        """ACOS cao nhất tương ứng ROAS target min."""
        return round(100 / self.roas_target_min, 1)


PRODUCT_GROUPS: dict[str, ProductGroupRule] = {
    # Thiết bị chăm sóc sắc đẹp (TBCSSD / Ngành làm đẹp)
    "thiet_bi_lam_dep": ProductGroupRule(
        name="Thiết bị làm đẹp",
        gross_margin_pct=25.0,
        net_margin_pct=15.0,
        roas_target_min=5.0,    # ✅ Xác nhận: ROAS 5–10 (số nhân)
        roas_target_max=10.0,   # ROAS_breakeven = 6.7 → target ≥ 7.5 là có lãi
        is_clearance=False,
    ),
    # Giày dép nữ
    "giay_dep": ProductGroupRule(
        name="Giày dép",
        gross_margin_pct=15.0,
        net_margin_pct=5.0,
        roas_target_min=5.0,    # ✅ Xác nhận: ROAS 5 (số nhân)
        roas_target_max=5.0,    # Lưu ý: ROAS_breakeven = 20 >> ROAS_target = 5
                                # → Chấp nhận lỗ ads để test sản phẩm (có chủ đích)
        is_clearance=False,
    ),
    # Đồ chơi — hàng xả (thu hồi vốn)
    "do_choi": ProductGroupRule(
        name="Đồ chơi",
        gross_margin_pct=10.0,
        net_margin_pct=0.0,     # Xả hàng, mục tiêu thu hồi tiền vốn
        roas_target_min=10.0,   # ✅ Xác nhận: ROAS 10
        roas_target_max=10.0,
        is_clearance=True,
    ),
    # Đồ ngủ — hàng xả (thu hồi vốn)
    "do_ngu": ProductGroupRule(
        name="Đồ ngủ",
        gross_margin_pct=10.0,
        net_margin_pct=0.0,
        roas_target_min=10.0,   # ✅ Xác nhận: ROAS 10
        roas_target_max=10.0,
        is_clearance=True,
    ),
}

# Chi phí cố định trên mỗi đơn (% doanh thu)
FIXED_COST_RATES = {
    "shopee_platform_fee_pct": 23.0,
    "packaging_pct": 2.0,
    "labor_pct": 10.0,
}
TOTAL_FIXED_COST_PCT = sum(FIXED_COST_RATES.values())  # = 35%


# ══════════════════════════════════════════════════════════════════
# 2. QUY TẮC TẮT CAMPAIGN
# ══════════════════════════════════════════════════════════════════

@dataclass
class PauseRules:
    """Điều kiện để TẮT campaign. Kiểm tra theo đúng thứ tự ưu tiên."""

    # P1: Chi phí vô ích (không đơn, đã tiêu đáng kể so với giá bán)
    zero_order_pause_spend_pct_of_price: float = 10.0  # > 10% giá bán → tắt

    # P2: Không đơn kéo dài
    zero_order_pause_days: int = 7

    # P3: ROAS yếu + chi tiêu đáng kể
    roas_min_weekly: float = 5.0
    min_spend_to_check_roas: float = 20_000  # đ

    # Tồn kho: không tắt (shop restocking nhanh)
    pause_on_stockout: bool = False

    # Ngưỡng cảnh báo ACOS (chưa tắt, chỉ tăng ROAS target)
    acos_warning_pct: float = 30.0

    def should_pause(
        self,
        roas_7d: float,
        spend_7d: float,
        orders_7d: int,
        days_running: int,
        spend_total: float,
        product_price: float,
    ) -> tuple[bool, str]:
        """Trả về (nên_tắt, lý_do). Kiểm tra đúng thứ tự ưu tiên."""
        # P1
        if orders_7d == 0 and product_price > 0:
            threshold = product_price * self.zero_order_pause_spend_pct_of_price / 100
            if spend_total >= threshold:
                return True, (
                    f"Chi phí {spend_total:,.0f}đ = "
                    f"{spend_total/product_price*100:.1f}% giá bán, chưa có đơn nào"
                )
        # P2
        if days_running >= self.zero_order_pause_days and orders_7d == 0:
            return True, f"Chạy {days_running} ngày không có đơn"

        # P3
        if spend_7d >= self.min_spend_to_check_roas and roas_7d < self.roas_min_weekly:
            return True, (
                f"ROAS 7 ngày = {roas_7d:.1f} < {self.roas_min_weekly} "
                f"(đã chi {spend_7d:,.0f}đ)"
            )
        return False, ""

    def needs_roas_increase(self, acos_actual_pct: float) -> bool:
        """ACOS vượt ngưỡng → tăng ROAS target (không tắt)."""
        return acos_actual_pct > self.acos_warning_pct


PAUSE_RULES = PauseRules()


# ══════════════════════════════════════════════════════════════════
# 3. QUY TẮC ĐIỀU CHỈNH ROAS TARGET
# ══════════════════════════════════════════════════════════════════
# ⚠️  Auto-bid: không chỉnh bid → chỉnh ROAS mục tiêu trong Shopee Ads

@dataclass
class RoasAdjustRules:
    """
    4 tình huống điều chỉnh ROAS target:
      A. Camp cắn thốc  → TĂNG ROAS target (Shopee bid thấp hơn, tiêu chậm lại)
      B. Camp không cắn → GIẢM ROAS target (Shopee bid cao hơn, mở rộng phân phối)
      C. ACOS > 30%     → TĂNG ROAS target nhẹ
      D. Scale up tốt   → GIẢM ROAS target nhẹ (mở rộng tệp dần, không vỡ tệp)
    """
    # A. Overspend — camp cắn thốc ngay từ đầu, CPA vượt target
    overspend_roas_delta: float = 0.75   # Tăng +0.5 ~ +1.0 (dùng 0.75 trung bình)

    # B. Underspend — camp không cắn tiền, phân phối quá hẹp
    underspend_roas_delta: float = -0.5  # Giảm −0.5

    # C. ACOS cao
    high_acos_roas_delta: float = 0.75   # Tăng +0.5 ~ +1.0

    # D. Scale up — ROAS ổn định trong vùng mục tiêu, conversions tốt
    #    → Giảm nhẹ ROAS để Shopee mở rộng tệp từ từ, không vỡ tệp
    scale_roas_delta: float = -0.5       # ✅ Xác nhận từ Huệ

    def adjustment_for_overspend(self) -> dict:
        return {
            "action": "INCREASE_ROAS_TARGET",
            "delta": self.overspend_roas_delta,
            "reason": "Camp cắn thốc — tăng ROAS target để Shopee bid thấp lại",
        }

    def adjustment_for_underspend(self) -> dict:
        return {
            "action": "DECREASE_ROAS_TARGET",
            "delta": self.underspend_roas_delta,
            "reason": "Camp không cắn — giảm ROAS target để mở rộng phân phối",
        }

    def adjustment_for_high_acos(self, acos_pct: float) -> dict:
        return {
            "action": "INCREASE_ROAS_TARGET",
            "delta": self.high_acos_roas_delta,
            "reason": f"ACOS {acos_pct:.1f}% > 30% — tăng ROAS target để giảm chi tiêu",
        }

    def adjustment_for_scale_up(self) -> dict:
        return {
            "action": "DECREASE_ROAS_TARGET",
            "delta": self.scale_roas_delta,
            "reason": (
                "Camp ổn định tốt — giảm ROAS target nhẹ để mở rộng tệp phân phối "
                "dần dần, tránh vỡ tệp"
            ),
        }


ROAS_ADJUST_RULES = RoasAdjustRules()


# ══════════════════════════════════════════════════════════════════
# 4. QUY TẮC SCALE UP
# ══════════════════════════════════════════════════════════════════

@dataclass
class ScaleUpRules:
    """
    Điều kiện TĂNG NGÂN SÁCH + GIẢM ROAS TARGET nhẹ.
    ✅ Huệ xác nhận: ROAS ≥ 10 VÀ conversions ≥ 2
       → tăng ngân sách VÀ giảm ROAS target khoảng 0.5
    """
    roas_min: float = 10.0
    min_conversions: int = 2
    roas_delta_on_scale: float = -0.5   # Giảm ROAS target để mở rộng tệp

    def should_scale_up(
        self, roas: float, conversions: int
    ) -> tuple[bool, str]:
        if roas >= self.roas_min and conversions >= self.min_conversions:
            return True, (
                f"ROAS = {roas:.1f} ≥ {self.roas_min} "
                f"và {conversions} đơn ≥ {self.min_conversions}"
            )
        return False, ""


SCALE_UP_RULES = ScaleUpRules()


# ══════════════════════════════════════════════════════════════════
# 5. CTR & CVR THRESHOLD
# ══════════════════════════════════════════════════════════════════
# ✅ Xác nhận từ Huệ (lần 2)

@dataclass
class QualityThresholds:
    """Ngưỡng chất lượng CTR và CVR."""

    # CTR — Tỉ lệ click
    ctr_bad_pct: float = 1.2       # CTR < 1.2% → cần review creative
    ctr_ok_pct: float  = 2.0       # CTR 1.2–2.0% → tạm chấp nhận
    # CTR ≥ 2.0% → tốt

    # CVR — Tỉ lệ chuyển đổi (click → đơn)
    cvr_bad_pct: float = 2.5       # CVR < 2.5% → cần review trang sản phẩm
    cvr_ok_pct: float  = 5.0       # CVR 2.5–5.0% → tạm chấp nhận
    # CVR ≥ 5.0% → tốt

    def rate_ctr(self, ctr_pct: float) -> tuple[str, str]:
        """Trả về (rating, action)."""
        if ctr_pct < self.ctr_bad_pct:
            return "BAD", "Review creative: ảnh bìa, title, giá hiển thị, voucher, rating"
        if ctr_pct < self.ctr_ok_pct:
            return "OK", "Tạm chấp nhận, theo dõi thêm"
        return "GOOD", ""

    def rate_cvr(self, cvr_pct: float) -> tuple[str, str]:
        """Trả về (rating, action)."""
        if cvr_pct < self.cvr_bad_pct:
            return "BAD", "Review trang sản phẩm: ảnh detail, mô tả, giá, đánh giá"
        if cvr_pct < self.cvr_ok_pct:
            return "OK", "Tạm chấp nhận, theo dõi thêm"
        return "GOOD", ""


QUALITY_THRESHOLDS = QualityThresholds()


# ══════════════════════════════════════════════════════════════════
# 6. QUY TẮC CHẠY CAMPAIGN MỚI
# ══════════════════════════════════════════════════════════════════

@dataclass
class LaunchRules:
    """Điều kiện để CHẠY campaign mới (từ file BigSeller)."""

    require_profit_positive: bool = True    # Cột Profit > 0
    require_no_active_campaign: bool = True  # Cột Link quảng cáo = trống

    # Không yêu cầu: tồn kho, review, rating, CVR organic
    min_stock: Optional[int] = None
    min_reviews: Optional[int] = None
    min_organic_cvr_pct: Optional[float] = None

    def should_launch(
        self, profit: float, has_active_campaign: bool
    ) -> tuple[bool, str]:
        if self.require_profit_positive and profit <= 0:
            return False, f"Profit = {profit:,.0f}đ ≤ 0"
        if self.require_no_active_campaign and has_active_campaign:
            return False, "Đã có campaign đang chạy"
        return True, "Đủ điều kiện: Profit > 0 và chưa có camp"

    def calc_cpa_target(
        self, selling_price: float, product_group_key: str = "thiet_bi_lam_dep"
    ) -> float:
        """CPA mục tiêu = Giá bán × ACOS_target_mid (%)."""
        group = PRODUCT_GROUPS.get(product_group_key, PRODUCT_GROUPS["thiet_bi_lam_dep"])
        acos_mid = 100 / group.roas_target  # ROAS_target → ACOS
        return round(selling_price * acos_mid / 100, 0)

    def calc_trial_budget(
        self, selling_price: float, product_group_key: str = "thiet_bi_lam_dep"
    ) -> float:
        """Ngân sách thử nghiệm = 1 CPA mục tiêu."""
        return self.calc_cpa_target(selling_price, product_group_key)


LAUNCH_RULES = LaunchRules()


# ══════════════════════════════════════════════════════════════════
# 7. ĐÁNH GIÁ & BÁO CÁO
# ══════════════════════════════════════════════════════════════════

EVALUATION_CONFIG = {
    "eval_from_day": 1,               # Đánh giá ngay từ ngày đầu
    "min_spend_before_eval": "CPA_target",  # Tiêu đủ 1 CPA mới đánh giá
    "reporting_mode": "on_demand",    # ✅ Xác nhận: thủ công, khi nào yêu cầu mới báo
    # reporting_mode options: "daily_morning" | "on_demand"
}

BUSINESS_GOALS = {
    "primary_goal": "maximize_profit",
    "seasonal_campaigns": False,
    "ads_mode": "shopee_auto_bid",
    "vip_products": [],
    "blacklist_products": [],
}


# ══════════════════════════════════════════════════════════════════
# 8. HÀM PHÂN LOẠI CAMPAIGN — entry point cho AI
# ══════════════════════════════════════════════════════════════════

def get_product_group(group_key: str) -> ProductGroupRule:
    return PRODUCT_GROUPS.get(group_key, PRODUCT_GROUPS["thiet_bi_lam_dep"])


def classify_campaign(
    roas_7d: float,
    acos_actual_pct: float,
    ctr_pct: float,
    cvr_pct: float,
    orders_7d: int,
    conversions_total: int,
    spend_7d: float,
    spend_total: float,
    days_running: int,
    product_price: float,
    product_group_key: str = "thiet_bi_lam_dep",
    is_spending: bool = True,   # True = camp đang tiêu tiền
) -> dict:
    """
    Phân loại campaign và đề xuất hành động.
    Trả về dict: action, reason, detail, urgency.

    Actions:
      PAUSE              → Tắt campaign
      INCREASE_ROAS_TARGET → Tăng ROAS target (giảm spend)
      DECREASE_ROAS_TARGET → Giảm ROAS target (tăng phân phối)
      SCALE_UP           → Tăng ngân sách + giảm ROAS nhẹ
      REVIEW_CREATIVE    → CTR thấp, xem lại ảnh/title
      REVIEW_LISTING     → CVR thấp, xem lại trang sản phẩm
      KEEP               → Đang tốt, giữ nguyên
      MONITOR            → Cần theo dõi thêm
    """
    group = get_product_group(product_group_key)
    result = {"action": "MONITOR", "reason": "", "detail": [], "urgency": "LOW"}

    # ── 1. Nên tắt không? ────────────────────────────────────────
    should_stop, stop_reason = PAUSE_RULES.should_pause(
        roas_7d, spend_7d, orders_7d, days_running, spend_total, product_price
    )
    if should_stop:
        return {
            "action": "PAUSE",
            "reason": stop_reason,
            "detail": [],
            "urgency": "HIGH",
        }

    # ── 2. Camp cắn thốc? ────────────────────────────────────────
    if is_spending and orders_7d == 0 and days_running <= 3 and spend_7d > 0:
        cpa_estimate = spend_7d / max(orders_7d, 1) if orders_7d > 0 else spend_7d
        if product_price > 0 and spend_7d > product_price * 0.05:
            adj = ROAS_ADJUST_RULES.adjustment_for_overspend()
            return {
                "action": adj["action"],
                "reason": adj["reason"],
                "detail": [f"delta ROAS = +{adj['delta']}"],
                "urgency": "HIGH",
            }

    # ── 3. Camp không cắn tiền? ──────────────────────────────────
    if not is_spending and days_running >= 1:
        adj = ROAS_ADJUST_RULES.adjustment_for_underspend()
        return {
            "action": adj["action"],
            "reason": adj["reason"],
            "detail": [f"delta ROAS = {adj['delta']}"],
            "urgency": "MEDIUM",
        }

    # ── 4. Scale up? ─────────────────────────────────────────────
    should_scale, scale_reason = SCALE_UP_RULES.should_scale_up(roas_7d, conversions_total)
    if should_scale:
        adj = ROAS_ADJUST_RULES.adjustment_for_scale_up()
        return {
            "action": "SCALE_UP",
            "reason": scale_reason,
            "detail": [
                "Tăng ngân sách campaign",
                f"{adj['reason']} (delta ROAS = {adj['delta']})",
            ],
            "urgency": "MEDIUM",
        }

    # ── 5. ACOS quá cao? ─────────────────────────────────────────
    if PAUSE_RULES.needs_roas_increase(acos_actual_pct):
        adj = ROAS_ADJUST_RULES.adjustment_for_high_acos(acos_actual_pct)
        return {
            "action": adj["action"],
            "reason": adj["reason"],
            "detail": [f"delta ROAS = +{adj['delta']}"],
            "urgency": "MEDIUM",
        }

    # ── 6. CTR / CVR thấp? ───────────────────────────────────────
    issues = []
    ctr_rating, ctr_action = QUALITY_THRESHOLDS.rate_ctr(ctr_pct)
    cvr_rating, cvr_action = QUALITY_THRESHOLDS.rate_cvr(cvr_pct)

    if ctr_rating == "BAD":
        issues.append({"type": "REVIEW_CREATIVE", "detail": ctr_action, "metric": f"CTR={ctr_pct:.2f}%"})
    if cvr_rating == "BAD":
        issues.append({"type": "REVIEW_LISTING", "detail": cvr_action, "metric": f"CVR={cvr_pct:.2f}%"})

    if issues:
        primary = issues[0]
        return {
            "action": primary["type"],
            "reason": f"{primary['metric']} — {primary['detail']}",
            "detail": [i["detail"] for i in issues],
            "urgency": "MEDIUM",
        }

    # ── 7. ROAS đang trong vùng mục tiêu → OK ────────────────────
    if group.roas_target_min <= roas_7d <= group.roas_target_max:
        return {
            "action": "KEEP",
            "reason": f"ROAS = {roas_7d:.1f} trong vùng mục tiêu [{group.roas_target_min}–{group.roas_target_max}]",
            "detail": [],
            "urgency": "LOW",
        }

    # ── 8. ROAS dưới mục tiêu nhưng chưa đủ điều kiện tắt ───────
    return {
        "action": "MONITOR",
        "reason": (
            f"ROAS = {roas_7d:.1f} dưới mục tiêu "
            f"[{group.roas_target_min}–{group.roas_target_max}], theo dõi thêm"
        ),
        "detail": [],
        "urgency": "LOW",
    }


# ══════════════════════════════════════════════════════════════════
# 9. QUICK REFERENCE — tóm tắt tất cả ngưỡng
# ══════════════════════════════════════════════════════════════════

QUICK_REFERENCE = {
    "nhom_san_pham": {
        g.name: {
            "roas_target": f"{g.roas_target_min}–{g.roas_target_max}",
            "acos_tuong_ung": f"{g.acos_target_min_pct}–{g.acos_target_max_pct}%",
            "roas_hoa_von": g.roas_breakeven or "N/A (xả hàng)",
            "la_hang_xa": g.is_clearance,
        }
        for g in PRODUCT_GROUPS.values()
    },
    "tat_campaign": {
        "p1_chi_phi_vo_ich": "> 10% giá bán mà không có đơn",
        "p2_khong_don": ">= 7 ngày không có đơn",
        "p3_roas_yeu": "ROAS 7 ngày < 5 VÀ chi phí > 20.000đ",
        "canh_bao_acos": "ACOS > 30% → tăng ROAS target",
    },
    "dieu_chinh_roas_target": {
        "can_thoc": "TĂNG +0.75",
        "khong_can": "GIẢM −0.5",
        "acos_cao": "TĂNG +0.75",
        "scale_up": "GIẢM −0.5 (mở rộng tệp dần)",
    },
    "scale_up": "ROAS ≥ 10 VÀ conversions ≥ 2 → tăng ngân sách + giảm ROAS −0.5",
    "ctr": {"xau": "< 1.2%", "ok": "1.2–2.0%", "tot": "≥ 2.0%"},
    "cvr": {"xau": "< 2.5%", "ok": "2.5–5.0%", "tot": "≥ 5.0%"},
    "chay_moi": "Profit > 0 VÀ Link camp = trống",
    "bao_cao": "Thủ công — chỉ khi được yêu cầu",
}
