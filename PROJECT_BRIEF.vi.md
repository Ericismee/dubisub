# DubiSub — Bản định hướng dự án độc lập

Ngày soạn: 17/10/2026. Trạng thái: đặc tả để bắt đầu chat và dự án mới; chưa triển khai ứng dụng.

## 1. Mục tiêu và quyết định đã chốt

Xây dựng một công cụ chạy cục bộ để người làm nội dung tải phim lên, lấy lời thoại/phụ đề, dịch sang tiếng Việt, chỉnh sửa và xuất thành phẩm.

Người dùng chọn một trong hai chế độ ngay khi tạo dự án:

- **Review phim:** biến nội dung phim thành kịch bản tóm tắt, lời dẫn và nhận xét; lồng giọng AI và dựng một video review ngắn từ các đoạn phim được chọn.
- **Dịch/lồng tiếng phim:** giữ diễn biến và thời lượng của phim, dịch phụ đề và tạo một bản có phụ đề, thuyết minh hoặc lồng tiếng theo đoạn hội thoại.

Hai chế độ dùng chung nguồn phim, phụ đề, bản dịch, danh sách nhân vật, giọng đọc và kho kết quả. Mỗi chế độ có timeline và bản xuất riêng. Có thể tạo cả hai từ cùng một dự án mà không phải tải phim hay dịch lại.

Thư mục dự án: `D:/WorkSpace/dubisub`.

Đây là hệ thống riêng: mã nguồn, cấu hình, database, hàng đợi, dữ liệu và cổng chạy riêng. NotebookE chỉ là bối cảnh tham khảo; không sửa mã hoặc ghi dữ liệu vào NotebookE. Các dịch vụ AI có thể được dùng qua endpoint do người dùng cấu hình.

Tên sản phẩm đã chọn: **DubiSub**. Repo đề xuất: `ericismee/dubisub`. Film Review Studio là tên làm việc cũ; giữ nguyên thư mục D:/WorkSpace/dubisub.

## 2. Trải nghiệm sử dụng

### Bước 1 — Tạo dự án

Nhập tên phim/dự án, chọn Review hoặc Dịch/lồng tiếng; tải video và tùy chọn tải phụ đề. Hiển thị thời lượng, độ phân giải, các track âm thanh và phụ đề phát hiện được. Người dùng chọn track cần xử lý.

Bản đầu nhận MP4/MKV/MOV và phụ đề SRT/VTT/ASS. Khả năng đọc thực tế phải kiểm tra qua FFprobe; không chỉ dựa vào đuôi file.

### Bước 2 — Lấy lời thoại

Ưu tiên theo thứ tự:

1. Phụ đề người dùng tải lên.
2. Track phụ đề dạng văn bản nằm trong video.
3. Nhận dạng âm thanh bằng Whisper/faster-whisper hoặc endpoint ASR tương thích.
4. OCR chữ phụ đề dính trên hình: giai đoạn nâng cao, có bước chọn vùng phụ đề và kiểm tra kết quả.

Phân biệt track chữ với track hình ảnh như PGS/VobSub. Không coi phụ đề dính trên hình là một track văn bản có thể trích xuất trực tiếp.

Cho xem video cùng phụ đề gốc; bấm vào câu để nhảy đến thời điểm tương ứng. Cho sửa chữ, mốc thời gian, tách/gộp câu và đánh dấu đoạn cần kiểm tra.

### Bước 3 — Dịch và duyệt

Chọn ngôn ngữ nguồn hoặc tự phát hiện. Đích mặc định là tiếng Việt; hỗ trợ nhiều ngôn ngữ theo capability thực tế của từng provider, bao gồm English.

Hiển thị gốc và bản dịch cạnh nhau. Có từ điển tên nhân vật, địa danh, thuật ngữ và cách xưng hô; cho sửa rồi áp dụng nhất quán cho các đoạn sau. Mỗi lần dịch lưu một phiên bản.

