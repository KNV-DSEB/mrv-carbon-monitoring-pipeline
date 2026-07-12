# Báo cáo Live-Run Đầu Tiên — MRV Carbon Monitoring Pipeline

**Phạm vi**: Lần chạy Google Earth Engine thật đầu tiên, AOI thí điểm, Bắc Ninh, Việt Nam
**Ngày**: Tháng 7/2026
**Phiên bản**: Tiếng Việt ([English version](02-first-live-run-report.en.md))

**Trạng thái**: Đây là **lần chạy thật đầu tiên trên dữ liệu Sentinel-2 thực**.
Nó đã kiểm chứng pipeline đầu-cuối trên ảnh thật, phát hiện và vá một lỗi metric,
và tạo ra tín hiệu mùa vụ đọc được cho một vụ — nhưng **chưa có kiểm chứng thực
địa / ground-truth**, và **không tuyên bố bất kỳ con số độ chính xác % nào**. Mọi
số liệu dưới đây lấy từ manifest của lần chạy này và
`data/processed/spectral_indices.csv`.

## 1. Tóm tắt điều hành

Lần chạy thật đầu tiên làm được ba việc. (1) **Kiểm chứng pipeline
`collect → features` trên ảnh Sentinel-2 thật** cho AOI thí điểm Bắc Ninh.
(2) **Phơi bày một lỗi metric** — `aoi_clear_fraction` đang đo `clear/valid` thay
vì `clear/total`, vô hiệu hoá âm thầm bộ lọc `MIN_CLEAR_FRACTION` — lỗi đã được
truy nguyên, vá, rồi tái kiểm trên chính dữ liệu thật đó. (3) Tạo ra một
**chuỗi 7 scene cho vụ Đông-Xuân 2025–26** đọc được như một cung vật hậu mạch lạc
(ngập/đổ ải → sinh trưởng → đỉnh trổ → chín/gặt).

Phát hiện vận hành cốt lõi: **chỉ ảnh quang học là ĐỦ để giám sát vật hậu mùa vụ ở
Đông-Xuân (7 scene dùng được), nhưng KHÔNG đủ cho MRV quanh năm** — vụ Mùa (mưa)
trả về **0 scene dùng được trong 45 ngày cao điểm mưa**. Điều này chỉ hướng
Sentinel-1 SAR là hướng đi phase 2, và kết luận đó rút ra từ số đo trên chính AOI
này, không phải trích dẫn tài liệu.

## 2. Cấu hình chốt

- **AOI**: `data/external/aoi/bac_ninh_pilot.geojson` — ~2.03 km², Lương Tài
  (Bắc Ninh cũ), centroid ≈ 21.0375 N, 106.2198 E.
- **`MAX_CLOUD_COVER_PCT` = 100**, **`MIN_CLEAR_FRACTION` = 0.5**.

**Vì sao `MAX_CLOUD_COVER_PCT = 100`.** Bộ lọc cấp scene
`CLOUDY_PIXEL_PERCENTAGE` được tính trên **cả tile Sentinel-2 ~110×110 km**, chứ
không phải trên AOI ~2 km² của ta. Một tile có thể bị gắn nhãn nhiều mây trong khi
AOI nhỏ của ta lại quang — nên ngưỡng cấp scene **vứt nhầm những scene thực ra
quang trên AOI**. Cách xử lý là ngừng lọc ở cấp tile và lọc ở **cấp AOI** thay thế,
qua `aoi_clear_fraction` + `MIN_CLEAR_FRACTION` — đúng tầng cho một AOI nhỏ. Đặt
`MAX_CLOUD_COVER_PCT = 100` tắt bộ lọc sai-tầng để không thứ gì bị loại trước khi
đo ở cấp AOI.

## 3. Lỗi metric (kết quả quan trọng nhất của lần chạy này)

**Triệu chứng.** Lần chạy đầu (`MAX_CLOUD_COVER_PCT = 70`) trả về 8 scene với
**mọi `aoi_clear_fraction` = 1.000** và **survival sweep phẳng lì** — bất khả thi
cho một AOI lúa xuyên vụ. Stress test mùa mưa (`MAX_CLOUD_COVER_PCT = 100`, 45
ngày cao điểm mưa) vẫn chỉ ra **1.000 hoặc None**, là bằng chứng trực tiếp rằng
metric đã hỏng, chứ không phải may mắn gặp bộ scene quang.

