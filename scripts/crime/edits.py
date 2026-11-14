#!/usr/bin/env python3
"""The catalogue of scene edits ("bảng cách edit") of this channel, and the mechanism that applies one to a scene.

Every entry is one scene layout of the owner's sample 00-video-mau/MAU-HO-SO.mp4 (the time in "sample" is where it
can be seen there), built from this repo's own board items (scripts/crime/layout.py: named places and pins). In
picks.json a scene names its edit — {"at": 5, "edit": "who", "why": "câu 5–6 giới thiệu bốn nạn nhân", "items": […]}
— and lists only the content: which picture, which words, on which spoken word each appears. apply() then gives
every item the template's place (pos / pin / colour / size) unless Claude wrote one himself, and refuses a scene
that lacks the items the template is made of, with the recipe to copy. "why" is a short Vietnamese reason for the
owner; it is never drawn. A scene without "edit" is built exactly as before.

An entry: vi (Vietnamese name), sample (m:ss in the sample), look, use (WHEN: by the meaning of the scene's lines),
needs / most ({"photo" | "pic" (photo or sticker) | "card:lined" …: count}), check (a function → error text),
scene (defaults of the scene itself), slots (defaults of the n-th item of a kind: a list, or for tapes a dict by
colour with "*" for the others; ["pic", 1] = the item index of the scene's 2nd picture), all (defaults of every
item of a kind), recipe (the JSON Claude copies; AGENT_CRIME.md §2.4 prints the same table: python3
scripts/crime/edits.py).
"""
import copy, json, re

KINDS = ('photo', 'sticker', 'tape', 'card', 'stat', 'string')
PICS = ('photo', 'sticker')            # "pic": either of them
COLOR0 = 'yellow'                      # colour of a tape that names none
CYCLE = True                           # more tapes than places: start again at the first place (pins stack downwards)
PLACE = ()                             # (strict catalogues only) what an item beyond the template's places must carry
GROUPS = {'tape': {'pin': ('pin', 'on'), 'xy': ('pin', 'on')}, 'photo': {'pos': ('pos', 'w')}, 'sticker': {'pos': ('pos', 'w')},
          'card': {'pos': ('pos', 'h')}}
LABEL = {'photo': 'ảnh (photo)', 'sticker': 'hình cắt rời (sticker)', 'pic': 'ảnh hoặc hình cắt rời (photo / sticker)',
         'tape': 'băng giấy (tape)', 'card': 'thẻ (card)', 'stat': 'số lớn (stat)', 'string': 'dây đỏ (string)'}
finish = None


def style_of(it):
    return it.get('card') if 'card' in it else None


def _head_only(sc):
    if not isinstance(sc.get('head'), (dict, list)) or not sc.get('head'): return 'cảnh phải có "head": {"kicker": …, "title": …}'
    if sc.get('items'): return 'cảnh chỉ có tiêu đề chương, không có "items" (các món đặt ở cảnh sau)'


def _ring(sc):
    if not any(('ring' in it or 'rings' in it or 'zoom' in it) for it in sc.get('items') or [] if 'photo' in it):
        return 'ảnh phải có "ring" (khoanh chi tiết) hoặc "zoom" (phóng vào chi tiết)'


def _stamp(sc):
    if not any(it.get('stamp') for it in sc.get('items') or [] if 'card' in it): return 'thẻ phải có "stamp" (dấu đỏ kết luận)'