Dịch theo nhóm câu có ngữ cảnh trước/sau, giữ ID câu và timecode. Kiểm tra thiếu câu, trùng ID, mất số, thay đổi tên và sai thứ tự. LLM phải trả về cấu trúc có thể kiểm tra trước khi lưu. Phụ đề là dữ liệu đầu vào, không phải chỉ dẫn cho hệ thống.

### Bước 4 — Biên tập theo chế độ

**Review:** xem bản tóm tắt diễn biến, chọn thời lượng mục tiêu, mức tiết lộ nội dung và phong cách kể. Hệ thống soạn lời mở đầu, phần dẫn truyện, nhận xét và kết. Mỗi đoạn lời review phải liên kết với mốc thời gian nguồn. Người dùng duyệt lời và các cảnh đề xuất trước khi tạo giọng/dựng.

**Dịch/lồng tiếng:** xem từng câu/đoạn dịch theo timeline gốc, gán người nói và giọng, kiểm tra đoạn quá dài so với khoảng thời gian có sẵn. Người dùng có thể chọn chỉ xuất phụ đề, phụ đề + video hoặc tạo bản thuyết minh/lồng tiếng.

### Bước 5 — Chọn và nghe giọng

Lọc theo Tiếng Việt/English, Nam/Nữ, vùng miền và phong cách nếu nhà cung cấp có metadata. Hiện tên giọng và nhà cung cấp rõ ràng. Lấy danh sách giọng từ provider; không hardcode số lượng giọng.

Tiếng Việt ưu tiên VieNeu. English dùng giọng bản ngữ từ provider có hỗ trợ; không đổi nhãn một giọng Việt thành giọng Anh chỉ vì model có khả năng đọc song ngữ.

Có mẫu nghe chuẩn bị trước cho từng giọng; bấm nghe dùng file đã tạo, không tổng hợp lại. Đổi giọng/ngôn ngữ dừng âm thanh cũ. Cho dùng một giọng người dẫn hoặc gán giọng riêng cho từng nhân vật. Nhân vật và giới tính giọng do người dùng xác nhận; nhận diện tự động chỉ là gợi ý ở giai đoạn sau.

### Bước 6 — Xuất và quản lý kết quả

Cho chọn 16:9 hoặc 9:16, độ phân giải, kiểu phụ đề, mức tiếng gốc và giọng đọc. Có bản xem thử ngắn trước khi xuất toàn bộ. Lưu preset của kênh: giọng dẫn, cách đọc tên riêng, font, màu phụ đề, tỷ lệ khung hình và âm lượng.

Các file tải xuống độc lập: phụ đề gốc, phụ đề dịch, kịch bản review, âm thanh thuyết minh, video review và video đã dịch/lồng tiếng. Hiển thị tiến độ, lỗi dễ hiểu, dung lượng và bước đang thực hiện.

## 3. Chế độ Review phim

### Cấu hình

- Thời lượng mục tiêu: 3, 5, 10 phút hoặc nhập riêng; thời lượng thật được tính từ âm thanh sau tổng hợp.
- Phong cách: kể chuyện, phân tích, giải trí; chọn mức hài hước và nhịp kể.
- Mức tiết lộ: không kể kết / kể một phần / kể đầy đủ.
- Người dẫn: một giọng hoặc nhiều giọng.
- Có thể thêm góc nhìn, nhận xét và thông điệp riêng của người làm kênh.

### Quy trình

Phụ đề đã duyệt → tóm tắt theo chương/nhóm cảnh → bản đồ diễn biến có timecode → kịch bản review → gắn cảnh nguồn → người dùng duyệt → tạo giọng → dựng → kiểm tra → xuất.

Phim dài được xử lý theo nhiều nhóm có checkpoint; không gửi toàn bộ phụ đề vào một prompt. Kịch bản phải viết lại có cấu trúc review và nhận xét, không mặc định đọc nguyên văn bản dịch của phim.

Mỗi đoạn review chứa: ID, nội dung lời dẫn, source ranges, giọng/model, trạng thái duyệt, audio path và thời lượng âm thanh thực. Nhiều đoạn nguồn có thể phục vụ một đoạn lời dẫn.