**Nguyên nhân gốc.** `collect.py` áp `collection.map(mask_clouds)` **TRƯỚC** khi
đo. `mask_clouds` mask các pixel không-quang của band SCL, nên `reduceRegion(mean)`
lấy trung bình chỉ trên các pixel còn sống (quang) — metric đo **clear / valid ≈
1.0**, không phải **clear / total**. `MIN_CLEAR_FRACTION` vì thế bị vô hiệu hoàn
toàn: mọi scene quan sát được đều đọc thành quang tuyệt đối.

**Cách vá.** Đo `aoi_clear_fraction` trên **SCL THÔ**, để pixel mây được đếm 0 ở
mẫu số (`clear / total-trong-footprint`). AOI toàn mây giờ ra **0.0**; `None` chỉ
còn nghĩa AOI nằm ngoài footprint của scene. (`features` vẫn giữ mask mây riêng của
nó để tính chỉ số — không đụng tới.)

**Tái kiểm trên dữ liệu thật.** Sau khi vá, cửa sổ mùa mưa giờ trả về giá trị
**0.0 và trung gian**, và survival sweep **hết phẳng** — xem Mục 4–5.

**Hệ quả trên dữ liệu ở cấu hình chốt.** Hai scene của chuỗi cũ (trước vá) giờ bị
loại đúng vì nhiễm mây: **16/2** và **27/4**. Lưu ý trung thực: **27/4 chính là
"đỉnh NDVI" (0.581) của chuỗi cũ — đỉnh đó là ARTEFACT MÂY**, không phải cực đại
thực vật thật. Đỉnh NDVI thật của chuỗi này là **27/5 (0.546)**. Bù lại, hạ ngưỡng
về 0.5 thu được **27/1**, scene pha ngập/đổ ải — điểm quý nhất chuỗi (Mục 6).

**Vì sao lọt lưới.** Lỗi lọt qua toàn bộ 57 unit test có sẵn vì các test đó dùng
`MagicMock` không mô hình hoá pixel nào — chính phép toán mask-vs-reducer gây lỗi
đơn giản là không được biểu diễn. Nó chỉ có thể lộ ra trên dữ liệu Earth Engine
thật.

## 4. Kết quả A — Vụ Mùa 2025 (vụ mưa)

Cửa sổ `2025-07-01 .. 2025-08-15` (45 ngày), `MAX_CLOUD_COVER_PCT = 100`.

- **Tier 1**: 11 scene trả về, 11 có clear-fraction, 0 no-data.
- **`aoi_clear_fraction`**: min = 0.000, median = 0.000, mean = 0.023,
  max = 0.185.
- **Histogram**: `<0.5` = 11; mọi bucket còn lại = 0.
- **Survival**: **0 scene ở MỌI ngưỡng 0.5 → 0.9.**

**Kết luận: quang học MÙ HOÀN TOÀN ở vụ mưa.** Xuyên suốt 45 ngày cao điểm Vụ Mùa,
**0 scene dùng được**. Đây là ràng buộc khó nhất đối với hướng MRV chỉ-quang-học
cho vùng này.

## 5. Kết quả B — Vụ Đông-Xuân 2025–26 (vụ khô)

Cửa sổ `2026-01-15 .. 2026-06-30`, `MAX_CLOUD_COVER_PCT = 100`.

- **Tier 1**: 38 scene trả về, 38 có clear-fraction, 0 no-data.
- **`aoi_clear_fraction`**: min = 0.000, median = 0.000, mean = 0.163,
  max = 1.000.
- **Histogram**: `<0.5` = 31 · `0.5–0.7` = 2 · `0.7–0.8` = 0 · `0.8–0.9` = 1 ·
  `>=0.9` = 4.
- **Survival sweep**: `0.5 → 7` · `0.6 → 6` · `0.7 → 5` · `0.8 → 5` · `0.9 → 4`.
- Ở **`MIN_CLEAR_FRACTION = 0.5`: 7/38 scene dùng được (~18%).**

Survival sweep không-phẳng chính là hành vi mà việc vá metric cần khôi phục:
`MIN_CLEAR_FRACTION` giờ đã tách được scene quang khỏi scene mây một cách có nghĩa.

