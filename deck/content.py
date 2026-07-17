# -*- coding: utf-8 -*-
"""All slide content for the SHB CreditOps EvidenceGraph pitch deck.

Pure data. Copy is final Vietnamese on-slide text per the design spec
(docs/superpowers/specs/2026-07-17-shb-pitch-deck-design.md).
Bracketed [..] strings are deliberate input slots (spec section 6) and must
survive until real data replaces them; deck/check_final.py gates on them.
"""

DISCLAIMER_SLIDES = {1, 4, 5, 6, 8, 13}

LAYOUTS = {
    "hook", "standard", "curve", "product", "before_after", "storyboard",
    "pipeline", "provenance", "grounding", "architecture", "compare_table",
    "criteria", "validation", "axes", "roadmap", "team", "closing",
}

SLIDES = [
    {
        "n": 1,
        "layout": "hook",
        "title": "Một câu hỏi đơn giản. Hàng chục tài liệu. Năm bàn làm việc.",
        "extra": {
            "quote": '"Tôi cần 2 tỷ nhập nguyên liệu cho đơn hàng Tết — "ngân hàng cần gì để cho tôi vay?"',
            "quote_by": "Giám đốc Công ty TNHH Thực phẩm Minh An (dữ liệu tổng hợp)",
            "doc_labels": ("ĐKKD", "Điều lệ", "CCCD người ĐDPL", "BCTC 2024",
                           "BCTC 2025", "Sao kê ngân hàng", "Tờ khai VAT",
                           "HĐ mua nguyên liệu", "HĐ bán hàng", "Kế hoạch tồn kho",
                           "Hồ sơ TSBĐ", "Nghị quyết bổ nhiệm"),
        },
        "disclaimer": True,
        "notes": "Mở đầu: SME tín dụng chậm không phải ở quyết định, mà ở khâu chuẩn bị.",
    },
    {
        "n": 2,
        "layout": "standard",
        "title": "Ngân hàng không thiếu dữ liệu. Ngân hàng thiếu bộ máy kiểm chứng dữ liệu.",
        "bullets": [
            "Tài liệu —có. Chính sách —có. Chuyên gia —có.",
            "Kiểm tra đầy đủ hồ sơ: làm thủ công",
            "Mâu thuẫn doanh thu ↔ sao kê: phát hiện muộn",
            "Trích dẫn chính sách: tra cứu bằng tay",
            "Tờ trình: lắp ghép copy-paste",
            "Dấu vết kiểm toán: dựng lại sau cùng",
        ],
        "killer": "Khoảng trống không nằm ở thông tin —mà ở việc kiểm chứng "
                  "và kết nối thông tin.",
        "disclaimer": False,
    },
    {
        "n": 3,
        "layout": "curve",
        "title": "AI ngân hàng đang dừng ở trả lời câu hỏi. Nghiệp vụ cần AI làm việc.",
        "extra": {
            "stages": ("Chatbot Q&A", "RAG trả lời có nguồn", "Đội ngũ agent làm việc thật"),
            "gap": "KHOẢNG CÁCH TIN CẬY",
        },
        "bullets": [
            "Chuyên môn tín dụng nằm trong số ít chuyên gia khó nhân rộng",
            "Xu hướng 2026: AI lập kế hoạch, phối hợp, dùng công cụ, hành động",
            "Nhưng tín dụng không thể tin AI thiếu bằng chứng, kiểm toán và phân quyền",
        ],
        "killer": "Đúng lúc ngân hàng cần AI làm việc thật, chatbot chỉ có thể nói.",
        "disclaimer": False,
    },
    {
        "n": 4,
        "layout": "product",
        "title": "SHB CreditOps EvidenceGraph —Phòng tín dụng số đầu tiên cho SHB",
        "extra": {
            "pitch": "Một đội ngũ chuyên gia AI biến chồng tài liệu rời rạc thành hồ sơ "
                     "tín dụng có bằng chứng —để con người ra quyết định.",
            "hub": "Credit Case Digital Twin\n(hồ sơ số có phiên bản)",
            "roles": ("Điều phối hồ sơ (Case Orchestrator)",
                      "Tiếp nhận nhu cầu (Intake)",
                      "Thẩm định tín dụng (Underwriting)",
                      "Pháp lý – Tuân thủ – TSBĐ",
                      "Kiểm soát rủi ro độc lập",
                      "Vận hành tín dụng"),
            "promises": ("Một đội ngũ —không phải một chatbot",
                         "Mọi kết luận đều có bằng chứng",
                         "Con người quyết định"),
            "screenshot": "[ẢNH MÀN HÌNH DASHBOARD —chèn khi demo sẵn sàng]",
        },
        "disclaimer": True,
    },
    {
        "n": 5,
        "layout": "before_after",
        "title": "Từ xử lý thủ công sang hồ sơ được chuẩn bị sẵn",
        "extra": {
            "before": ("Tài liệu đến qua email / Zalo",
                       "Cán bộ phân loại, gõ lại số liệu",
                       "Thiếu giấy tờ: phát hiện sau nhiều tuần",
                       "Khách hàng bị hỏi đi hỏi lại",
                       "Thẩm định đọc lại toàn bộ hồ sơ",
                       "Tờ trình lắp ghép copy-paste"),
            "before_bar": "NHIỀU TUẦN",
            "after": ("Tải lên một lần —agent phân loại, trích xuất kèm độ tin cậy",
                      "Cán bộ xác nhận từng tài liệu",
                      "Thiếu sót & mâu thuẫn hiện ngay, kèm đề xuất bổ sung (người duyệt)",
                      "Thẩm định + Pháp lý chạy song song trên cùng hồ sơ",
                      "Phản biện độc lập maker–checker",
                      "Tờ trình kèm trích dẫn bấm-để-xem"),
            "after_bar": "VÀI NGÀY",
        },
        "killer": "Trước: con người phục vụ hồ sơ. Sau: hồ sơ được chuẩn bị "
                  "để con người quyết định.",
        "disclaimer": True,
    },
    {
        "n": 6,
        "layout": "storyboard",
        "title": "Một hồ sơ hoàn chỉnh, trong một cuộc trình diễn",
        "extra": {
            "steps": (
                "Tạo hồ sơ, tải ~20 tài liệu của Minh An",
                "Agent phân loại & trích xuất —cán bộ xác nhận từng tài liệu",
                "Bắt mâu thuẫn: doanh thu BCTC ≠ sao kê → khoảng trống BLOCKING "
                "→ người duyệt yêu cầu bổ sung",
                "Thẩm định + Pháp lý song song; công cụ tính toán xác định",
                "Kiểm soát rủi ro chất vấn: nguồn trả nợ tập trung một người mua "
                "— maker phản hồi, đối thoại được lưu vết",
                "Tờ trình dự thảo —mỗi con số bấm về nguồn; gate chờ con người quyết định",
            ),
            "screenshot": "[ẢNH MÀN HÌNH TỪNG BƯỚC —chèn khi demo sẵn sàng]",
        },
        "disclaimer": True,
        "notes": "Slide này là preview 60 giây; demo trực tiếp chạy đúng hồ sơ này.",
    },
    {
        "n": 7,
        "layout": "pipeline",
        "title": "Hệ thống không trò chuyện về hồ sơ. Hệ thống xử lý hồ sơ.",
        "extra": {
            "steps": ("1. Tiếp nhận nhu cầu", "2. Số hoá & phân loại",
                      "3. Trích xuất dữ kiện", "4. Cán bộ xác nhận",
                      "5. Khoảng trống & xung đột", "6. Phân tích song song",
                      "7. Phản biện độc lập", "8. Tờ trình & gate phê duyệt"),
        },
        "killer": "Chat không phải là hồ sơ. Hồ sơ là Credit Case Digital Twin —"
                  "có phiên bản, có bằng chứng, có kiểm toán.",
        "disclaimer": False,
    },
    {
        "n": 8,
        "layout": "provenance",
        "title": "Mọi kết luận đều được truy vết —không phỏng đoán.",
        "extra": {
            "chain": ("Phiên bản tài liệu", "Trang / vùng", "Dữ kiện trích xuất",
                      "Tính toán xác định / trích dẫn chính sách", "Nhận định (finding)",
                      "Phản biện độc lập", "Phê duyệt của con người"),
            "gap_panel": ("Vấn đề & bằng chứng hiện có", "Thông tin còn thiếu",
                          "Tài liệu đề xuất + lý do", "Cơ sở chính sách",
                          "Mức độ: BLOCKING / CONDITIONAL / CLARIFICATION",
                          "Tác vụ bị ảnh hưởng", "Trạng thái phê duyệt"),
            "screenshot": "[VÍ DỤ MINH AN: con số vốn lưu động truy về nguồn —"
                          "chèn khi demo sẵn sàng]",
        },
        "disclaimer": True,
    },
    {
        "n": 9,
        "layout": "grounding",
        "title": "Không có con số bịa. Không có chính sách tưởng tượng. "
                 "Không có kết luận thiếu nguồn.",
        "extra": {
            "sources": ("Tài liệu gốc (bất biến, có phiên bản)",
                        "Dữ kiện đã được cán bộ xác nhận",
                        "Công cụ tính toán xác định",
                        "Kho chính sách có phiên bản + trích dẫn chính xác",
                        "Tra cứu KYC/AML mô phỏng, có kiểm soát",
                        "Nhật ký kiểm toán chỉ-ghi-thêm"),
            "layer": "LỚP BẰNG CHỨNG",
            "out": "Phản hồi của agent —kèm nguồn",
            "abstain": "Thiếu nguồn → từ chối trả lời → chuyển kiểm tra thủ công",
        },
        "bullets": [
            "Fail-closed: không có nguồn thì không kết luận",
            "Tài liệu tải lên là dữ liệu, không phải mệnh lệnh —"
            "chống chỉ thị ẩn (prompt injection)",
        ],
        "disclaimer": False,
    },
    {
        "n": 10,
        "layout": "architecture",
        "title": "Kiến trúc cho độ chính xác, chủ quyền dữ liệu và khả năng mở rộng",
        "extra": {
            "bands": (
                "Vercel —giao diện tiếng Việt (Next.js)",
                "Cloud Run —FastAPI + creditops-worker · máy trạng thái xác định · "
                "cổng mô hình trung lập",
                "Supabase —Postgres (Digital Twin + EvidenceGraph) · Queues · "
                "Storage riêng tư · pgvector",
                "FPT AI Factory —suy luận có quản lý (ứng viên: Qwen3-30B-A3B, "
                "SaoLa3.1-medium, FPT.AI-KIE v1.7, Table-Parsing v1.1, "
                "Qwen2.5-VL, e5-large / Vietnamese_Embedding)",
            ),
            "trust": ("Frontend không bao giờ gọi mô hình",
                      "Mô hình không bao giờ sở hữu trạng thái hồ sơ",
                      "Mọi đầu ra qua kiểm tra schema trước khi chạm vào hồ sơ"),
            "note": "Tên mô hình là ứng viên —chốt sau benchmark tiếng Việt.",
        },
        "killer": "Mô hình có thể thay. Kiến trúc ra quyết định thì không.",
        "disclaimer": False,
    },
    {
        "n": 11,
        "layout": "compare_table",
        "title": "Chatbot tìm câu trả lời. Chúng tôi chuẩn bị quyết định.",
        "extra": {
            "cols": ("Năng lực", "Quy trình thủ công", "Chatbot RAG đơn",
                     "Multi-agent demo thông thường", "SHB CreditOps EvidenceGraph"),
            "rows": (
                ("Đọc & trích xuất tài liệu tiếng Việt (KIE, bảng biểu)",
                 "Thủ công", "—", "Một phần", "✓"),
                ("Phát hiện thiếu sót & mâu thuẫn giữa tài liệu",
                 "Muộn", "—", "Không ổn định", "✓"),
                ("Truy vết bằng chứng cho từng kết luận",
                 "Rời rạc", "Nguồn chung chung", "Hiếm", "✓"),
                ("Phân tách maker–checker (thẩm định ≠ phản biện)",
                 "✓ (chậm)", "—", "—", "✓"),
                ("Gate phê duyệt của con người trong workflow",
                 "✓", "—", "Hiếm", "✓"),
                ("Dashboard truy vết agent & kiểm toán",
                 "—", "—", "Một phần", "✓"),
                ("Chống chỉ thị ẩn trong tài liệu (prompt injection)",
                 "N/A", "Yếu", "Yếu", "Thiết kế sẵn"),
            ),
        },
        "disclaimer": False,
    },
    {
        "n": 12,
        "layout": "criteria",
        "title": "Đề bài yêu cầu —chúng tôi xây đúng, rồi đi xa hơn một tầng tin cậy.",
        "extra": {
            "rows": (
                ("≥2–3 chuyên gia số (Credit, Legal/Compliance, Operations)",
                 "6 vai trò chuyên trách —bao gồm đúng 3 vai trò đề bài nêu"),
                ("Điều phối planner–executor",
                 "Case Orchestrator phân rã & định tuyến; executor có giới hạn"),
                ("Dùng công cụ thật (API, dữ liệu, hành động)",
                 "KIE / trích xuất bảng, máy tính xác định, tra cứu mô phỏng, tạo tờ trình"),
                ("RAG chuyên ngành cho từng agent",
                 "RAG bằng chứng hồ sơ + RAG chính sách kèm trích dẫn chính xác"),
                ("Dashboard truy vết agent, trạng thái, quyết định",
                 "Giao diện truy vết / kiểm toán của sản phẩm"),
                ("So sánh với chatbot đơn agent",
                 "Đo lường đối đầu —xem slide Kiểm chứng"),
            ),
            "benefits": ("GenAI: từ trả lời → làm việc",
                         "Một hệ thống đại diện nhiều phòng ban",
                         "Giảm phụ thuộc chuyên gia cá nhân —vẫn giữ kiểm soát",
                         "Nền tảng tự động hoá quy trình đầu-cuối"),
        },
        "disclaimer": False,
    },
    {
        "n": 13,
        "layout": "validation",
        "title": "Chúng tôi không chỉ demo. Chúng tôi đo.",
        "bullets": [
            "[N] hồ sơ SME tổng hợp —6 kịch bản: đủ / thiếu tài liệu / mâu thuẫn "
            "/ ngoại lệ chính sách / scan kém / cần xử lý tay",
            "Ground-truth gắn nhãn trước; đối đầu chatbot RAG đơn dùng CÙNG mô hình nền",
        ],
        "extra": {
            "metrics": (
                ("Độ phủ trích dẫn (kết luận có nguồn đúng)", "[X%]", "so với chatbot [Y%]"),
                ("Phát hiện khoảng trống (recall / precision)", "[X%]", ""),
                ("Tính toán qua công cụ xác định", "mục tiêu 100%", ""),
                ("Tỷ lệ khẳng định thiếu nguồn", "[X%]", "so với chatbot [Y%]"),
                ("Tuân thủ gate phê duyệt của con người", "0 lần vượt", "trên mọi lần chạy"),
                ("Thời gian chuẩn bị hồ sơ đầu-cuối", "[X giờ] → [Y phút]", "so với thủ công"),
            ),
        },
        "killer": "Câu hỏi không phải là demo có đẹp không —mà là hệ thống có đáng tin "
                  "để đứng cạnh một quyết định tín dụng không.",
        "disclaimer": True,
    },
    {
        "n": 14,
        "layout": "axes",
        "title": "Nghiệp vụ mới —cùng một bộ máy bằng chứng.",
        "bullets": [
            "Không gì trong bộ máy bị đóng cứng vào vốn lưu động: mở rộng = thêm "
            "schema tài liệu, kho chính sách, chỉ dẫn vai trò, công cụ —"
            "không phải kiến trúc mới",
            "Cổng mô hình trung lập: nâng cấp mô hình không phải xây lại ứng dụng",
        ],
        "extra": {
            "axes": (
                ("Sâu hơn trong vòng đời (kế hoạch)",
                 "Giai đoạn 7–14: thông báo, hợp đồng, TSBĐ, điều kiện giải ngân, "
                 "agent giám sát & thu hồi"),
                ("Nhiều sản phẩm tín dụng hơn (kế hoạch)",
                 "Vay trung dài hạn, bảo lãnh, tài trợ thương mại / LC, bán lẻ"),
                ("Nghiệp vụ ngân hàng khác (kế hoạch)",
                 "Rà soát KYC, chuẩn bị kiểm toán nội bộ, xử lý khiếu nại —"
                 "cùng mẫu hình: digital twin + chuyên gia giới hạn + gate con người"),
            ),
        },
        "disclaimer": False,
    },
    {
        "n": 15,
        "layout": "standard",
        "title": "Hồ sơ tốt hơn → quyết định nhanh hơn → vốn đến doanh nghiệp sớm hơn.",
        "bullets": [
            "Thời gian ra quyết định SME: từ nhiều tuần hướng tới vài ngày",
            "Ít vòng bổ sung tài liệu —thiếu sót bắt ngay từ tiếp nhận, "
            "một yêu cầu gộp duy nhất",
            "Chính sách áp dụng nhất quán giữa các chi nhánh",
            "Giảm phụ thuộc chuyên gia thâm niên khan hiếm",
            "Dấu vết kiểm toán sinh ra trong lúc làm việc —không phải dựng lại sau",
            "Chỉ tiêu (điền số đo thực): giảm [X%] thời gian chuẩn bị hồ sơ · "
            "giảm [X] vòng bổ sung · tăng [X%] công suất mỗi cán bộ",
        ],
        "killer": "Tín dụng SME là ưu tiên tăng trưởng —nút thắt là năng lực chuẩn bị "
                  "hồ sơ, và hệ thống này chính là năng lực đó.",
        "disclaimer": False,
    },
    {
        "n": 16,
        "layout": "roadmap",
        "title": "Từ nguyên mẫu hackathon đến trợ thủ tín dụng triển khai được",
        "extra": {
            "milestones": (
                ("Hackathon", "Demo hoạt động: intake + agent phối hợp + dashboard, "
                              "dữ liệu tổng hợp, trên đúng kiến trúc đích"),
                ("+1 tháng", "Benchmark tiếng Việt, chốt endpoint mô hình; "
                             "phủ đủ 6 vai trò"),
                ("+3 tháng", "Pilot shadow-mode với một đội tín dụng SHB "
                             "(cần phê duyệt dữ liệu & quản trị)"),
                ("+6 tháng", "Biên tích hợp LOS/ACAS có kiểm soát; "
                             "mở rộng chuẩn bị sau phê duyệt"),
                ("Tương lai", "Agent giám sát, tiếp nhận đa kênh, tài liệu đa phương thức"),
            ),
            "note": "Các giai đoạn sau hackathon thực hiện theo quản trị, "
                    "chấp thuận an ninh và cư trú dữ liệu của SHB.",
        },
        "disclaimer": False,
    },
    {
        "n": 17,
        "layout": "team",
        "title": "Đội ngũ xây AI đáng tin cho ngân hàng",
        "extra": {
            "members": (
                ("[Họ tên]", "Kỹ sư AI / LLM", "[Đóng góp trong demo]", "[Thế mạnh]"),
                ("[Họ tên]", "Kỹ sư backend / dữ liệu", "[Đóng góp trong demo]", "[Thế mạnh]"),
                ("[Họ tên]", "Sản phẩm & thiết kế", "[Đóng góp trong demo]", "[Thế mạnh]"),
                ("[Họ tên]", "Chuyên môn nghiệp vụ ngân hàng", "[Đóng góp trong demo]", "[Thế mạnh]"),
                ("[Họ tên]", "Trưởng nhóm đánh giá / kiểm chứng", "[Đóng góp trong demo]", "[Thế mạnh]"),
            ),
        },
        "killer": "Chúng tôi kết hợp kỹ thuật AI, tư duy sản phẩm và hiểu biết "
                  "nghiệp vụ tín dụng.",
        "disclaimer": False,
    },
    {
        "n": 18,
        "layout": "closing",
        "title": "Biến chồng tài liệu rời rạc thành quyết định tín dụng có bằng chứng.",
        "extra": {
            "ctas": ("Quét QR —demo trực tiếp hồ sơ Minh An",
                     "Đưa hệ thống một hồ sơ tổng hợp mới ngay tại chỗ",
                     "Đồng hành pilot cùng một đội tín dụng SHB"),
            "qr": "[QR DEMO —chèn liên kết khi demo sẵn sàng]",
        },
        "killer": "Không phải thêm một chatbot —mà là một đội ngũ chuyên gia số "
                  "có thể kiểm chứng, cho nghiệp vụ cốt lõi nhất của ngân hàng.",
        "disclaimer": False,
    },
]