Khi dựng, chọn cảnh theo source ranges đã duyệt. Nếu hình ngắn hơn lời, cho người dùng chọn thêm cảnh hoặc điều chỉnh đoạn; việc lặp hoặc làm chậm cảnh cần được thể hiện trong bản xem trước. Không thay đổi tốc độ giọng quá mức để ép đúng thời lượng mục tiêu.

Phụ đề của video review được tạo theo lời review và timeline mới; không dùng nguyên timecode phim gốc cho video đã cắt ngắn.

### Đầu ra

`review.mp4`, `review.srt`, `review.vtt`, `narration.mp3`, `review-script.md`, `edit-decision-list.json`.

## 4. Chế độ Dịch/lồng tiếng toàn bộ phim

### Ba lựa chọn xuất

- **Phụ đề:** SRT/VTT/ASS hoặc video kèm phụ đề mềm/đốt phụ đề lên hình.
- **Thuyết minh:** giọng người dẫn đọc bản dịch; có thể giảm tiếng gốc phía sau.
- **Lồng tiếng theo người nói:** gán giọng từng nhân vật, tạo và căn âm thanh theo đoạn.

Phân biệt rõ thuyết minh một giọng với lồng tiếng nhiều nhân vật trong giao diện và kết quả.

### Quy trình

Lời thoại có timecode → bản dịch đã duyệt → gán người nói → tạo từng đoạn âm thanh → đo thời lượng thực → căn timeline → kiểm tra đoạn tràn/thiếu → phối âm → xuất.

Giữ timecode gốc cho phụ đề dịch. Khi bản dịch dài hơn khoảng lời thoại, ưu tiên biên tập câu ngắn gọn, chia đoạn và điều chỉnh nhịp trong giới hạn cấu hình. Chỉ mở rộng sang khoảng lặng khi người dùng cho phép và không chồng lên câu khác. Mọi đoạn chưa khớp được đưa vào danh sách cần kiểm tra.

Mỗi lần sửa một câu chỉ tạo lại câu đó và các đoạn xuất phụ thuộc. Lưu phiên bản âm thanh theo text, voice, model, ngôn ngữ và thiết lập đọc.

Giữ nguyên phim gốc; tạo file kết quả mới. Có tùy chọn tắt tiếng gốc hoặc giảm âm lượng. Giữ nhạc/hiệu ứng bằng cách tách stem là tính năng nâng cao, cần đánh giá chất lượng trên cảnh thật. Không hứa hẹn tự khớp khẩu hình trong bản đầu.

### Đầu ra

`translated.srt`, `translated.vtt`, `dubbed.mp4`, `dubbed-audio.wav`, `speaker-mapping.json`, cùng danh sách đoạn cần kiểm tra.

## 5. Màn hình và bố cục làm việc

1. **Thư viện dự án:** tìm kiếm, trạng thái xử lý, chế độ, mở lại dự án.
2. **Tạo dự án:** chọn chế độ, video, phụ đề, ngôn ngữ nguồn/đích.
3. **Studio:** video player; tab Phụ đề gốc / Bản dịch / Kịch bản review / Lồng tiếng / Xuất.
4. **Phụ đề:** hai cột gốc-dịch, sửa theo câu, nhảy video, cảnh báo timecode.
5. **Kịch bản review:** các đoạn có lời dẫn, cảnh nguồn, giọng và trạng thái duyệt.
6. **Nhân vật & giọng:** danh sách nhân vật, gán giọng, lọc Nam/Nữ, nghe mẫu sẵn.
7. **Timeline:** xem đoạn thoại, cảnh và audio; bản đầu hỗ trợ chỉnh trường thời gian trước khi làm timeline kéo thả phức tạp.
8. **Xuất:** bản xem thử, preset, file kết quả và log công việc.
9. **Cài đặt:** endpoint AI, model, thư mục dữ liệu, hàng đợi, kiểm tra kết nối.

