# Milestone 1 Report — MRV Carbon Monitoring Pipeline

**Phạm vi**: Pilot stage, đồng bằng sông Hồng (Bắc Ninh), Việt Nam
**Ngày**: 07/2026
**Bản**: Tiếng Việt ([English version](01-milestone-one-report.en.md))

**Trạng thái tại thời điểm báo cáo (07/2026)**: chưa có lần chạy tích
hợp (integration run) nào với Google Earth Engine thật; chưa có
validation với dữ liệu thực địa/ground-truth; dự án đang ở giai đoạn
Milestone 1 / technical MVP cục bộ.

## 1. Tóm tắt điều hành

Canh tác lúa ngập nước liên tục là nguồn phát thải methane lớn tại Việt
Nam; kỹ thuật tưới ngập-khô xen kẽ (AWD) giảm được phát thải này nhưng
thiếu một cơ chế đo lường, báo cáo, xác minh (MRV) chi phí thấp và có
thể mở rộng ở quy mô nông hộ nhỏ. Dự án MRV Carbon Monitoring Pipeline
xây dựng một hệ thống dựa trên ảnh vệ tinh Sentinel-2 và Google Earth
Engine để ước tính việc áp dụng AWD thông qua các chỉ số phổ phản ánh
trạng thái ngập/khô của ruộng. Tính đến thời điểm báo cáo, hai module
đầu của pipeline (`data_collection`, `features`) đã có code chạy được,
được kiểm thử đầy đủ bằng cách giả lập (mock) toàn bộ lệnh gọi Google
Earth Engine, với 38 unit test pass và một quy trình packaging chuẩn
(`pyproject.toml` + editable install).

Dự án hiện ở giai đoạn pre-traction, đã hoàn thành một technical MVP
chạy cục bộ; bước tiếp theo cần thiết là chạy thử nghiệm tích hợp
(integration run) với thông tin xác thực Google Earth Engine thật và
một vùng thí điểm (AOI) cụ thể tại Bắc Ninh.

## 2. Bài toán đặt ra

Đo lường chu kỳ ngập-khô trên từng thửa ruộng nhỏ là một bài toán khó vì
ba lý do chính. Thứ nhất, cảm biến độ ẩm đất hoặc mực nước lắp đặt tại
ruộng gần như không tồn tại ở quy mô nông hộ nhỏ tại Việt Nam — chi phí
lắp đặt và bảo trì trên diện rộng là không khả thi. Thứ hai, ranh giới
thửa ruộng thường nhỏ, không đồng đều và chưa có bộ dữ liệu ranh giới
(parcel boundary) chuẩn hoá, công khai, đủ chi tiết. Thứ ba, việc kiểm
tra thực địa thủ công theo mùa vụ, trên diện rộng, tốn chi phí và không
mở rộng được.

Bài toán này có ý nghĩa trực tiếp với MRV và carbon accounting: việc
phát hành tín chỉ carbon dựa trên giảm phát thải từ AWD đòi hỏi bằng
chứng đo lường có thể lặp lại và kiểm chứng độc lập, không chỉ dựa vào
tự khai báo của nông hộ hay đơn vị triển khai. Khoảng trống hiện tại là
thiếu một phương pháp remote-sensing chi phí thấp, mở rộng được, và phù
hợp với đặc thù Việt Nam — thửa ruộng nhỏ, mật độ mây cao trong mùa mưa,
và hạ tầng đo đạc thực địa còn hạn chế.

## 3. Cách tiếp cận của dự án

Pipeline sử dụng ảnh Sentinel-2 Surface Reflectance, truy vấn và xử lý
qua Google Earth Engine (GEE) — toàn bộ tính toán (lọc mây, tính chỉ số
phổ, thống kê vùng) chạy phía server của GEE, không cần tải và xử lý
raster dung lượng lớn cục bộ. Ba chỉ số phổ được dùng làm tín hiệu proxy
cho trạng thái nước và thực vật trên ruộng: NDVI (thực vật), NDWI theo
công thức McFeeters (nước bề mặt), và LSWI (độ ẩm bề mặt/nước, nhạy với
băng SWIR). Đây là các chỉ số proxy gián tiếp — không đo methane hay độ
ẩm đất trực tiếp.

