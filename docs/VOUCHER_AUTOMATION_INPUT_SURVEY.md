# Khảo Sát Đầu Vào Triển Khai Voucher Automation

## 1. Mục tiêu tài liệu

Tài liệu này dùng để khảo sát và chốt toàn bộ đầu vào cần thiết trước khi triển khai hệ thống automation cho module voucher của Shopee.

Mục tiêu vận hành mong muốn:
- Nhân sự kinh doanh chỉ cần điền dữ liệu vào Google Sheet.
- Nhân sự bấm 1 nút hoặc trigger 1 workflow.
- Hệ thống tự tạo, cập nhật, kết thúc hoặc xóa voucher hàng loạt trên nhiều shop.
- Hệ thống trả log kết quả rõ ràng theo từng shop và từng voucher.

Phạm vi tài liệu này chỉ tập trung vào:
- `voucher`
- không bao gồm `discount`
- hướng tới vận hành đa shop, hiện tại khoảng 21 shop và có thể scale thêm

## 2. Mục tiêu phase 1

Đề xuất phase 1 chỉ hỗ trợ:
- tạo voucher
- cập nhật voucher
- kết thúc voucher
- xóa voucher
- shop voucher
- product voucher nếu dữ liệu item đã đủ ổn định

Đề xuất chưa làm ở phase 1 nếu chưa thật sự cần:
- rule chọn item tự động phức tạp
- AI tự suy luận loại voucher từ mô tả tự nhiên
- rollback liên hoàn nhiều bước
- dashboard BI nâng cao

## 3. Kết quả đầu ra mong muốn của automation

Sau mỗi lần chạy, hệ thống cần trả được:
- job id
- thời gian chạy
- người chạy
- chế độ chạy: `dry_run` hoặc `execute`
- tổng số shop được chọn
- tổng số voucher dự kiến xử lý
- tổng số thành công
- tổng số thất bại
- chi tiết lỗi theo từng shop
- chi tiết voucher_id tạo ra hoặc voucher_id bị ảnh hưởng

Đầu ra nên ghi vào ít nhất 1 trong 2 nơi:
- response JSON trả về ngay sau khi bấm nút
- sheet log riêng để audit

Đề xuất nên có cả hai.

## 4. Luồng vận hành mục tiêu

1. Nhân sự điền dữ liệu vào sheet đầu vào.
2. Nhân sự chọn job hoặc ngày chạy.
3. Nhân sự bấm nút `Run Voucher Automation`.
4. Hệ thống đọc sheet, validate dữ liệu, resolve danh sách shop, kiểm tra xung đột.
5. Nếu chạy `dry_run`, hệ thống chỉ báo trước kết quả dự kiến và lỗi.
6. Nếu chạy `execute`, hệ thống gọi Shopee API theo từng shop.
7. Hệ thống ghi log kết quả và trả summary.

## 5. Các câu hỏi nghiệp vụ cần chốt

### 5.1 Phạm vi nghiệp vụ

- Cần hỗ trợ những action nào:
  - `create`
  - `update`
  - `end`
  - `delete`
- Một lần chạy có được phép trộn nhiều action không, hay mỗi job chỉ 1 action?
- Có cần hỗ trợ `product voucher` ngay từ đầu không?
- Có cần hỗ trợ `coin cashback` không?

### 5.2 Phạm vi áp dụng shop

- Một voucher có áp dụng cho:
  - 1 shop
  - nhiều shop
  - toàn bộ shop active
- Có khái niệm nhóm shop không:
  - theo brand
  - theo ngành hàng
  - theo khu vực
  - theo owner nội bộ
- Nếu một số shop bị khóa token hoặc lỗi API thì:
  - bỏ qua shop lỗi và chạy tiếp
  - dừng toàn job
  - chạy tiếp nhưng đánh dấu partial success

### 5.3 Quản lý mã voucher

- `voucher_code` sẽ:
  - nhập tay 100%
  - tự sinh 100%
  - nhập template rồi hệ thống sinh
- Nếu tự sinh thì format như thế nào:
  - prefix theo campaign
  - suffix theo shop
  - suffix theo ngày
  - random segment
- Có yêu cầu mã voucher phải giống nhau giữa nhiều shop không?
- Khi trùng code thì:
  - fail
  - auto sinh lại
  - bỏ qua shop đó

### 5.4 Thời gian hiệu lực

- Nhân sự nhập:
  - `start_time` và `end_time` đầy đủ
  - hay chỉ nhập `campaign_date`, `start_hour`, `end_hour`