## 6. Chuỗi 7 scene mùa vụ

Bảy scene sống sót (từ `data/processed/spectral_indices.csv`; giá trị làm tròn,
độ chính xác đầy đủ trong file):

| Ngày | clear | NDVI | NDWI | LSWI | Pha |
|---|---|---|---|---|---|
| 27/1 | 0.608 | 0.049 | −0.005 | 0.194 | ngập / đổ ải |
| 13/3 | 0.999 | 0.313 | −0.265 | 0.294 | sinh trưởng sớm |
| 7/4 | 1.000 | 0.445 | −0.392 | 0.224 | sinh trưởng |
| 12/4 | 1.000 | 0.307 | −0.247 | 0.234 | bất thường — xem §7 |
| 27/5 | 0.566 | 0.546 | −0.496 | 0.170 | đỉnh NDVI (trổ) |
| 1/6 | 0.851 | 0.490 | −0.457 | 0.121 | sau đỉnh |
| 21/6 | 0.964 | 0.274 | −0.289 | 0.154 | chín / gặt |

Đọc theo trình tự, chuỗi vẽ ra một cung mùa vụ hợp lý: ngập/đổ ải → sinh trưởng →
đỉnh trổ → chín/gặt. **Xác nhận chéo pha ngập**: NDWI cao nhất (−0.005, giống nước
nhất) rơi đúng vào ngày NDVI thấp nhất (27/1) — hai chỉ số độc lập cùng đồng thuận
rằng 27/1 là giai đoạn ngập, thực vật thấp.

## 7. Giới hạn (nêu rõ ràng, không giấu)

1. **Hố 45 ngày (27/1 → 13/3)** nuốt trọn giai đoạn **CẤY** (tháng 2). Giai đoạn
   đó đơn giản là không được quan sát trong chuỗi này.
2. **Bất thường 12/4**: NDVI tụt từ 0.445 (7/4) xuống 0.307 (12/4) trong 5 ngày,
   dù **cả hai scene đều `clear` = 1.000**. Đây là điều **CHƯA GIẢI THÍCH ĐƯỢC —
   một open question.** TUYỆT ĐỐI KHÔNG được gọi đó là sự kiện tháo nước AWD; ở đây
   không có cơ sở cho điều đó.
3. **27/5 (`clear` 0.566) và 1/6 (`clear` 0.851)** dựa trên ít pixel quang hơn các
   scene ≈1.0, nên **kém đại diện về không gian hơn**.
4. **Giới hạn partial-footprint** (đã ghi ở
   [spec 05](../specs/05-clear-fraction-measures-cloud.md)): một AOI chỉ được
   footprint phủ một phần sẽ cho fraction tính trên phần được phủ, có thể đọc cao
   dù một phần AOI không được quan sát.
5. **Đây là chu kỳ MÙA VỤ (vật hậu), KHÔNG phải chu kỳ ngập/khô AWD.** AWD dao động
   ở nhịp dưới-tháng; muốn phân giải được cần ảnh dày hơn rất nhiều **và** cấp thửa.
   Không được đọc bất cứ điều gì ở đây thành "đã phát hiện AWD."
6. **Chưa có ground truth thực địa.** Không tuyên bố con số độ chính xác % nào cho
   bất kỳ tín hiệu nào.

## 8. Kết luận chiến lược

Trên bằng chứng từ chính số đo của AOI này:

- **Chỉ-quang-học là ĐỦ để giám sát vật hậu mùa vụ ở Đông-Xuân** — 7 scene dùng
  được vẽ ra một cung mùa vụ đọc được.
- **Chỉ-quang-học KHÔNG đủ cho MRV quanh năm** — Vụ Mùa trả về **0 scene dùng được
  trong 45 ngày** — **cũng không đủ để phát hiện sự kiện ngập/khô AWD**, vốn ở nhịp
  dưới-tháng.

Do đó **Sentinel-1 SAR (xuyên mây) là hướng đi phase 2** cho phủ quanh năm và độ
nhạy với sự kiện AWD. Đây là kết luận rút ra từ các con số đo trên chính AOI thí
điểm này, không phải trích dẫn từ tài liệu.
