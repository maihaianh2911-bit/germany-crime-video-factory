# Bàn giao dự án (đọc trước khi làm việc với chủ kênh)

Repo này làm **video vụ án tiếng Đức** (dọc 1080×1920, 30 fps, ~2 phút) **kiểu hồ sơ vụ án** theo video mẫu của chủ kênh (`00-video-mau/MAU-HO-SO.mp4`): ảnh trắng đen in báo trên bàn gỗ tối, băng giấy dán hiện đúng lúc giọng đọc nói tới, tờ hồ sơ gõ chữ, sổ ghi có dấu ✓, số lớn, đồ vật cắt rời, dây đỏ, tiêu đề chương, phụ đề hộp trắng; giọng và chữ tiếng Đức, viết cho người xem Đức. Xây ngày 13/11/2026 cùng lúc với repo song sinh `maihaianh2911-bit/japan-crime-video-factory` (tiếng Nhật): hai repo **cùng mã**, chỉ khác `prompts/channel.json` (ngôn ngữ, giọng, chữ ghi trên ảnh AI) và `prompts/readings.json`. Cách vận hành giống các repo khác của chủ kênh (phiếu → Claude chia lời → máy tạo giọng, tìm ảnh → Claude chọn ảnh, xem trước → máy dựng → Claude kiểm tra). Mã lấy từ `japan-archive-video-factory` (dây chuyền, xem trước, ảnh từ kho tự do) và `germany-news-video-factory` (kiểm tra giọng tiếng Đức).

## Chủ kênh

- GitHub `maihaianh2911-bit`. Nói chuyện **bằng tiếng Việt, ngắn gọn, dễ hiểu, không thuật ngữ**.
- Muốn **tự động hoàn toàn**: mở phiếu có kịch bản là có video; góp ý thì sửa trên cùng phiếu.
- Chỉ dùng **hạn mức gói Claude** (dùng chung với các repo khác), không dùng Claude API trả tiền; không giảm chất lượng.

## Quyết định của chủ kênh (giữ nguyên khi làm)

- 13/11: *"Tạo 2 repo mới cho dạng vụ án, chia ra Đức/Nhật"* + video mẫu → hai repo `germany-crime-video-factory` và `japan-crime-video-factory`, chia **theo ngôn ngữ kênh** (repo Đức: giọng và chữ tiếng Đức; repo Nhật: tiếng Nhật; vụ án ở nước nào cũng được).
- ~~13/11: dựng như mẫu cũ (một ảnh cũ, chữ vàng 2–3 từ, tiêu đề trên cùng)~~ → **14/11: chủ kênh gửi video mẫu mới (kiểu hồ sơ) và chọn: "Thay hẳn kiểu cũ, giảm xuống còn 2 phút, làm cho phù hợp với người Đức hơn".** Người Đức: giọng kể điềm tĩnh, không giật gân; ngày giờ, số theo kiểu Đức; người chưa bị kết án không gọi là thủ phạm, tên nghi phạm viết tắt họ (Pressekodex); chữ trên hình là từ hồ sơ tiếng Đức (`AKTE`, `UNGELÖST`, `KEINE ÜBEREINSTIMMUNG`) — chi tiết trong `AGENT_CRIME.md` §1.3.
- 14/11: repo Nhật **chưa đổi** sang kiểu hồ sơ: chủ kênh chưa trả lời có đổi luôn không. Hỏi trước khi chép mã sang.
- 13/11: hình ảnh: **ảnh thật trước + AI minh họa** — ưu tiên ảnh thật (nơi xảy ra, báo cũ, tòa án); thiếu thì ảnh AI, **luôn có chữ "KI-Illustration"** trên ảnh và **không vẽ giống mặt người thật**. Không máu me, không chữ giả (báo, hồ sơ giả).

## Quy trình

Phiếu `[Vụ án] …` → `.github/workflows/crime.yml` + `scripts/crime/run.py` (máy) và `AGENT_NIGHTLY.md` → `AGENT_CRIME.md` (Claude):

`crime-plan` Claude viết `crime/<N>/script.json` (tiêu đề, câu đọc, từ khóa tìm ảnh, lời tạo ảnh AI) → `crime-voice` máy tạo giọng (11labs, một job mỗi câu), Whisper kiểm tra phát âm và lấy thời điểm từng từ, tìm ảnh (Commons, Openverse, Europeana, Thư viện Quốc hội Mỹ), tạo ảnh AI → `crime-pick` Claude xem ảnh, chọn, đặt khung, xem trước (`scripts/crime/preview.py`), viết `picks.json` → `crime-render` máy dựng (`src/crime/CrimeV.tsx`, Remotion) → `crime-check` Claude xem bảng cảnh → `crime-done`. Bình luận của chủ kênh → `crime-fix`. Kết quả: nhánh `renders`, thư mục `crime/<N>/`.