- Timezone cố định có phải luôn là `Asia/Saigon` không?
- Có cần hỗ trợ:
  - chạy trong ngày
  - chạy nhiều ngày liên tiếp
  - chạy định kỳ
- Có cần rule mặc định như:
  - bắt đầu 00:00
  - kết thúc 23:59
  - hoặc theo khung giờ cố định

### 5.5 Luật xử lý khi voucher đã tồn tại

- Khi chạy `create` mà phát hiện voucher tương tự đã có thì:
  - fail
  - bỏ qua
  - chuyển thành update
- Tiêu chí xác định "đã tồn tại" là gì:
  - cùng `voucher_code`
  - cùng `voucher_name`
  - cùng `voucher_code + shop`
  - cùng `time window + reward`

### 5.6 Quy trình duyệt

- Có cần `dry_run` trước khi chạy thật không?
- Có cần bước xác nhận lần hai khi:
  - số shop > ngưỡng nào đó
  - số voucher > ngưỡng nào đó
  - action là `delete` hoặc `end`
- Có cần role phân quyền:
  - người nhập liệu
  - người duyệt
  - người chạy

## 6. Dữ liệu đầu vào bắt buộc cho mỗi job

Đây là dữ liệu tối thiểu để automation có thể thực thi.

### 6.1 Nhóm điều khiển job

- `job_id`
- `action`
- `apply_to`
- `run_mode`
- `campaign_name`
- `operator_note`

Giải thích:
- `job_id`: mã duy nhất để trace và audit
- `action`: `create`, `update`, `end`, `delete`
- `apply_to`: danh sách shop hoặc nhóm shop
- `run_mode`: `dry_run` hoặc `execute`
- `campaign_name`: tên chiến dịch nội bộ
- `operator_note`: ghi chú của nhân sự

### 6.2 Nhóm dữ liệu voucher

- `voucher_name`
- `voucher_code` hoặc `voucher_code_template`
- `voucher_type`
- `reward_type`
- `usage_quantity`
- `start_time`
- `end_time`

### 6.3 Nhóm dữ liệu theo reward

Nếu `reward_type` là fixed amount:
- `discount_amount`
- `min_basket_price`

Nếu `reward_type` là percentage:
- `percentage`
- `max_price`
- `min_basket_price`

Nếu `reward_type` là coin cashback:
- cần chốt rõ schema thực tế trước khi bật

### 6.4 Nhóm dữ liệu để update/end/delete

Nếu action không phải `create`, cần thêm:
- `voucher_id`

Nếu không có `voucher_id`, cần chốt có cho resolve tự động hay không theo:
- `shop_code + voucher_code`
- `shop_code + voucher_name`

Khuyến nghị phase 1:
- `update`, `end`, `delete` phải có `voucher_id`
- không nên để hệ thống tự dò mơ hồ

## 7. Cấu trúc Google Sheet đề xuất

## 7.1 Sheet 1: `voucher_jobs`

Mỗi dòng là một job voucher.

Các cột đề xuất:

| Cột | Bắt buộc | Ví dụ | Mục đích |
| --- | --- | --- | --- |
| `job_id` | Có | `VCH-2026-04-03-001` | Mã job nội bộ |
| `status` | Có | `READY` | Trạng thái vận hành |
| `action` | Có | `create` | Loại hành động |
| `run_mode` | Có | `dry_run` | Chạy thử hoặc chạy thật |
| `apply_to` | Có | `all` | Áp dụng cho shop nào |
| `campaign_name` | Có | `Mega Sale 4.4` | Tên chiến dịch nội bộ |
| `voucher_name` | Có | `MEGA SALE 4.4 - 50K` | Tên voucher hiển thị |
| `voucher_code` | Tùy | `MEGA44A` | Mã voucher cụ thể |
| `voucher_code_template` | Tùy | `MEGA44_{SHOP}` | Template sinh code |
| `voucher_type` | Có | `shop` | Loại voucher |
| `reward_type` | Có | `fixed_amount` | Loại ưu đãi |
| `discount_amount` | Tùy | `50000` | Mức giảm cố định |
| `percentage` | Tùy | `20` | % giảm |
| `max_price` | Tùy | `100000` | Trần giảm giá |
| `min_basket_price` | Tùy | `299000` | Giá trị đơn tối thiểu |
| `usage_quantity` | Có | `500` | Tổng lượt sử dụng |
| `start_time` | Có | `2026-04-04 00:00:00` | Bắt đầu |
| `end_time` | Có | `2026-04-04 23:59:59` | Kết thúc |
| `voucher_id` | Tùy | `123456789` | Bắt buộc nếu update/end/delete |
| `operator_note` | Không | `Áp dụng toàn hệ thống` | Ghi chú |
| `created_by` | Không | `anh.a` | Người tạo |
| `approved_by` | Không | `chị.b` | Người duyệt |