Luôn có trạng thái đang tải, rỗng, cần thao tác, đang xử lý, đã hủy, lỗi và thành công. Nhãn nút ghi hành động cụ thể. Hỗ trợ bàn phím, focus rõ, phụ đề đọc được và bố cục laptop.

## 6. Kiến trúc đề xuất

### Công nghệ

- Frontend: React + TypeScript + Vite; giao diện web chạy cục bộ.
- Backend: FastAPI/Python, API async.
- Database: SQLite cho bản cục bộ một người dùng; media nằm trên filesystem, database chỉ lưu đường dẫn và metadata.
- Worker riêng: chạy công việc dài, có hàng đợi bền vững trong database. Không phụ thuộc việc tab trình duyệt có mở hay không.
- Media: FFmpeg/FFprobe.
- ASR: adapter cho Whisper/faster-whisper local hoặc dịch vụ tương thích.
- Dịch/kịch bản: adapter LLM cấu hình base URL, model và API key; có thể dùng Ollama hoặc dịch vụ ngoài.
- TTS: adapter VieNeu và Edge TTS/provider khác; tách việc chọn giọng khỏi model mặc định.
- Polling tiến độ cho bản đầu; SSE có thể bổ sung sau.

Cổng dự kiến: UI `3600`, API `6060`. VieNeu có thể trỏ tới dịch vụ hiện có `http://127.0.0.1:8001/v1`; đây là endpoint cấu hình, không phải phụ thuộc cứng. Kiểm tra cổng trước khi chạy. Ứng dụng có thể hoạt động mà NotebookE không chạy.

Không sao chép API key hoặc tự sửa `.env` của NotebookE. Cấu hình và khóa của hệ thống mới nằm trong `.env` riêng, được bỏ qua bởi Git; API trả metadata, không trả giá trị khóa.

### Các module

- `projects`: metadata, upload, thư viện, phiên bản.
- `media`: probe, audio tracks, embedded subtitles, clip/render/export.
- `subtitles`: parse/format, edit, timing validation.
- `translation`: batching, ngữ cảnh, glossary, kiểm tra kết quả.
- `review`: tóm tắt phân cấp, kịch bản, scene mapping.
- `dubbing`: speaker assignment, TTS, alignment, phối âm.
- `voices`: discovery, ngôn ngữ/giới tính, cache mẫu.
- `jobs`: queue, progress, checkpoint, cancel, retry/resume.
- `providers`: các adapter LLM/ASR/TTS.

### Dữ liệu chính

Project, MediaAsset, SubtitleTrack, SubtitleCue, TranslationRevision, GlossaryEntry, Speaker, VoiceProfile, ReviewScript, ReviewSegment, DubSegment, Job, JobCheckpoint, ExportArtifact, ChannelPreset.

Mọi cue/segment có ID ổn định. Mốc thời gian nội bộ dùng số nguyên millisecond; chỉ đổi sang định dạng SRT/VTT khi xuất. Phân biệt timeline nguồn và timeline video review. Lưu model/voice/language/settings thực được dùng trong snapshot công việc.

### API khởi đầu

- `POST /api/projects`: tạo dự án và upload hoặc khởi tạo upload.
- `GET /api/projects`, `GET /api/projects/{id}`: thư viện và chi tiết.
- `POST /api/projects/{id}/assets`: thêm video/phụ đề.
- `GET/PUT /api/projects/{id}/subtitles`: đọc và sửa track/cue.
- `POST /api/projects/{id}/jobs`: yêu cầu extract, transcribe, translate, review, synthesize hoặc render.
- `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel`, `POST /api/jobs/{id}/retry`.
- `GET/PUT /api/projects/{id}/review`: kịch bản và scene mapping.
- `GET/PUT /api/projects/{id}/speakers`: ánh xạ người nói/giọng.
- `GET /api/voices?language=vi&gender=female`: danh sách giọng và trạng thái mẫu nghe.
- `GET /api/voices/{id}/sample`: phát mẫu đã chuẩn bị.
- `GET /api/projects/{id}/artifacts`: danh sách kết quả tải xuống.
- `GET/PUT /api/settings`, `POST /api/providers/test`, `GET /health`.