Bố cục đo từ video mẫu: `scripts/crime/layout.py` (vị trí có tên: `main`, `top`, `g1`…, `bl`…). Claude viết từng cảnh trong `picks.json` (ảnh, băng giấy, thẻ, số, dây — mỗi thứ hiện đúng lúc một từ được đọc, `"at": "3/Blut"`), `build.py` tính ra từng điểm ảnh, `src/crime/CrimeV.tsx` vẽ. Bản xem trước (`preview.py`) chụp khung hình bằng chính bộ dựng video (Remotion), nên giống hệt video. Phụ đề chia đoạn: `scripts/crime/captions.py` (`subs`). Ảnh trắng đen in báo, hình dán cắt rời, nền gỗ: `scripts/crime/prep.py`. Phông theo ngôn ngữ: `scripts/crime/fonts.json`. Tạo ảnh AI (cả đồ vật trên nền trắng để cắt rời): `scripts/gen_images.py`.

## Trạng thái (13/11/2026)

- 13/11: mã kiểu cũ đã viết và thử bằng dữ liệu giả cả tiếng Nhật và tiếng Đức (`tests/crime_units.py`, `tests/crime_smoke.py --still`). Trên GitHub: workflow **Kiểm tra mã** chạy xanh, các nhãn `crime-*` đã tạo, tác vụ Claude chung (`AGENT_NIGHTLY.md` của `japan-video-factory`) đã kiểm tra phiếu vụ án của cả hai repo. **Chưa có video thật nào** (chưa có nhánh `renders`).
- 13/11 (sửa sau kiểm tra): chữ vàng tiếng Nhật không còn cắt giữa từ (思いま|すか, できな|かった, chữ nhỏ ょ ở đầu cụm), một dòng chữ rộng hơn (12 chữ Nhật); chữ tiếng Đức giữ dấu chấm của số thứ tự và chữ viết tắt (`AM 1. JULI`, `DR. MÜLLER`); bản xem trước đặt tiêu đề, nhãn và chữ đúng chỗ như video, chữ Đức nghiêng như video; vòng đỏ hình bầu dục trong video không còn bị xoay sai hình.
- Còn thiếu, theo thứ tự:
  1. Secrets (Settings → Secrets and variables → Actions): `VN11_API_KEY` (giọng đọc; 14/11 chủ kênh đã lưu với tên `VOICE`, crime.yml nhận cả hai tên), `CLAUDE_TASK_URL` + `CLAUDE_TASK_TOKEN` (cùng giá trị như `japan-video-factory`).
  2. Khóa tạo ảnh AI (không bắt buộc) — **chủ kênh chưa chọn**: một trong `OPENAI_API_KEY` (đẹp nhất, trả tiền theo ảnh), `GEMINI_API_KEY` (đẹp, trả tiền theo ảnh), hoặc `CF_ACCOUNT_ID` + `CF_API_TOKEN` (Cloudflare, miễn phí mỗi ngày một số ảnh, kém hơn). Chưa có khóa thì video chỉ dùng ảnh thật (và ảnh chủ kênh gửi kèm phiếu).
  3. Video thật đầu tiên: mở một phiếu `[Vụ án] …`.
- 14/11: **đổi sang kiểu hồ sơ** (video mẫu mới). Đã thử bằng dữ liệu giả (mọi loại: ảnh, băng giấy, tờ hồ sơ, sổ ✓, bìa hồ sơ, số lớn, hình dán, dây đỏ, vòng tròn, tiêu đề chương) và dựng thử 30 giây bằng ảnh cắt từ video mẫu (chỉ để kiểm tra, không đăng). Dựng ~4 khung hình/giây: video 2 phút mất ~15–20 phút trên GitHub.
- Sau video đầu tiên: đo lại tốc độ đọc trong `AGENT_CRIME.md`, xem cỡ băng giấy, cỡ phụ đề và độ đậm của lưới chấm ảnh, hỏi chủ kênh.

## Lưu ý kỹ thuật

- `gh` trong phiên cloud chỉ dùng REST (`gh api …`), lệnh GraphQL lỗi.
- Wikimedia chặn tải ảnh gốc kích thước tùy ý (lỗi 429): chỉ lấy các cỡ chuẩn (1920, 3840 px) — đã xử lý trong `scripts/find_images.py`.
- ffmpeg trên máy GitHub lấy từ gói pip `imageio-ffmpeg` (xem `scripts/crime/ff.py`). Ghim `faster-whisper==1.1.1` + `av==13.1.0` (PyAV mới làm hỏng faster-whisper).
- Từ hay bị giọng đọc sai ghi vào `prompts/readings.json`.
- Phông (`scripts/crime/fonts.json`): tiếng Đức Source Sans 3 (phụ đề), Courier Prime (chữ máy đánh chữ), Merriweather (tên, tiêu đề chương), Patrick Hand (chữ viết tay); tiếng Nhật Noto Sans JP, M PLUS 1 Code, Noto Serif JP, Yomogi. `scripts/crime/get_fonts.sh` tự chọn theo `prompts/channel.json`.
- Wikimedia Commons bị chặn trong phiên Claude trên cloud (lỗi 403 ở proxy): tìm ảnh chỉ chạy trên GitHub.