Ở giai đoạn hiện tại, pipeline tính time-series zonal statistics (giá
trị trung bình mỗi chỉ số) trên toàn bộ vùng thí điểm (AOI) theo từng
ảnh vệ tinh — bước nền tảng trước khi xây module phát hiện chu kỳ
ngập/khô ở bước tiếp theo. Hướng tiếp cận này phù hợp với bối cảnh thị
trường đang phát triển vì dựa hoàn toàn trên dữ liệu vệ tinh mở
(Sentinel-2, miễn phí), một stack mã nguồn mở, và hạn ngạch tính toán
miễn phí của GEE cho mục đích nghiên cứu — không phụ thuộc vào hạ tầng
vệ tinh thương mại hay chi phí hạ tầng cloud lớn để bắt đầu.

## 4. Kiến trúc hệ thống / Pipeline overview

Pipeline được thiết kế theo 4 module nối tiếp:

- **`data_collection`** — đã hoàn thành: truy vấn Sentinel-2 qua GEE
  theo AOI và khoảng thời gian, lọc mây, xuất scene manifest.
- **`features`** — đã hoàn thành: tính chỉ số phổ và zonal statistics
  từ manifest, xuất bảng dữ liệu dạng CSV.
- **`baseline`** — kế hoạch: phát hiện chu kỳ ngập/khô bằng phương pháp
  rule-based (ngưỡng trên NDWI/LSWI), chưa triển khai code.
- **`reporting`** (API + dashboard) — kế hoạch: sinh báo cáo MRV cấp
  field/parcel và hiển thị qua FastAPI + Streamlit, chưa triển khai
  code.

Luồng dữ liệu thực tế theo code hiện có: file GeoJSON định nghĩa AOI
(chuẩn bị bên ngoài hệ thống, lưu tại `data/external/aoi/`) → scene
manifest JSON tại `data/raw/sentinel2_manifest.json` (do `data_collection`
sinh ra) → bảng chỉ số phổ CSV tại `data/processed/spectral_indices.csv`
(do `features` sinh ra) → module `baseline` và `reporting` (chưa xây,
sẽ tiêu thụ artifact ở bước trên).

Ba nguyên tắc thiết kế xuyên suốt: (1) toàn bộ tính toán trên pixel chạy
phía server của GEE, chỉ kéo về các giá trị scalar nhỏ qua `getInfo()`;
(2) mọi artifact trung gian đều nhỏ và dạng bảng/JSON (không xuất raster
ảnh); (3) toàn bộ logic có thể kiểm thử cục bộ bằng cách giả lập hoàn
toàn các lệnh gọi `ee.*`, không cần mạng hay thông tin xác thực thật để
chạy test. Toàn bộ pipeline được xây theo quy trình spec-driven: viết
spec ngắn → đề xuất plan → chờ duyệt → triển khai → viết test → chạy
verify, ghi rõ trong `CLAUDE.md`.

## 5. Những gì đã hoàn thành ở Milestone 1

**`data_collection`** (`src/mrv/data_collection/`): truy vấn bộ dữ liệu
Sentinel-2 Surface Reflectance (`COPERNICUS/S2_SR_HARMONIZED`) trên GEE
theo AOI và khoảng ngày cấu hình qua `.env`; áp dụng cloud mask theo
band Scene Classification Layer (SCL) với baseline có chủ đích thận
trọng (loại bỏ cả class 7/Unclassified khỏi tập pixel hợp lệ, không mặc
định coi là sạch); sinh scene manifest JSON gồm `image_id`,
`sensing_date`, `mgrs_tile`, `cloudy_pixel_percentage`,
`aoi_clear_fraction`, và `scene_count`.