Tên endpoint có thể điều chỉnh khi triển khai; phải giữ nguyên yêu cầu nghiệp vụ và kiểm thử.

## 7. Công việc dài và độ tin cậy

Trạng thái job: queued → running → succeeded / failed / canceled; job bị gián đoạn được phục hồi qua checkpoint và đánh dấu rõ, không treo ở running vô hạn.

- Lưu checkpoint theo nhóm dịch, đoạn TTS và clip render.
- Cancel phải dừng subprocess con; retry không tạo trùng bản xuất.
- Nếu đổi script/giọng, vô hiệu hóa đúng audio/render phụ thuộc; tái sử dụng phần không đổi.
- Đọc upload theo luồng; giới hạn dung lượng cấu hình được. Không nạp cả phim vào RAM.
- Tạo proxy video nhẹ cho biên tập; render final từ bản gốc.
- Kiểm tra dung lượng trống trước render và dọn file tạm theo chính sách rõ ràng.
- Ghi file bằng đường dẫn nội bộ UUID; chặn path traversal. Gọi FFmpeg bằng danh sách tham số, không ghép lệnh shell từ tên file người dùng.
- Lỗi provider phải nêu bước thất bại và cách thử lại; không tự đổi giọng đã chọn.
- Chuẩn hóa `vi`/`en` hoặc BCP 47 ở API, database và adapter. Các nhãn như Vietnamese/English chỉ là nhãn hiển thị.

Máy hiện được quan sát có RTX 3050 Laptop 4 GB. Mặc định dùng VieNeu ONNX/CPU và giới hạn đồng thời TTS/render, để tránh tranh tài nguyên. Chưa cam kết tốc độ xử lý phim dài; đo bằng file mẫu trước khi lựa chọn model ASR hoặc tăng độ song song.

## 8. Phạm vi triển khai theo mốc

### Mốc 1 — Nền tảng và phụ đề

Dự án độc lập, health check, cấu hình provider, upload, FFprobe, SQLite, worker, đọc SRT/VTT/ASS, trích phụ đề chữ, sửa và xuất phụ đề. Có dữ liệu mẫu và kiểm thử đường dẫn Windows có dấu/khoảng trắng.

### Mốc 2 — Dịch có kiểm soát

Dịch theo ngữ cảnh, glossary, phiên bản, timecode, kiểm tra thiếu câu, retry/resume và duyệt bản dịch. Kết nối ASR theo adapter khi không có phụ đề chữ.

### Mốc 3 — Review hoàn chỉnh

Tóm tắt phân cấp, kịch bản review chỉnh sửa được, scene mapping, giọng có mẫu nghe sẵn, tạo audio, dựng bản xem trước và xuất review MP4 + SRT.

### Mốc 4 — Dịch/lồng tiếng hoàn chỉnh

Giữ timeline phim, gán người nói thủ công, tạo/căn audio theo đoạn, kiểm tra đoạn tràn, phối âm và xuất phim có phụ đề/thuyết minh/lồng tiếng.

Bản đầu được coi hoàn thành sau cả mốc 3 và 4, để người dùng thực sự dùng được hai lựa chọn. Không gọi một màn hình có hai nút nhưng chỉ một luồng hoạt động là bản hoàn chỉnh.

### Giai đoạn nâng cao

OCR phụ đề dính, tự phân biệt người nói, tách nhạc/hiệu ứng, scene detection nâng cao, timeline kéo thả, xử lý theo lô, nhiều preset kênh, render GPU và đóng gói desktop. Lip-sync và xuất bản trực tiếp lên nền tảng là các hạng mục riêng cần đánh giá sau.

## 9. Tiêu chí nghiệm thu