G6 = [{'pos': p} for p in ('g1', 'g2', 'g3', 'g4', 'g5', 'g6')]
EDITS = {
 'hook': {
  'vi': 'mở đầu', 'sample': '0:00–0:11',
  'look': 'một ảnh đứng lớn (ảnh ngang được cắt thành khung đứng 4:5 — đặt `view` vào chủ thể, hoặc tự ghi `aspect`); băng giấy dán dần xuống hai góc dưới, mỗi thứ giọng đọc kể một băng; băng trắng con số ở mép trên',
  'use': 'MỞ ĐẦU: 2–3 câu đầu kể điều lạ của vụ án, liệt kê những thứ để lại, rồi con số gây tò mò',
  'needs': {'photo': 1, 'tape': 2},
  'slots': {'photo': [{'pos': 'main', 'aspect': '4:5'}], 'tape': {'white': [{'pin': 'top'}], '*': [{'pin': 'bl'}, {'pin': 'br'}]}},
  'recipe': {'at': 1, 'edit': 'hook', 'why': '…', 'items': [
      {'photo': 'house'}, {'tape': 'Blut', 'color': 'red', 'at': '2/Blut'}, {'tape': 'DNA', 'at': '2/DNA'},
      {'tape': 'Schuhspuren', 'at': '2/Schuh'}, {'tape': '25+ JAHRE', 'color': 'white', 'at': '3/25'}]}},
 'chapter': {
  'vi': 'tiêu đề chương', 'sample': '0:12, 3:18',
  'look': 'tiêu đề chương một mình giữa bảng (dải đen + tên trên giấy rách), cảnh sau nó chạy lên trên cùng',
  'use': 'CHUYỂN PHẦN: câu gọi tên vụ án, hoặc mở một phần mới (phân tích năm 2025, phiên tòa…)',
  'check': _head_only,
  'recipe': {'at': 4, 'edit': 'chapter', 'why': '…', 'head': {'kicker': 'AKTE 2000', 'title': 'Familie Miyazawa'}}},
 'where': {
  'vi': 'bìa hồ sơ nơi xảy ra', 'sample': '0:14–0:17',
  'look': 'bìa hồ sơ màu be kẹp một ảnh; băng vàng tên nơi chốn ở góc ảnh, băng đỏ tình trạng ở dưới',
  'use': 'NƠI CHỐN: câu nói vụ án xảy ra ở đâu (thành phố, khu, ngôi nhà) và tình trạng của nó (chưa có lời giải)',
  'needs': {'card:folder': 1, 'photo': 1},
  'slots': {'card': [{'pos': 'main'}], 'photo': [{'pos': 'in'}], 'tape': {'red': [{'pin': 'below-l'}], '*': [{'pin': 'tr'}, {'pin': 'bl'}]}},
  'recipe': {'at': 5, 'edit': 'where', 'why': '…', 'items': [
      {'card': 'folder', 'tab': 'AKTE · SETAGAYA', 'corner': 'TOKIO'}, {'photo': 'house', 'at': 5.05},
      {'tape': 'Setagaya, Tokio', 'at': '5/Tokio'}, {'tape': 'ungelöst', 'color': 'red', 'at': '5/ungelöst'}]}},
 'who': {
  'vi': 'tờ giấy tên và tuổi', 'sample': '0:18–0:31',
  'look': 'tờ giấy kem: dòng đầu gõ ngày giờ, rồi từng dòng tên + tuổi gõ ra khi được đọc; mẩu giấy viết tay ở cuối',
  'use': 'NGƯỜI / NGÀY THÁNG: câu giới thiệu nạn nhân, những người liên quan, tên, tuổi, ngày xảy ra',
  'needs': {'card:paper': 1}, 'most': {'pic': 0},
  'slots': {'card': [{'pos': 'main'}], 'tape': {'*': [{'pin': 'bottom'}]}},
  'recipe': {'at': 6, 'edit': 'who', 'why': '…', 'items': [
      {'card': 'paper', 'head': 'NACHT 30./31.12.2000', 'rows': [['Mikio M.', '44 J.', '6/Mikio'], ['Yasuko', '41 J.', '6/Yasuko']],
       'note': {'text': 'im eigenen Haus getötet', 'at': '7/Haus'}}]}},
 'place': {
  'vi': 'ảnh hiện trường + giờ', 'sample': '0:32–0:35',
  'look': 'một ảnh ngang ở nửa trên; băng trắng gõ giờ hoặc ngày ngay dưới ảnh',
  'use': 'THỜI ĐIỂM / HIỆN TRƯỜNG: câu nói việc xảy ra lúc mấy giờ, ngày nào, ở chỗ nào của hiện trường',
  'needs': {'photo': 1, 'tape': 1},
  'slots': {'photo': [{'pos': 'top'}], 'tape': {'white': [{'pin': 'below-l', 'rot': -1}], 'red': [{'pin': 'below-l', 'rot': -1}], '*': [{'pin': 'tl'}, {'pin': 'tr'}]}},
  'recipe': {'at': 8, 'edit': 'place', 'why': '…', 'items': [
      {'photo': 'street'}, {'tape': 'ca. 23:00 UHR', 'color': 'white', 'at': '8/23'}]}},
 'figure': {
  'vi': 'bóng người', 'sample': '0:36–0:43, 2:02–2:07',
  'look': 'một ảnh đứng ở giữa (bóng người, hành lang); băng trắng gõ chữ phía trên ảnh, băng vàng ở góc dưới, băng đỏ bên dưới ảnh',
  'use': 'CON NGƯỜI BÍ ẨN: câu nói về hung thủ chưa rõ mặt, nghi phạm, một nhận định về hắn (tàn bạo, bình tĩnh)',
  'needs': {'photo': 1, 'tape': 1}, 'most': {'photo': 1},
  'slots': {'photo': [{'pos': 'center'}], 'sticker': [{'pos': [250, 1250, 360]}],
            'tape': {'white': [{'pin': 'above', 'on': ['pic', 0]}], 'red': [{'pin': 'below', 'on': ['pic', 0]}],
                     '*': [{'pin': 'br', 'on': ['pic', 0]}, {'pin': 'bl', 'on': ['pic', 0]}]}},
  'recipe': {'at': 9, 'edit': 'figure', 'why': '…', 'items': [
      {'photo': 'hall', 'view': [0.2, 0, 0.8, 1]}, {'tape': 'VERDÄCHTIGER?', 'color': 'white', 'at': '9/Verdacht'},
      {'tape': 'brutal', 'at': '9/brutal'}, {'tape': 'kein Name', 'color': 'red', 'at': '10/Namen'}]}},
 'fact': {
  'vi': 'bằng chứng + vật chứng', 'sample': '0:44–0:51',
  'look': 'ảnh ở nửa trên với băng vàng ở góc và băng đỏ; món thứ hai (ảnh nhỏ hoặc hình cắt rời) hiện ở nửa dưới khi được nhắc',
  'use': 'MỘT SỰ VIỆC CÓ BẰNG CHỨNG: câu nói điều gì đã xảy ra và cảnh sát tìm được gì (bị thương → máu → nhóm máu → DNA)',
  'needs': {'pic': 2, 'tape': 1},
  'slots': {'pic': [{'pos': 'top'}, {'pos': 'bottom', 'w': 560}],
            'tape': {'red': [{'pin': 'below-r', 'on': ['pic', 0]}], 'white': [{'pin': 'br'}], '*': [{'pin': 'tl', 'on': ['pic', 0]}, {'pin': 'tr'}]}},
  'recipe': {'at': 10, 'edit': 'fact', 'why': '…', 'items': [
      {'photo': 'lab'}, {'tape': 'an der Hand verletzt', 'at': '10/Hand'}, {'tape': 'Blutgruppe A', 'color': 'red', 'at': '10/Blutgruppe'},
      {'sticker': 'dna', 'at': '10/DNA'}, {'tape': 'DNA gesichert', 'color': 'white', 'at': '10/gesichert'}]}},
 'pair': {
  'vi': 'hai ảnh chồng nhau', 'sample': '0:52–0:57',
  'look': 'hai ảnh chồng chéo (trái trên, phải dưới), ảnh thứ hai rơi xuống khi được nhắc; mỗi ảnh một băng giấy',
  'use': 'HAI THỨ ĐI CÙNG NHAU: câu nêu hai dấu vết, hai người, hai nơi (vân tay và dấu giày) rồi rút ra một kết luận',
  'needs': {'pic': 2, 'tape': 1},
  'slots': {'pic': [{'pos': 'left'}, {'pos': 'right'}],
            'tape': {'white': [{'pin': 'above', 'on': ['pic', 1]}], 'red': [{'pin': 'below', 'on': ['pic', 1]}],
                     '*': [{'pin': 'tl', 'on': ['pic', 0]}, {'pin': 'br', 'on': ['pic', 1]}]}},
  'recipe': {'at': 11, 'edit': 'pair', 'why': '…', 'items': [
      {'photo': 'finger'}, {'photo': 'sole', 'at': '11/Schuhspur'}, {'tape': 'fremde Abdrücke', 'at': 11.1},
      {'tape': '1 SCHUHSPUR', 'color': 'white', 'at': '11/Schuhspur'}, {'tape': 'nur ein Täter', 'color': 'red', 'at': '11/Täter'}]}},
 'list': {
  'vi': 'ảnh + danh sách băng giấy', 'sample': '1:02–1:11',
  'look': 'một ảnh ở nửa trên; bên dưới là hai cột băng vàng, mỗi món được đọc hiện một băng; băng trắng số đo ở mép trên ảnh',
  'use': 'LIỆT KÊ: câu đọc một dãy đồ vật hoặc chi tiết (áo, mũ, khăn, túi, giày…), từ 3 món trở lên',
  'needs': {'pic': 1, 'tape': 3}, 'most': {'pic': 1},
  'slots': {'pic': [{'pos': 'top'}], 'tape': {'white': [{'pin': 'top'}], '*': [{'pin': 'below-l'}, {'pin': 'below-r'}]}},
  'recipe': {'at': 12, 'edit': 'list', 'why': '…', 'items': [
      {'photo': 'clothes'}, {'tape': 'Sweatshirt', 'at': '12/Sweat'}, {'tape': 'Mütze', 'at': '12/Mütze'}, {'tape': 'Schal', 'at': '12/Schal'},
      {'tape': 'Gürteltasche', 'at': '12/Gürtel'}, {'tape': 'GRÖSSE 27,5', 'color': 'white', 'at': '13/Größe'}]}},
 'number': {
  'vi': 'số lớn', 'sample': '1:12–1:23',
  'look': 'một ảnh nhỏ ở góc trên; các con số lớn kiểu máy đánh chữ hiện lần lượt bên dưới, mỗi số một dòng chú thích',
  'use': 'CON SỐ: câu có số đếm, số lượng, tỉ lệ (130 chiếc, 12 người mua, 3 nghi phạm) — tối đa 3 số',
  'needs': {'stat': 1}, 'most': {'pic': 1},
  'slots': {'pic': [{'pos': 'small'}], 'tape': {'*': [{'pin': 'tr', 'on': ['pic', 0]}]}}, 'all': {'sticker': {'w': 400}},
  'recipe': {'at': 14, 'edit': 'number', 'why': '…', 'items': [
      {'photo': 'sweat'}, {'stat': [['130', 'Stück in\nganz Japan', '14/130'], ['12', 'Käufer\nermittelt', '15/zwölf', 'yellow']]},
      {'tape': 'bis Ende 2025', 'color': 'white', 'at': '15/Ende'}]}},
 'object': {
  'vi': 'đồ vật cắt rời', 'sample': '1:38–1:49, 3:04–3:15',
  'look': 'một đồ vật cắt rời viền giấy trắng nằm giữa bảng; băng trắng tên hoặc số đo ở dưới, băng vàng chi tiết ở trên',
  'use': 'MỘT ĐỒ VẬT: câu tả một vật chứng (con dao, cái túi, chiếc giày), tên gọi, kích thước của nó',
  'needs': {'sticker': 1, 'tape': 1}, 'most': {'pic': 1},
  'slots': {'sticker': [{'pos': 'center', 'w': 780}], 'tape': {'white': [{'pin': 'below'}], 'red': [{'pin': 'below'}], '*': [{'pin': 'above'}, {'pin': 'below-r'}]}},
  'recipe': {'at': 16, 'edit': 'object', 'why': '…', 'items': [
      {'sticker': 'knife', 'rot': -18}, {'tape': 'SASHIMI-MESSER', 'color': 'white', 'at': '16/Sashimi'}, {'tape': 'Tatwaffe', 'at': '16/Tatwaffe'}]}},
 'detail': {
  'vi': 'khoanh chi tiết', 'sample': '1:50–2:01',
  'look': 'một ảnh lớn; vòng vàng (hoặc đỏ) vẽ tay khoanh chi tiết đúng lúc được nhắc, băng giấy ở các góc, băng trắng ở dưới',
  'use': 'CHỈ VÀO MỘT CHI TIẾT: câu nói "trên đó có…", một vết, một chỗ đáng chú ý trong ảnh hoặc tài liệu',
  'needs': {'photo': 1}, 'check': _ring,
  'slots': {'photo': [{'pos': 'main'}], 'tape': {'white': [{'pin': 'below-l', 'rot': -1}], 'red': [{'pin': 'below-l', 'rot': -1}], '*': [{'pin': 'tl'}, {'pin': 'br'}]}},
  'recipe': {'at': 17, 'edit': 'detail', 'why': '…', 'items': [
      {'photo': 'cloth', 'ring': {'box': [0.1, 0.5, 0.45, 0.8], 'at': '17/Taschentuch'}},
      {'tape': 'schwarzes Taschentuch', 'at': '17/Taschentuch'}, {'tape': 'SCHNITT ~3 CM', 'color': 'white', 'at': '17/Schnitt'}]}},
 'compare': {
  'vi': 'so sánh + dấu đỏ', 'sample': '2:08–2:15',
  'look': 'tờ giấy kem: hai vế gõ lần lượt, dấu ≠ đỏ ở giữa, rồi dấu đỏ kết luận đóng xuống',
  'use': 'SO SÁNH / MÂU THUẪN: câu đối chiếu hai thứ và có kết luận (DNA không trùng, lời khai không khớp, bị loại)',
  'needs': {'card:paper': 1}, 'most': {'pic': 0}, 'check': _stamp,
  'slots': {'card': [{'pos': 'center'}], 'tape': {'*': [{'pin': 'below'}]}},
  'recipe': {'at': 18, 'edit': 'compare', 'why': '…', 'items': [
      {'card': 'paper', 'head': 'DNA-ABGLEICH', 'rows': [['DNA Verdächtiger', '', '18/Mann'], {'l': '≠', 'color': 'red', 'at': '19/nicht'}, ['DNA Tatort', '', '19/Tatort']],
       'stamp': {'text': 'KEINE\nÜBEREINSTIMMUNG', 'at': '19/passt'}}]}},
 'statement': {
  'vi': 'một câu then chốt', 'sample': '2:16–2:19',
  'look': 'bảng trống, chỉ một băng giấy đỏ to ở giữa',
  'use': 'CÂU CHUYỂN: một câu ngắn báo điều sắp tới ("dann das verstörendste Detail"), bước ngoặt — không có vật gì để cho xem',
  'needs': {'tape': 1}, 'most': {'pic': 0, 'card': 0, 'tape': 2},
  'slots': {'tape': {'*': [{'pin': 'center', 'big': True, 'color': 'red'}, {'xy': [540, 1010], 'color': 'white'}]}},
  'recipe': {'at': 20, 'edit': 'statement', 'why': '…', 'items': [{'tape': 'das verstörendste Detail', 'at': 20.05}]}},
 'actions': {
  'vi': 'sổ ghi việc hắn làm', 'sample': '2:20–2:35',
  'look': 'ảnh ở nửa trên; trang sổ kẻ dòng ở nửa dưới, mỗi việc được đọc là một dòng chữ xanh có dấu ✓; băng đỏ ở mép dưới',
  'use': 'CHUỖI HÀNH ĐỘNG: câu kể lần lượt những việc một người đã làm (ăn, dùng máy tính, lục giấy tờ)',
  'needs': {'card:lined': 1, 'pic': 1}, 'most': {'pic': 1},
  'slots': {'pic': [{'pos': 'top'}], 'card': [{'pos': 'bottom'}],
            'tape': {'white': [{'pin': 'tr', 'on': ['pic', 0]}], 'red': [{'pin': 'bottom'}], '*': [{'pin': 'tl', 'on': ['pic', 0]}]}},
  'all': {'sticker': {'w': 520}},
  'recipe': {'at': 21, 'edit': 'actions', 'why': '…', 'items': [
      {'photo': 'kitchen'}, {'tape': 'FLOH NICHT', 'color': 'white', 'at': '21/floh'},
      {'card': 'lined', 'rows': [['gegessen', '', '22/aß'], ['Toilette benutzt', '', '22/Toilette'], ['Computer genutzt', '', '22/Computer']]}]}},
 'timeline': {
  'vi': 'ảnh + thẻ giờ giấc', 'sample': '2:36–2:55',
  'look': 'ảnh hoặc đồ vật ở nửa trên; thẻ giấy nhỏ ở nửa dưới gõ từng mốc giờ; băng đỏ ghi điều chưa chắc',
  'use': 'MỐC THỜI GIAN: câu có hai mốc giờ hoặc ngày trở lên (01:18, khoảng 10:00), trình tự trước – sau',
  'needs': {'card:paper': 1, 'pic': 1}, 'most': {'pic': 1},
  'slots': {'pic': [{'pos': 'top'}], 'card': [{'pos': 'bottom'}],
            'tape': {'red': [{'pin': 'bottom'}], '*': [{'pin': 'tr', 'on': ['pic', 0]}]}},
  'all': {'sticker': {'w': 520}},
  'recipe': {'at': 23, 'edit': 'timeline', 'why': '…', 'items': [
      {'sticker': 'pc'}, {'card': 'paper', 'head': 'INTERNET', 'rows': [['01:18 Uhr', 'online', '23/1:18'], ['ca. 10:00 Uhr', 'erneut', '23/10']]},
      {'tape': 'Zeitpunkt unsicher', 'color': 'red', 'at': '24/unsicher'}]}},
 'span': {
  'vi': 'thẻ nhỏ khoảng thời gian', 'sample': '3:28–3:31, 3:42–3:45',
  'look': 'một thẻ giấy nhỏ ở giữa: dòng đầu gõ chữ, một hai dòng kết quả (dòng quan trọng màu đỏ)',
  'use': 'KHOẢNG THỜI GIAN / TUỔI / ƯỚC TÍNH: câu nói bao nhiêu năm đã qua, tuổi lúc đó và bây giờ, một ước tính',
  'needs': {'card:paper': 1}, 'most': {'pic': 0},
  'slots': {'card': [{'pos': 'center', 'h': 520}], 'tape': {'*': [{'pin': 'below-r'}]}},
  'recipe': {'at': 26, 'edit': 'span', 'why': '…', 'items': [
      {'card': 'paper', 'head': 'ALTER DES TÄTERS', 'rows': [['damals', 'ca. 30', '26/damals'], {'l': 'heute', 'r': '50–60', 'color': 'red', 'at': '26/heute'}]},
      {'tape': 'nur eine Schätzung', 'at': '27/Presse'}]}},
 'board': {
  'vi': 'bảng chứng cứ nối dây đỏ', 'sample': '2:56–3:03',
  'look': '3–6 ảnh nhỏ và hình cắt rời xếp hai cột, hiện từng cái khi được nhắc, nối nhau bằng dây đỏ; băng nhỏ dưới mỗi cái',
  'use': 'TỔNG HỢP CHỨNG CỨ: câu điểm lại nhiều thứ cảnh sát đang có (máu, DNA, vân tay, quần áo) — thường trước câu "nhưng không có tên"',
  'needs': {'pic': 3},
  'slots': {'pic': G6, 'tape': {'white': [{'xy': [540, 1300], 'big': True}],
                                 '*': [{'pin': 'below', 'on': ['pic', k]} for k in range(6)]}},
  'all': {'sticker': {'w': 380}},
  'recipe': {'at': 28, 'edit': 'board', 'why': '…', 'items': [
      {'photo': 'site'}, {'photo': 'tubes', 'at': '28/Blut'}, {'photo': 'finger', 'at': '28/Finger'}, {'sticker': 'bag', 'at': '28/Kleidung'},
      {'string': [0, 1], 'at': '28/Blut'}, {'string': [1, 2], 'at': '28/Finger'}, {'string': [2, 3], 'at': '28/Kleidung'},
      {'tape': 'NAME: ???', 'color': 'white', 'at': '29/Nur'}]}},
 'question': {
  'vi': 'ảnh + câu hỏi / điều ngược lại', 'sample': '3:58–4:05',
  'look': 'một ảnh lớn đứng yên; băng trắng gõ câu hỏi ở mép dưới ảnh, rồi băng đỏ câu trả lời bên dưới',
  'use': 'CÂU HỎI MỞ / ĐIỀU NGƯỢC LẠI: câu đặt câu hỏi cho người xem, hoặc lật lại điều vừa nói (biến mất không dấu vết? — ngược lại)',
  'needs': {'photo': 1, 'tape': 1}, 'most': {'pic': 1},
  'slots': {'photo': [{'pos': 'main'}], 'tape': {'white': [{'pin': 'bottom'}], 'red': [{'pin': 'below'}], '*': [{'pin': 'tl'}]}},
  'recipe': {'at': 30, 'edit': 'question', 'why': '…', 'items': [
      {'photo': 'house', 'view': [0.1, 0, 0.9, 1]}, {'tape': 'SPURLOS?', 'color': 'white', 'at': '30/spurlos'},
      {'tape': 'im Gegenteil', 'color': 'red', 'at': '31/Gegenteil'}]}},
 'ending': {
  'vi': 'kết: chứng cứ + thẻ "tên: ???"', 'sample': '4:06–4:12',
  'look': 'hàng ảnh chứng cứ nhỏ ở trên nối dây đỏ; bên dưới một thẻ hồ sơ: `TÄTER` / `Name: ???` (dấu hỏi màu đỏ)',
  'use': 'KẾT: câu cuối — có gần như mọi thứ, trừ cái tên; câu hỏi còn bỏ ngỏ',
  'needs': {'pic': 2, 'card': 1}, 'most': {'pic': 4, 'card': 1},
  'slots': {'pic': G6[:4], 'card': [{'pos': [540, 1270, 720, 300]}], 'tape': {'*': [{'pin': 'above'}]}},
  'all': {'sticker': {'w': 380}},
  'recipe': {'at': 32, 'edit': 'ending', 'why': '…', 'items': [
      {'photo': 'site'}, {'photo': 'tubes'}, {'photo': 'finger'}, {'photo': 'sole'}, {'string': [0, 1]}, {'string': [1, 3]}, {'string': [2, 3]},
      {'card': 'paper', 'head': 'TÄTER', 'rows': [{'l': 'Name:', 'r': '???', 'color': 'red', 'at': '32/Namen'}], 'at': '32/außer'}]}},
}