**`features`** (`src/mrv/features/`): đọc scene manifest, fetch lại
từng ảnh theo `image_id`, tính NDVI/NDWI/LSWI server-side bằng
`ee.Image.normalizedDifference()`, tính trung bình theo vùng (zonal
mean, scale 20m) trên toàn AOI cho mỗi chỉ số, lọc bỏ scene có độ che
phủ mây vượt ngưỡng cấu hình (`min_clear_fraction`), và ghi kết quả ra
`data/processed/spectral_indices.csv`.

**Packaging**: dự án được đóng gói bằng `pyproject.toml` (setuptools,
src-layout) và cài đặt qua `pip install -e .` — đã verify chạy được
`python -m mrv.data_collection.collect` từ thư mục gốc repo mà không
cần cấu hình `PYTHONPATH` thủ công.

**Documentation**: `CLAUDE.md` mô tả kiến trúc mục tiêu và quy trình
làm việc; ba spec module (`docs/specs/00-project-overview.md`,
`01-data-collection.md`, `02-features.md`); một decision note về hướng
tiếp cận packaging (`docs/decisions/01-packaging-approach.md`).

**Testing**: **38 unit test pass** trong `tests/unit/`, toàn bộ giả lập
(mock) các lệnh gọi `ee.*`, chạy được hoàn toàn cục bộ không cần mạng
hay thông tin xác thực thật. Ý nghĩa của con số này: chứng minh logic
truy vấn, lọc, cloud-mask, và tính chỉ số đúng theo đặc tả thiết kế —
nhưng **chưa** chứng minh pipeline chạy đúng trên dữ liệu vệ tinh thật,
vì chưa có lần chạy tích hợp (integration run) nào với GEE thật.

Cần nhấn mạnh: repository hiện ở mức **technical MVP chạy cục bộ**
(local-only), chưa qua triển khai production, chưa có deployment, và
chưa có lần chạy nào với dữ liệu vệ tinh thật.

## 6. Các quyết định kỹ thuật quan trọng và lý do

**Vì sao chọn Sentinel-2**: dữ liệu miễn phí, chu kỳ quay lại khoảng 5
ngày, độ phân giải không gian phù hợp để quan sát ruộng lúa — so với
các lựa chọn ảnh vệ tinh thương mại có chi phí cao hơn đáng kể cho một
dự án giai đoạn pilot.

**Vì sao chọn Google Earth Engine**: tránh phải tải và xử lý raster
dung lượng lớn trên máy cục bộ; tận dụng hạ tầng tính toán server-side
miễn phí cho mục đích nghiên cứu, phù hợp với ràng buộc compute cục bộ
của dự án ở giai đoạn hiện tại.

**Vì sao ưu tiên cloud masking + scene filtering thay vì chỉ lấy ảnh
trời quang**: mùa mưa ở Bắc Bộ có mật độ mây cao; nếu chỉ giữ lại ảnh
hoàn toàn không mây, phần lớn time-series sẽ bị loại bỏ, không đủ dữ
liệu để theo dõi chu kỳ ngập/khô. Quyết định là chấp nhận ảnh có mây một
phần, kết hợp lọc ở cấp scene (ngưỡng % mây) và masking ở cấp pixel
(SCL) để giữ được nhiều thời điểm quan sát hơn mà vẫn kiểm soát chất
lượng.

**Vì sao làm AOI-level trước, parcel-level sau**: hiện chưa có bộ dữ
liệu ranh giới thửa ruộng (parcel boundary) đáng tin cậy cho vùng thí
điểm. Quyết định này được nêu rõ trong cả hai spec `01-data-collection.md`
và `02-features.md`, nhằm tránh overclaim về độ chi tiết của kết quả khi
chưa có dữ liệu ranh giới phù hợp.

**Vì sao dùng spec-driven workflow và unit-test trước khi chạy tích
hợp**: chạy thử trên GEE thật tiêu tốn thời gian và hạn ngạch tính toán;
việc giả lập toàn bộ `ee.*` cho phép xác minh logic nhanh, không tốn
chi phí, và lặp lại được nhiều lần trước khi thực hiện một lần chạy thật
— giảm rủi ro debug trên dữ liệu thật do lỗi ở tầng logic đáng lẽ có thể
phát hiện sớm hơn.