1. Tải một video và SRT lên, đóng tab rồi mở lại vẫn thấy dự án và tiến độ.
2. Mốc thời gian và ký tự tiếng Việt round-trip qua parse/edit/export không hỏng; xử lý được CRLF/BOM và file ASS có thẻ định dạng.
3. Dịch không làm mất, trùng hoặc đảo ID câu. Người dùng sửa được trước khi tạo giọng.
4. Chọn vi/en chỉ hiện giọng phù hợp; có nhóm Nam/Nữ và mẫu nghe sẵn. Đổi giọng dừng âm thanh cũ; bấm nghe mẫu sẵn không gọi TTS lại.
5. Review tạo được MP4 và phụ đề theo timeline mới, có lời dẫn/nhận xét và các cảnh nguồn có thể kiểm tra.
6. Chế độ dịch/lồng tiếng xuất được phụ đề riêng và một video có audio dịch; không ghi đè video nguồn.
7. Đoạn lời dài quá khung được báo rõ; người dùng sửa và chỉ tạo lại đoạn đó.
8. Hủy và chạy tiếp một tác vụ dịch/TTS/render không làm trùng dữ liệu hoặc treo trạng thái.
9. Phim có phụ đề hình/không có phụ đề được phát hiện đúng và đưa ra lựa chọn ASR/OCR thích hợp; không báo đã trích xuất khi chưa có nội dung.
10. Có kiểm thử thực: pytest cho backend, kiểm thử frontend và Playwright cho upload → sửa → chọn chế độ → nghe giọng → xuất. Dùng video fixture ngắn do dự án tự tạo và FFmpeg thật, không chỉ mock toàn bộ pipeline.
11. Có README, `.env.example`, script khởi động Windows, hướng dẫn phụ thuộc và cách kiểm tra provider. Không lưu secret vào Git/log.
12. Hoạt động độc lập: không import package, truy cập bảng, dùng hàng đợi hoặc sửa cấu hình của NotebookE.

## 10. Tài liệu kỹ thuật tham khảo