# ---------------------------------------------------------------------------------------------------------------
# The mechanism (the same in both crime repos; the catalogue above is each repo's own)
# ---------------------------------------------------------------------------------------------------------------
def names():
    return list(EDITS)


def kind_of(it):
    return next((k for k in KINDS if k in it), None)


def _count(items, what):
    """How many items are `what`: a kind ("photo"), "pic" (any picture kind) or "kind:style" ("card:lined")."""
    kind, _, style = what.partition(':')
    n = 0
    for it in items:
        k = kind_of(it)
        if kind == 'pic' and k in PICS: n += 1
        elif k == kind and (not style or style_of(it) == style): n += 1
    return n


def _label(what):
    kind, _, style = what.partition(':')
    return (LABEL.get(kind, kind) + (f' "{style}"' if style else ''))


def recipe(name):
    return json.dumps(EDITS[name]['recipe'], ensure_ascii=False)


def apply(sc, n, fail):
    """Scene `sc` (number n) of picks.json with "edit": a copy in which every item has the template's defaults for
    what Claude left out (position, tilt, size, colour), after checking that the name exists and that the scene has
    the items the template is made of. A scene without "edit" is returned untouched."""
    if 'edit' not in sc:
        return sc
    name = sc['edit']
    if not isinstance(name, str) or name not in EDITS:
        fail(f'cảnh {n}: không có kiểu edit {json.dumps(name, ensure_ascii=False)}. Các kiểu: {", ".join(EDITS)}')
    if not isinstance(sc.get('why', ''), str):
        fail(f'cảnh {n}: "why" phải là một câu ngắn (chữ)')
    ed = EDITS[name]
    sc = copy.deepcopy(sc)
    for k, v in (ed.get('scene') or {}).items(): sc.setdefault(k, copy.deepcopy(v))
    items = sc.get('items') or []
    for k, it in enumerate(items):
        if kind_of(it) is None: fail(f'cảnh {n}, mục {k + 1}: thiếu loại ({", ".join(KINDS)})')
    for what, least in (ed.get('needs') or {}).items():
        have = _count(items, what)
        if have < least:
            fail(f'cảnh {n}: kiểu edit "{name}" cần ít nhất {least} {_label(what)} (đang có {have}). Mẫu: {recipe(name)}')
    for what, most in (ed.get('most') or {}).items():
        have = _count(items, what)
        if have > most:
            fail(f'cảnh {n}: kiểu edit "{name}" chỉ dùng tối đa {most} {_label(what)} (đang có {have}). Mẫu: {recipe(name)}')
    err = ed['check'](sc) if ed.get('check') else None
    if err: fail(f'cảnh {n}: kiểu edit "{name}": {err}. Mẫu: {recipe(name)}')

    slots, seen = ed.get('slots') or {}, {}
    given = [set(it) for it in items]                # what Claude wrote himself, before the template adds to it
    pic_index = [k for k, it in enumerate(items) if kind_of(it) in PICS]
    for k, it in enumerate(items):
        kind = kind_of(it)
        table = slots.get(kind, slots.get('pic') if kind in PICS else None)
        key = 'pic' if kind not in slots and kind in PICS else kind
        dflt = {}
        if isinstance(table, dict):                 # by colour: {'white': […], 'red': […], '*': […]}
            col = it.get('color', COLOR0)
            col = col if col in table else '*'
            table, key = table.get(col), f'{key}/{col}'
        if table:
            i = seen.get(key, 0); seen[key] = i + 1
            if i < len(table) or CYCLE:
                dflt = dict(table[i % len(table)])
            elif any(p not in it for p in PLACE):
                fail(f'cảnh {n}, mục {k + 1}: kiểu edit "{name}" chỉ có sẵn {len(table)} chỗ cho {LABEL.get(kind, kind)}'
                     f'{" màu này" if "/" in key else ""}; mục thừa phải tự ghi {", ".join(PLACE)}')
        dflt.update((ed.get('all') or {}).get(kind) or {})
        for mine, drop in GROUPS.get(kind, {}).items():   # Claude placed it himself: the template's place is not mixed in
            if mine in it:
                for g in drop: dflt.pop(g, None)
        for g, v in dflt.items():
            if isinstance(v, list) and len(v) == 2 and v[0] == 'pic':   # "on the 2nd picture of this scene" → item index
                if v[1] >= len(pic_index): continue
                v = pic_index[v[1]]
            it.setdefault(g, v)
    return finish(sc, n, fail, given) if finish else sc


