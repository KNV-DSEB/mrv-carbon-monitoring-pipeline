# Báo cáo Phát hiện SAR — MRV Carbon Monitoring Pipeline

**Phạm vi**: Lần chạy Sentinel-1 SAR đầu tiên, AOI thí điểm, Bắc Ninh, Việt Nam
**Ngày**: Tháng 7/2026
**Phiên bản**: Tiếng Việt ([English version](03-sar-findings-report.en.md))

**Trạng thái**: Lần chạy Sentinel-1 đầu tiên trên AOI thí điểm, khoá quỹ đạo về
**DESCENDING / 91** cho cả hai vụ. Nó chứng minh độ phủ quanh năm không mây và
kiểm chứng chéo tín hiệu ngập của optical bằng một cảm biến độc lập. **Chưa có
kiểm chứng thực địa / ground-truth, và không tuyên bố bất kỳ con số độ chính xác %
nào.** Mọi số liệu lấy từ `data/processed/s1_backscatter.csv`.

## 1. Tóm tắt điều hành

Sentinel-1 SAR băng C **giải xong bài toán phủ quanh năm** mà optical không làm
được (báo cáo 02): nơi lần chạy optical mùa mưa trả về **0 scene dùng được**, SAR
trả về một chuỗi dày, không mây, ở cả hai vụ. Chuỗi SAR còn **kiểm chứng chéo độc
lập tín hiệu ngập của optical** — VV backscatter thấp nhất vụ khô rơi cách scene
ngập của optical đúng hai ngày, qua một cơ chế vật lý hoàn toàn khác — và nó **lấp
đúng cái hố 45 ngày của optical** đã khiến baseline pha mùa vụ phải trả
`undetermined` tại đỉnh NDVI thật.

Điều SAR **CHƯA** làm được: phát hiện *sự kiện* ngập/khô AWD dưới-tháng. Đó vẫn là
bài toán cấp thửa, chu kỳ lặp dày hơn (Mục 5).

## 2. Cấu hình

- **Khoá quỹ đạo: DESCENDING / relative orbit 91**, áp cho cả hai cửa sổ. Đây là
  **orbit DUY NHẤT mạnh ở cả hai vụ**, nên backscatter của nó so sánh được xuyên
  năm — quỹ đạo ascending/khác chụp AOI ở góc tới khác và không được trộn vào
  (spec 07 R2).
- Cả hai cửa sổ truy vấn trên `COPERNICUS/S1_GRD`, chế độ IW, VV+VH, **không lọc
  mây** (SAR xuyên mây), trung bình AOI tính ở thang linear power rồi báo cáo ở dB
  (spec 07 R3).

## 3. Độ phủ — optical vs SAR (cả hai vụ)

| Vụ (cửa sổ) | Optical dùng được | SAR dùng được | Day-gap SAR (min/median/max) |
|---|---|---|---|
| Vụ Mùa `2025-07-01..08-15` | **0** | **5** | 6 / 9 / 12 |
| Đông-Xuân `2026-01-15..06-30` | **7** | **14** | 7 / 12 / 24 |

SAR trả về **0 scene có AOI ngoài footprint** ở cả hai cửa sổ (optical thường
xuyên rơi vào mép swath → no-data). Kết quả mùa mưa là kết quả quyết định:
**5 scene SAR dùng được nơi optical có 0** — đúng như dự đoán khả-chứng-sai của
spec 07.

## 4. Phát hiện chính — hai cảm biến độc lập, một sự kiện ngập

Chuỗi SAR Đông-Xuân (DESCENDING/91, 14 scene):

| Ngày | VV (dB) | VH (dB) | ghi chú |
|---|---|---|---|
| 2026-01-17 | −7.53 | −14.48 | |
| 2026-01-29 | **−11.32** | −19.10 | **VV min (z = −2.00)** |
| 2026-02-10 | −10.22 | −18.38 | VV thấp (z = −1.06) |
| 2026-02-22 | −10.75 | −19.20 | VV thấp (z = −1.51) |
| 2026-03-18 | −9.16 | −18.73 | |
| 2026-03-30 | −8.21 | −18.05 | |
| 2026-04-11 | −7.54 | −16.92 | |
| 2026-04-23 | −8.36 | −16.23 | |
| 2026-05-05 | −8.06 | −15.86 | |
| 2026-05-17 | −8.53 | −15.10 | |
| 2026-05-29 | −9.11 | −14.50 | |
| 2026-06-10 | −8.11 | **−14.05** | **VH max** |
| 2026-06-22 | −9.08 | −15.94 | |
| 2026-06-29 | −9.77 | −16.47 | |