- [FFmpeg: stream selection, chuyển mã và pipeline media](https://ffmpeg.org/ffmpeg.html).
- [FFmpeg filters: phụ đề, audio mix và xử lý hình](https://ffmpeg.org/ffmpeg-filters.html).
- [faster-whisper: nhận dạng lời thoại](https://github.com/SYSTRAN/faster-whisper).
- [VieNeu-TTS: SDK, preset voices và speech server](https://github.com/pnnbao97/VieNeu-TTS).

Đây là nguồn tham khảo cho lựa chọn công cụ. Các hành vi nghiệp vụ, mốc triển khai và kiến trúc ở trên là đề xuất thiết kế cho dự án mới, chưa phải tính năng đã xây dựng.


## 12. Phạm vi mở rộng đã chốt — Studio dịch và dựng video đa ngôn ngữ

Cập nhật 17/10/2026. Phần này ưu tiên khi mâu thuẫn với các giới hạn bản đầu ở phần trên. Đặc tả là mục tiêu phát triển, không phải danh sách tính năng đã chạy.

Trọng tâm là trình dịch video/phụ đề từ nhiều ngôn ngữ sang tiếng Việt hoặc ngôn ngữ đích khác, kèm trình biên tập video tổng quát. Review phim vẫn là chế độ lựa chọn. Không giới hạn sản phẩm ở phim hoặc cặp Việt–Anh. CapCut là tham chiếu nhóm chức năng; không sao chép thương hiệu, tài sản hoặc hứa đạt toàn bộ tính năng trong một mốc.

### Nhập video và phụ đề bằng URL

- Hỗ trợ upload, URL file trực tiếp và URL trang được adapter yt-dlp hỗ trợ. Bước phân tích link trả metadata, định dạng, dung lượng ước tính, track audio/sub, caption tự động và ngôn ngữ trước khi tải.
- Cho chọn tải video + sub, chỉ sub, chỉ audio, chất lượng, audio track và nhiều subtitle track. Ghi rõ sub tác giả hay tự động; không mặc định chất lượng tương đương.
- Tự động hóa tùy chọn: phân tích → tải → trích sub hoặc ASR khi thiếu → dịch → duyệt hoặc tiếp tục theo preset → xuất. Lưu lựa chọn xuất ngay từ đầu; mặc định yêu cầu duyệt bản dịch trước TTS/render, cho bật tự động hoàn toàn rõ ràng.
- URL sub trực tiếp nhận SRT/VTT/ASS, HTTP Content-Type và nội dung phải kiểm tra. Giữ provenance, URL đã che token, thời điểm nhập và checksum; không ghi cookie/token vào log.
- Hỗ trợ hủy, timeout, retry có giới hạn và tiếp tục tải nếu server hỗ trợ range. Dung lượng tải, thời lượng, redirect, số file và dung lượng đĩa đều có giới hạn cấu hình. Playlist phải xác nhận danh sách và giới hạn số mục.
- Adapter có capability và báo lỗi website không hỗ trợ, yêu cầu đăng nhập hoặc DRM. Chỉ tải nguồn người dùng có quyền truy cập; không triển khai vượt DRM/paywall. Không hứa tải mọi website.
- Chỉ nhận HTTP(S), chặn loopback/private/link-local và địa chỉ metadata ở mọi lần resolve/redirect. Áp dụng kiểm soát cả request từ extractor/subprocess, không chỉ URL ban đầu; nếu không đảm bảo được thì vô hiệu adapter đó cho đầu vào không tin cậy. Endpoint AI local là cấu hình riêng, không dùng chung cơ chế tải media.
- Cookie đăng nhập chỉ nhập chủ động cho nguồn cần thiết, lưu bí mật cục bộ, không tự đọc profile trình duyệt. Dọn file tạm khi thất bại/hủy; không xóa media gốc đã hoàn thành.

### Ngôn ngữ và phụ đề

- Chọn nguồn tự phát hiện hoặc thủ công, một hoặc nhiều đích trong một dự án. Mỗi đích có track, glossary, bản dịch, speaker voices và artifact riêng; không ghi đè track gốc.
- Registry chuẩn hóa BCP 47 và ánh xạ mã riêng provider; UI chỉ hiện ngôn ngữ/model/giọng có capability đã xác minh. Dịch được một ngôn ngữ không có nghĩa ASR/TTS cũng hỗ trợ ngôn ngữ đó.
- Hỗ trợ font fallback, Unicode, CJK, RTL, xuống dòng, giới hạn ký tự/tốc độ đọc, sửa dấu câu và offset/drift theo toàn track hoặc vùng. Không hứa mọi font/ASS effect được giữ nguyên khi chuyển sang SRT.
- Auto-caption theo từ, highlight từ/karaoke, song ngữ, template caption, dịch lại vùng chọn và đánh dấu confidence thấp. Căn theo từ là adapter tùy chọn, không giả timestamp nếu provider không trả.
- Xuất ngay SRT/VTT/ASS sau dịch không cần chờ dựng video. Có xuất audio, video gắn sub mềm hoặc burn-in, nhiều track nếu container hỗ trợ. MP4/MKV và codec được kiểm tra bằng capability.

### Trình dựng video tổng quát

- Timeline nhiều track video/audio/text/subtitle/overlay; trim, split, delete, ripple delete, nối/cắt, kéo sắp xếp, snap, zoom, mute/solo/lock, grouping và undo/redo.
- Preview có proxy, thumbnail, waveform, playhead, seek, chọn vùng, phím tắt, autosave và phục hồi phiên. Save/reopen không làm mất media tham chiếu; có relink và đóng gói project portable.
- Crop, rotate, flip, position, scale, opacity, tỷ lệ canvas 16:9/9:16/1:1/custom; speed và freeze frame. Speed ramp, reverse, stabilization được triển khai sau nền tảng timeline.
- Text/title, ảnh/logo/overlay, template subtitle; transition, fade, keyframe transform/opacity/volume; chỉnh sáng, tương phản, bão hòa, white balance, LUT/filter và reset.
- Audio: volume, fade, normalize, ducking khi đọc lời, nhiều track, noise reduction; EQ, stem separation và effects theo giai đoạn, nêu rõ chất lượng thực tế.
- Export theo vùng/toàn timeline, preset chất lượng/codec/FPS/resolution/bitrate, batch ngôn ngữ và hàng đợi export. Không upscale giả chất lượng; tương thích encoder phần cứng được probe trước khi cho chọn.
- Các tính năng nặng như background removal, tracking, chroma key, optical flow, motion template và plugin marketplace là roadmap riêng; chỉ đánh dấu hoàn thành khi có luồng thật và kiểm chứng.

### Hợp đồng timeline và render

Source media bất biến; thao tác biên tập lưu thành project document versioned và command history. Timeline output dùng frame/rational timebase có quy tắc rounding; cue và dữ liệu nguồn dùng millisecond, quy đổi tập trung. Clip có source in/out, timeline start, speed và liên kết audio/subtitle. Ripple/cắt/đổi tốc độ phải cập nhật phụ thuộc hoặc cảnh báo track bị khóa.

Preview và FFmpeg export dùng chung render-plan/schema và bộ kiểm thử đối chiếu; không dựng hai logic độc lập. Cache invalidation theo hash nội dung/settings/phụ thuộc. SQLite migrations có version; ghi project atomically và phục hồi autosave. Không đưa preview frame vào React state từng frame; đo scrub/drag trên proxy trước khi tối ưu.

### Mốc phát triển thay thế lộ trình cũ

1. Foundation: ứng dụng độc lập, cấu hình, DB migrations, job queue, upload/probe, subtitle editor, autosave, export SRT/VTT thực.
2. Import URL: direct URL + yt-dlp adapter, chọn track/quality, tải video/sub, progress/cancel/retry và kiểm thử bảo vệ URL.
3. Translation: nhiều đích, provider registry, ASR fallback, glossary, batch/checkpoint, xuất sub và preset pipeline tự động.
4. Editing core: nhiều track, trim/split/move/ripple, proxy/waveform, undo/redo, preview và FFmpeg render đồng nhất.
5. Dubbing + review: hai chế độ hoạt động từ đầu đến cuối, voice samples có sẵn, alignment và artifact tách ngôn ngữ.
6. Editing polish: text/overlay/transition/keyframe/color/audio, preset, portable project, batch export và tài liệu vận hành.
7. Advanced AI/editor: OCR, diarization, stems, speed ramp, stabilization, tracking/background removal theo đo đạc và giá trị sử dụng.

Mỗi mốc cần demo chạy thật, test phù hợp và báo phần chưa hỗ trợ. Không gọi skeleton hoặc mock adapter là sản phẩm hoàn thiện.

### Tiêu chí bổ sung

- Import cùng nguồn từ upload/link cho ra metadata/track tương đương; sub-only không tải video thừa. Thiếu sub thực sự kích hoạt ASR khi người dùng bật và provider sẵn sàng.
- Một nguồn xuất được ít nhất hai ngôn ngữ trong fixture kiểm thử; giữ ID/timing/Unicode; không tự thay ngôn ngữ hoặc giọng khi thiếu provider.
- Pipeline từ URL đến sub dịch có thể tự hoàn tất theo preset; xuất sub độc lập với render. Lỗi một đích không phá kết quả đích khác.
- Timeline lưu/mở lại và undo/redo; split/ripple/speed giữ audio/sub đúng mapping. Kiểm tra audio/video/sub đồng bộ đầu/giữa/cuối bằng fixture đã biết.
- Dùng local HTTP fixture để test redirect, size cap, private IP, malformed subtitle, mất mạng và resume; không để CI phụ thuộc video công khai có thể biến mất.
- QA trên Windows gồm tên file tiếng Việt, đường dẫn có khoảng trắng, phim dài, hết đĩa, worker restart, cancel subprocess và thiếu FFmpeg/provider. Benchmark ghi môi trường thật, không bịa FPS/thời gian render.

Nguồn kỹ thuật: https://github.com/yt-dlp/yt-dlp ; https://ffmpeg.org/ffmpeg.html ; https://ffmpeg.org/ffmpeg-filters.html