def first_line(sc, default=1):
    """The script line a scene starts with (its "at": 3, 3.5, "3/Wort" or "3:言葉")."""
    m = re.match(r'\s*(\d+)', str(sc.get('at', default)))
    return int(m.group(1)) if m else default


def listing(scenes_in, text, bounds=None):
    """edits.md: one row per scene — number, time, first line, edit, why — for the closing comment, so the owner can
    answer "cảnh 5 đổi sang kiểu …". text = {line number: line}; bounds = scene start times (+ the end) or None."""
    rows, prev = [], None
    for j, sc in enumerate(scenes_in):
        name = sc.get('edit')
        line = (text.get(first_line(sc)) or '').replace('|', '/')
        if len(line) > 46: line = line[:45].rstrip() + '…'
        when = f'{bounds[j]:.0f}–{bounds[j + 1]:.0f} s' if bounds else ''
        kind = f'`{name}` — {EDITS[name]["vi"]}' if name in EDITS else '—'
        why = str(sc.get('why') or '').replace('|', '/').replace('\n', ' ')
        if name and name == prev: why = (why + ' ' if why else '') + '⚠️ trùng kiểu với cảnh trước'
        rows.append(f'| {j + 1} | {when} | {line} | {kind} | {why} |')
        prev = name
    return ('| Cảnh | Lúc | Câu đầu | Kiểu edit | Vì sao |\n|---|---|---|---|---|\n' + '\n'.join(rows) + '\n\n'
            'Muốn đổi kiểu của một cảnh: viết bình luận, ví dụ "cảnh 5 đổi sang kiểu `number`". Các kiểu: '
            + ', '.join(f'`{k}` ({v["vi"]})' for k, v in EDITS.items()) + '.\n')


def repeats(scenes_in):
    """Scene numbers that use the same edit as the scene before (the board should change shape every scene)."""
    return [j + 2 for j, (a, b) in enumerate(zip(scenes_in, scenes_in[1:])) if b.get('edit') and b.get('edit') == a.get('edit')]


def table_md():
    """The catalogue as the table of AGENT_CRIME.md (python3 scripts/crime/edits.py prints it)."""
    out = ['| `edit` | Trông thế nào (mẫu, phút:giây) | Dùng KHI các câu của cảnh nói về… | Công thức (chép rồi thay nội dung) |', '|---|---|---|---|']
    for k, v in EDITS.items():
        out.append(f'| `{k}`<br>{v["vi"]} | {v["look"]} ({v["sample"]}) | {v["use"]} | `{recipe(k).replace("|", "¦")}` |')
    return '\n'.join(out)


if __name__ == '__main__':
    print(table_md())