## 7.2 Sheet 2: `shop_mapping`

Mỗi dòng là một shop.

Các cột đề xuất:

| Cột | Bắt buộc | Ví dụ | Mục đích |
| --- | --- | --- | --- |
| `shop_code` | Có | `shop_tb_hn_01` | Mã shop nội bộ dùng cho MCP |
| `shop_name` | Có | `TB Hà Nội 01` | Tên shop |
| `shop_id` | Có | `847753176` | Shop ID Shopee |
| `group_name` | Không | `mien_bac` | Nhóm shop |
| `brand` | Không | `TB` | Brand |
| `is_active` | Có | `TRUE` | Có được chạy không |
| `priority` | Không | `1` | Ưu tiên nếu cần |

## 7.3 Sheet 3: `job_logs`

Mỗi dòng là kết quả 1 shop trong 1 job.

Các cột đề xuất:

| Cột | Ví dụ | Mục đích |
| --- | --- | --- |
| `job_id` | `VCH-2026-04-03-001` | Link với job đầu vào |
| `shop_code` | `shop_tb_hn_01` | Shop thực thi |
| `action` | `create` | Action đã chạy |
| `result` | `SUCCESS` | Kết quả |
| `voucher_id` | `99887766` | Voucher ID thực tế |
| `voucher_code` | `MEGA44A` | Code thực tế |
| `message` | `Created successfully` | Thông báo |
| `raw_error` | `error_param` | Mã lỗi gốc nếu có |
| `executed_at` | `2026-04-03 09:01:33` | Thời điểm chạy |

## 8. Chuẩn hóa giá trị enum

Để giảm lỗi do nhập liệu, nên khóa dropdown trong sheet.

### 8.1 `action`

Giá trị cho phép:
- `create`
- `update`
- `end`
- `delete`

### 8.2 `run_mode`

Giá trị cho phép:
- `dry_run`
- `execute`

### 8.3 `voucher_type`

Giá trị đề xuất cho người dùng nhập:
- `shop`
- `product`

Mapping kỹ thuật:
- `shop` -> `1`
- `product` -> `2`

### 8.4 `reward_type`

Giá trị đề xuất cho người dùng nhập:
- `fixed_amount`
- `percentage`
- `coin_cashback`

Mapping kỹ thuật:
- `fixed_amount` -> `1`
- `percentage` -> `2`
- `coin_cashback` -> `3`

### 8.5 `status`

Giá trị đề xuất cho điều phối job:
- `DRAFT`
- `READY`
- `APPROVED`
- `RUNNING`
- `DONE`
- `FAILED`

## 9. Rule validate cần có trước khi chạy

## 9.1 Validate chung

- `job_id` không được trống
- `action` phải thuộc tập giá trị cho phép
- `apply_to` phải resolve được thành ít nhất 1 shop active
- `start_time < end_time`
- `usage_quantity > 0`
- nếu `run_mode=execute` thì `status` phải là `READY` hoặc `APPROVED`

## 9.2 Validate theo action

### `create`

- phải có `voucher_name`
- phải có `voucher_code` hoặc `voucher_code_template`
- phải có `voucher_type`
- phải có `reward_type`
- phải có `usage_quantity`
- phải có `start_time`, `end_time`

### `update`

- phải có `voucher_id`
- phải có ít nhất 1 field update thực sự

### `end`

- phải có `voucher_id`

### `delete`

- phải có `voucher_id`

## 9.3 Validate theo reward

### `fixed_amount`

- phải có `discount_amount`
- phải có `min_basket_price`

### `percentage`

- phải có `percentage`
- phải có `max_price`
- nên có `min_basket_price`

### `coin_cashback`

- chưa bật ở phase 1 nếu chưa chốt schema thực tế

## 10. Rule xử lý đa shop

Đây là phần quan trọng nhất để scale.