## 7. Giới hạn hiện tại và rủi ro

- **Chưa có parcel boundaries**: kết quả hiện tại chỉ ở cấp AOI, chưa
  thể báo cáo ở cấp từng thửa ruộng thật.
- **Chưa chạy live GEE thật**: toàn bộ 38 test đều dựa trên mock; pipeline
  chưa được xác minh trên dữ liệu vệ tinh thật.
- **Chưa có ground-truth/field validation**: chưa có dữ liệu thực địa
  để đối chiếu xem NDVI/NDWI/LSWI có phản ánh đúng chu kỳ AWD thật hay
  không.
- **Chỉ số phổ là proxy gián tiếp**: không đo methane hay độ ẩm đất
  trực tiếp — đây là giới hạn về bản chất phương pháp, không phải lỗi
  triển khai.
- **Phụ thuộc dữ liệu công khai và chất lượng cloud mask**: pipeline
  dựa vào Sentinel-2 và (dự kiến) ranh giới hành chính công khai
  (GADM); band SCL dùng để lọc mây không hoàn hảo tuyệt đối, đã được
  ghi nhận rõ trong `docs/specs/01-data-collection.md`.

## 8. Bước tiếp theo / Milestone 2 roadmap

1. Chạy integration run thật: hoàn tất đăng ký Google Earth Engine, xác
   định AOI cụ thể tại Bắc Ninh qua `notebooks/explore_bac_ninh_aoi.py`,
   sau đó chạy `data_collection` và `features` với dữ liệu thật.
2. Xây module `baseline` — phát hiện chu kỳ ngập/khô bằng phương pháp
   rule-based trên NDWI/LSWI, theo đúng roadmap trong
   `docs/specs/00-project-overview.md`.
3. Mở rộng xuống parcel-level khi có nguồn dữ liệu ranh giới thửa ruộng
   đáng tin cậy.
4. Thực hiện validation với dữ liệu thực địa hoặc ảnh vệ tinh độ phân
   giải cao hơn để kiểm chứng tín hiệu proxy.
5. API (FastAPI) và dashboard (Streamlit): stretch goal, chưa có mốc
   thời gian cụ thể — dự án ưu tiên đúng đắn về kỹ thuật hơn tốc độ.

## 9. Cách chạy dự án (cho reviewer kỹ thuật)

```bash
python -m venv .venv
.venv/Scripts/pip install -e .        # macOS/Linux: .venv/bin/pip install -e .

cp .env.example .env
# Điền GEE_PROJECT_ID, GEE_SERVICE_ACCOUNT_KEY_PATH, AOI_PATH và các
# biến còn lại trong .env — xem docs/setup/gee_setup.md để đăng ký GEE.

python -m mrv.data_collection.collect  # → data/raw/sentinel2_manifest.json
python -m mrv.features.compute         # → data/processed/spectral_indices.csv

pytest tests/unit/ -v                  # 38 passed
```

Hai lệnh chạy pipeline thật (`mrv.data_collection.collect` và
`mrv.features.compute`) cần thông tin xác thực Google Earth Engine và
một AOI cụ thể đã được cấu hình — đây là cách để chạy khi đã có đủ điều
kiện đó, **không phải kết quả đã được chạy thành công** trong quá trình
phát triển tới thời điểm báo cáo này.

## 10. Trạng thái dự án / Team

Dự án hiện do một single contributor phát triển. Trạng thái: pre-
traction — technical MVP cục bộ đã hoàn thành ở mức mô tả tại mục 5,
integration run thật và module `baseline` đang chờ triển khai. Focus
địa lý: Việt Nam, thí điểm tại Bắc Ninh, đồng bằng sông Hồng. Dự án mở
với các cơ hội hợp tác, pilot, hoặc góp ý kỹ thuật — liên hệ qua
repository GitHub của dự án.