(VV trung bình −8.98 dB, sd 1.17.)

**Kiểm chứng chéo pha ngập.** VV thấp nhất vụ là **−11.32 dB ngày 29/1**
(z = −2.00). Ruộng ngập là mặt nước phẳng phản xạ gương, dội sóng radar đi khỏi vệ
tinh → VV thấp. Optical, một cách độc lập, đánh dấu **27/1** là pha ngập/đổ ải
(NDVI 0.049 — thấp nhất chuỗi; NDWI −0.005 — giống nước nhất). **Hai cơ chế vật lý
khác nhau, cách nhau hai ngày, cùng chỉ vào một sự kiện ngập.**

**Một cửa sổ ngập kéo dài.** VV thấp bất thường ở **ba ngày LIÊN TIẾP** — 29/1
(z = −2.00), 10/2 (z = −1.06), 22/2 (z = −1.51) — cho thấy cửa sổ ngập kéo dài từ
cuối tháng 1 sang tháng 2.

**SAR lấp đúng lỗ hổng đã làm hỏng optical.** Trong ba điểm đó, **10/2 và 22/2 nằm
gọn trong hố 45 ngày của optical** (27/1 → 13/3) — chính cái hố đã che giai đoạn
cấy và sườn lên của đỉnh NDVI, buộc baseline pha mùa vụ phải trả `undetermined`
(báo cáo 02 / spec 06). SAR quan sát đúng nơi optical bị mù.

**VH bám theo sinh trưởng tán.** VH tăng đều từ **−19.2 dB (22/2)** lên
**−14.05 dB (10/6)**, khớp với sinh khối tán tăng dần — cùng cung đường mà NDVI
optical vẽ ra.

## 5. Đối chiếu thực địa sơ bộ (KHÔNG phải kiểm chứng)

Một cuộc hỏi nhanh qua điện thoại với nông dân địa phương trong khu vực AOI cho
biết ruộng **ngập vào cuối tháng 1** — khớp với cả VV minimum của SAR (29/1) lẫn
scene ngập của optical (27/1). Đây là **giai thoại, không phải kiểm chứng**: vài
cuộc điện thoại dựa trên hồi tưởng, n nhỏ, không có quy trình ground-truth có cấu
trúc, không định vị cấp thửa. Nó chỉ được nêu như một phép kiểm tra độc lập yếu
cùng hướng với hai cảm biến — không bao giờ là một con số độ chính xác đo được.

## 6. Giới hạn (nêu rõ ràng, không giấu)

1. **−11.3 dB là ngập VỪA, không phải mặt nước hở.** Mặt nước hở thường đọc −15
   đến −20 dB VV. Trung bình AOI 2 km² gộp cả ruộng lẫn bờ, đường, mép làng, làm
   pha loãng tín hiệu. **Không tuyên bố "phát hiện mặt nước hở".**
2. **n = 14, một vụ, một AOI, chưa có ground truth.** Không nêu con số độ chính
   xác % nào cho bất kỳ tín hiệu nào.
3. **Đây là pha ngập MÙA VỤ (kéo dài nhiều tuần), chưa phải sự kiện AWD.** Chu kỳ
   lặp 12 ngày (max gap 24) **sẽ trượt các lần khô AWD 5–10 ngày** hoàn toàn.
4. **AWD có thể không đo được ở cấp AOI.** Hàng trăm thửa tháo nước không đồng bộ
   sẽ triệt tiêu nhau trong trung bình toàn AOI. Phát hiện AWD thật đòi hỏi phân
   tích **cấp THỬA** — ngoài scope hiện tại, ghi thẳng.
5. **Lọc speckle ở cấp AOI gần như không đáng kể** (~20.300 pixel đã tự triệt
   speckle trong phép trung bình); nó là future-proofing cho công việc cấp thửa.

## 7. Kết luận

Trên chính số đo của AOI này: **SAR giải xong bài toán phủ quanh năm** — đã chứng
minh, với mùa mưa (optical 0) giờ được phủ bởi 5 scene và vụ khô tăng gấp đôi
(7 → 14). **SAR chưa giải bài toán phát hiện sự kiện AWD**, vốn ở nhịp dưới-tháng
và sẽ cần độ phân giải cấp thửa cùng mật độ đa-quỹ-đạo — ngoài phạm vi dự án này.
Công việc dừng ở đây như một **sản phẩm portfolio kỹ thuật**, không phải một sản
phẩm thương mại (xem README để biết lý do).