Các quyết định cần chốt:
- 1 dòng job áp cho tất cả shop trong `apply_to`, hay hệ thống phải nổ thành nhiều task con?
- `voucher_code` có được phép giống nhau ở tất cả shop không?
- Có cần thêm token placeholder trong code template không:
  - `{SHOP}`
  - `{DATE}`
  - `{SEQ}`
- Nếu 21 shop mà fail 2 shop:
  - job tổng là `PARTIAL_SUCCESS`
  - hay `FAILED`

Khuyến nghị:
- 1 dòng job -> nhiều task con theo từng shop
- log theo từng shop
- summary cấp job
- không rollback đồng loạt ở phase 1

## 11. Rule audit và an toàn vận hành

Nên bắt buộc lưu:
- người tạo job
- người duyệt job
- thời điểm chạy
- input snapshot
- output snapshot
- lỗi gốc từ Shopee API

Nên chặn thêm:
- không cho `delete` chạy nếu không có `dry_run` trước
- không cho `execute` nếu token shop đang invalid
- không cho chạy nếu cùng `job_id` đã `DONE`

## 12. Mẫu dòng dữ liệu đề xuất

### 12.1 Tạo voucher giảm tiền cố định cho toàn bộ shop

| job_id | status | action | run_mode | apply_to | campaign_name | voucher_name | voucher_code_template | voucher_type | reward_type | discount_amount | min_basket_price | usage_quantity | start_time | end_time |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `VCH-2026-04-04-001` | `READY` | `create` | `execute` | `all` | `4.4 MEGA` | `Voucher 50K 4.4` | `V44_{SHOP}` | `shop` | `fixed_amount` | `50000` | `299000` | `1000` | `2026-04-04 00:00:00` | `2026-04-04 23:59:59` |

### 12.2 End voucher theo nhiều shop

| job_id | status | action | run_mode | apply_to | voucher_id | operator_note |
| --- | --- | --- | --- | --- | --- | --- |
| `VCH-2026-04-04-002` | `READY` | `end` | `execute` | `mien_bac` | `99887766` | `Dừng sớm do hết tồn kho` |

## 13. Các quyết định kỹ thuật cần chốt trước khi code

Đây là checklist bắt buộc.

### 13.1 Nguồn dữ liệu

- Google Sheet nào là nguồn chính?
- Có dùng nhiều tab trong 1 file hay nhiều file?
- Ai có quyền sửa?

### 13.2 Trigger

- bấm nút Apps Script
- gọi MCP tool trực tiếp
- webhook nội bộ
- cron theo lịch

### 13.3 Logging

- log ở sheet
- log ở file
- log ở database
- hay kết hợp

### 13.4 Khả năng mở rộng

- có dự kiến tăng lên bao nhiêu shop?
- có giới hạn concurrency theo Shopee API không?
- có cần queue job không?

### 13.5 Xử lý trùng lặp

- job trùng `job_id`
- voucher code trùng
- cùng một shop bị chạy hai lần trong cùng job

## 14. Đề xuất triển khai phase 1

Để có tốc độ triển khai nhanh và ít rủi ro, đề xuất:

- chỉ hỗ trợ `shop voucher`
- chỉ hỗ trợ `fixed_amount` và `percentage`
- action gồm `create`, `update`, `end`, `delete`
- input từ Google Sheet
- bắt buộc `dry_run`
- ghi log ra `job_logs`
- chạy theo từng shop song song có giới hạn

## 15. Những gì cần phòng kinh doanh trả lời ngay

Đây là danh sách khảo sát rút gọn để chốt nhanh.

1. Có cần `product voucher` ngay từ phase 1 không?
2. Có cần `coin cashback` ngay từ phase 1 không?
3. `voucher_code` nhập tay hay auto-generate?
4. Một job áp cho nhiều shop hay mỗi shop một dòng?
5. Khi code trùng thì fail hay tự sinh lại?
6. Có bắt buộc `dry_run` trước khi chạy thật không?
7. Khi một vài shop lỗi, có cho phép partial success không?
8. Có cần bước duyệt trước khi `execute` không?
9. Log kết quả cần lưu ở đâu?
10. Nguồn Google Sheet cụ thể là file nào?

## 16. Đầu ra của tài liệu này

Sau khi điền xong khảo sát, đội triển khai phải chốt được:
- schema sheet chính thức
- enum chuẩn
- flow vận hành
- rule validate
- rule conflict
- format output/log
- phạm vi phase 1

Khi 7 mục trên đã chốt, có thể bắt đầu code voucher automation mà không còn mơ hồ về đầu vào.
