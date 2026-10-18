"""Launch owned API/worker/Vite processes, run a real browser flow, then stop them."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import threading
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def available(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise RuntimeError(f'Port {port} in use; no existing process was touched')


def main():
    os.chdir(ROOT)
    for port in (3600, 6060):
        available(port)
    with tempfile.TemporaryDirectory(prefix='dubisub-e2e-') as temporary:
        work = Path(temporary)
        sample = work/'video tiếng Việt có khoảng trắng.mp4'
        sub = work/'phụ đề.srt'
        sub.write_text('1\n00:00:00,100 --> 00:00:01,200\nXin chào Việt Nam!\n\n2\n00:00:01,300 --> 00:00:02,900\nمرحبا 世界\n', encoding='utf-8-sig')
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=24:d=3','-f','lavfi','-i','sine=frequency=440:duration=3','-c:a','aac','-c:v','libx264','-pix_fmt','yuv420p','-y',str(sample)],check=True)
        stats={'speech_calls':0}
        class FixtureHandler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_HEAD(self):self.serve(False)
            def do_GET(self):
                if self.path=='/openapi.json':self.json_response({'paths':{'/v1/voices':{'post':{'requestBody':{'content':{'multipart/form-data':{'schema':{'$ref':'#/components/schemas/Enrollment'}}}}}}},'components':{'schemas':{'Enrollment':{'properties':{'name':{},'file':{},'denoise':{}}}}}});return
                if self.path=='/v1/voices':self.json_response({'data':[{'id':'fixture-vi','name':'Fixture Vietnamese','languages':['vi'],'gender':'female'},{'id':'fixture-en','name':'Fixture English','languages':['en'],'gender':'male'}]});return
                if self.path=='/v1/models':self.json_response({'data':[{'id':'fixture-model'},{'id':'vieneu-v3-turbo'}]});return
                self.serve(True)
            def json_response(self,value):
                data=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def do_POST(self):
                if self.path=='/v1/voices':
                    import re
                    raw=self.rfile.read(int(self.headers['Content-Length']));name=re.search(b'name="name"\r\n\r\n([^\r]+)',raw).group(1).decode();self.json_response({'id':name});return
                if self.path=='/v1/audio/speech':
                    import wave,io
                    self.rfile.read(int(self.headers['Content-Length']));stats['speech_calls']+=1
                    stream=io.BytesIO()
                    with wave.open(stream,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\x00\x00'*32000)
                    content=stream.getvalue();self.send_response(200);self.send_header('Content-Type','audio/wav');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
                if self.path!='/v1/chat/completions':self.send_error(404);return
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                content=body['messages'][-1]['content']
                if content.startswith('Return JSON only: '):
                    self.json_response({'choices':[{'message':{'content':content.removeprefix('Return JSON only: ')}}]});return
                payload=json.loads(content)
                if 'evidence' in payload:
                    self.json_response({'choices':[{'message':{'content':json.dumps({'items':[{'text':'Fixture review narration','evidence_ids':list(payload['evidence'])[:1]}]})}}]});return
                answer={'cues':[{'id':c['id'],'text':'fixture-'+payload['target_language']+': '+c['text']} for c in payload['cues']]}
                self.json_response({'choices':[{'message':{'content':json.dumps(answer)}}]})
            def serve(self,body):
                if self.path not in ('/fixture.mp4','/fixture.srt'):
                    self.send_error(404);return
                path=sample if self.path.endswith('.mp4') else sub
                self.send_response(200);self.send_header('Content-Length',str(path.stat().st_size));self.send_header('Content-Type','video/mp4' if path==sample else 'text/plain');self.end_headers()
                if body:self.wfile.write(path.read_bytes())
        fixture=ThreadingHTTPServer(('127.0.0.1',0),FixtureHandler)
        fixture_thread=threading.Thread(target=fixture.serve_forever,daemon=True);fixture_thread.start()
        env = dict(os.environ, DUBISUB_DATA_DIR=str(work/'dữ liệu riêng'))
        processes = []
        log = (work/'servers.log').open('w',encoding='utf-8')
        try:
            for args in ([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','6060'],
                         [sys.executable,str(ROOT/'tests/url_fixture_worker.py'),str(fixture.server_port)],
                         [shutil.which('node'),str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','3600','--strictPort']):
                processes.append(subprocess.Popen(args,cwd=ROOT/'frontend' if args[0]==shutil.which('node') else ROOT, env=env, stdout=log, stderr=log))
            for port in (6060,3600):
                deadline=time.monotonic()+30
                while True:
                    try:
                        urlopen(f'http://127.0.0.1:{port}'+('/health' if port==6060 else '/'),timeout=1).close()
                        break
                    except Exception:
                        if time.monotonic()>deadline:raise RuntimeError('Server startup timed out')
                        time.sleep(.25)
            with sync_playwright() as pw:
                # Installed Edge supplies Windows H.264 playback; bundled Chromium may not.
                browser=pw.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:3600')
                page.wait_for_load_state('networkidle')
                assert page.evaluate('document.documentElement.dataset.theme')=='dark'
                page.get_by_role('button',name='Cài đặt studio',exact=True).click()
                settings=page.get_by_role('dialog',name='Cài đặt',exact=True)
                expect(settings).to_be_visible()
                settings.get_by_label('Sáng',exact=False).check()
                assert page.evaluate('document.documentElement.dataset.theme')=='light'
                settings.get_by_label('Tối',exact=False).check()
                settings.get_by_role('navigation',name='Nhóm cấu hình').get_by_role('button',name='LLM · Dịch & kịch bản',exact=True).click()
                settings.get_by_label('Endpoint API',exact=True).fill(f'http://127.0.0.1:{fixture.server_port}/v1')
                settings.get_by_label('Model',exact=True).fill('fixture-model')
                settings.get_by_role('button',name='Lưu cấu hình',exact=True).click()
                page.wait_for_function("fetch('/api/settings').then(r=>r.json()).then(s=>s.providers.some(p=>p.kind==='translation'&&p.model==='fixture-model'))")
                settings.get_by_label('Đồng ý gửi prompt/ảnh tổng hợp',exact=False).check()
                settings.get_by_role('button',name='Kiểm tra text',exact=True).click()
                expect(settings.locator('.capability-status .verified').filter(has_text='text:')).to_be_visible(timeout=20000)
                settings.get_by_role('navigation',name='Nhóm cấu hình').get_by_role('button',name='Giọng đọc',exact=True).click()
                settings.get_by_label('Endpoint API',exact=True).fill(f'http://127.0.0.1:{fixture.server_port}/v1')
                settings.get_by_label('Model',exact=True).fill('vieneu-v3-turbo')
                settings.get_by_role('button',name='Lưu cấu hình',exact=True).click()
                page.wait_for_function("fetch('/api/settings').then(r=>r.json()).then(s=>s.providers.some(p=>p.kind==='tts'&&p.model==='vieneu-v3-turbo'))")
                settings.get_by_role('navigation',name='Nhóm cấu hình').get_by_role('button',name='Lưu trữ & media',exact=True).click()
                expect(settings.get_by_text('FFmpeg',exact=True)).to_be_visible()
                settings.get_by_role('button',name='Đóng cài đặt',exact=True).click()
                expect(page.get_by_role('heading',name='Tạo dự án',exact=True)).to_be_visible()
                # All core studio surfaces exist before selecting or creating a project.
                expect(page.get_by_role('navigation',name='Công cụ studio')).to_be_visible()
                expect(page.get_by_role('heading',name='Phụ đề nguồn',exact=True)).to_be_visible()
                expect(page.get_by_role('region',name='Timeline nguồn')).to_be_visible()
                assert page.locator('.studio-banner').evaluate('(i)=>i.complete && i.naturalWidth > 0')
                assert page.locator('.brand-wordmark').evaluate('(i)=>i.complete && i.naturalWidth > 0')
                assert 'svg+xml' in page.locator('body').evaluate('(e)=>getComputedStyle(e).cursor')
                page.get_by_label('Tên dự án').fill('Bản dịch thử nghiệm')
                page.get_by_label('Chế độ',exact=True).select_option('review')
                page.get_by_role('button',name='Tạo dự án',exact=True).click()
                expect(page.get_by_role('heading',name='Bản dịch thử nghiệm')).to_be_visible()
                page.get_by_label('Nhập video hoặc audio',exact=True).set_input_files(sample)
                expect(page.get_by_text('succeeded',exact=False)).to_be_visible(timeout=20000)
                page.wait_for_function('document.querySelector("video")?.readyState >= 1')
                assert page.locator('video').evaluate('(v)=>v.duration') == 3
                page.get_by_label('Nhập phụ đề',exact=True).set_input_files(sub)
                cue=page.get_by_label('Câu 1',exact=True)
                expect(cue).to_have_value('Xin chào Việt Nam!',timeout=15000)
                cue.fill('Chào DubiSub — tiếng Việt 世界')
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Hoàn tác',exact=True).click()
                expect(cue).to_have_value('Xin chào Việt Nam!')
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Làm lại',exact=True).click()
                expect(cue).to_have_value('Chào DubiSub — tiếng Việt 世界')
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Tới câu 2',exact=True).click()
                assert abs(page.locator('video').evaluate('(v)=>v.currentTime')-1.3)<.05
                # Reopening must round-trip through SQLite, not component state.
                page.reload();page.wait_for_load_state('networkidle')
                page.locator('.project-open').filter(has_text='Bản dịch thử nghiệm').click()
                expect(page.get_by_label('Câu 1',exact=True)).to_have_value('Chào DubiSub — tiếng Việt 世界')
                expect(page.get_by_label('Câu 2',exact=True)).to_have_value('مرحبا 世界')
                page.wait_for_function('document.querySelector("video")?.textTracks[0]?.cues?.length === 2')
                page.get_by_role('slider',name='Thu phóng timeline',exact=True).fill('2')
                assert page.locator('.timeline-content').evaluate('(e)=>e.style.width') == '200%'
                page.get_by_role('slider',name='Vị trí phát',exact=True).fill('2')
                assert abs(page.locator('video').evaluate('(v)=>v.currentTime')-2)<.05
                page.get_by_role('button',name='Phát video',exact=True).click()
                expect(page.get_by_role('button',name='Tạm dừng',exact=True)).to_be_visible()
                page.get_by_role('button',name='Tạm dừng',exact=True).click()
                page.get_by_label('Tỷ lệ preview').select_option('9/16')
                assert page.locator('.preview-frame').evaluate('(e)=>e.style.aspectRatio') == '9 / 16'
                page.get_by_label('Tỷ lệ preview').select_option('16/9')
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Dịch thuật',exact=True).click()
                expect(page.get_by_role('heading',name='Transcript & bản dịch',exact=True)).to_be_visible()
                expect(page.get_by_role('heading',name='Phụ đề nguồn',exact=True)).to_be_visible()
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Phụ đề',exact=True).click()
                for fmt in ('SRT','VTT','ASS'):
                    with page.expect_download() as download:
                        page.get_by_role('link',name='Xuất '+fmt,exact=True).click()
                    content=Path(download.value.path()).read_text(encoding='utf-8')
                    assert 'Chào DubiSub — tiếng Việt 世界' in content
                    assert 'مرحبا 世界' in content
                    assert ('00:00:00,100' if fmt=='SRT' else '00:00:00.100' if fmt=='VTT' else '0:00:00.10') in content
                page.locator('.subtitle-tools summary').click()
                page.get_by_label('Tìm chữ phụ đề',exact=True).fill('Chào DubiSub')
                page.get_by_label('Thay chữ phụ đề',exact=True).fill('Đổi thử')
                page.get_by_role('button',name='Thay tất cả',exact=False).click()
                expect(page.get_by_label('Câu 1',exact=True)).to_have_value('Đổi thử — tiếng Việt 世界')
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Hoàn tác',exact=True).click()
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Tách câu 1',exact=True).click()
                expect(page.locator('.cues article')).to_have_count(3)
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Gộp câu 1 với câu sau',exact=True).click()
                expect(page.locator('.cues article')).to_have_count(2)
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Hoàn tác',exact=True).click()
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                page.get_by_role('button',name='Hoàn tác',exact=True).click()
                expect(page.get_by_role('status')).to_have_text('Đã tự lưu',timeout=10000)
                expect(page.get_by_label('Câu 1',exact=True)).to_have_value('Chào DubiSub — tiếng Việt 世界')
                page.locator('.subtitle-tools summary').click()
                page.get_by_label('Vùng xuất bắt đầu',exact=True).fill('1000')
                page.get_by_label('Vùng xuất kết thúc',exact=True).fill('3000')
                page.get_by_label('Tốc độ xuất',exact=True).select_option('2')
                page.get_by_role('button',name='Xuất MP4',exact=True).click()
                expect(page.locator('.artifact-list a')).to_have_count(1,timeout=20000)
                with page.expect_download() as rendered:
                    page.locator('.artifact-list a').click()
                assert Path(rendered.value.path()).stat().st_size>100
                page.get_by_label('Ngôn ngữ dịch đích',exact=True).fill('vi, en')
                page.get_by_role('button',name='Dịch track đã chọn',exact=True).click()
                expect(page.locator('.track-select option')).to_have_count(3,timeout=20000)
                english=page.locator('.track-select option').filter(has_text='· en ·').get_attribute('value')
                page.get_by_label('Track phụ đề',exact=True).select_option(english)
                expect(page.get_by_label('Câu 1',exact=True)).to_have_value('fixture-en: Chào DubiSub — tiếng Việt 世界')
                page.get_by_role('button',name='Đánh dấu đã duyệt',exact=True).click()
                expect(page.get_by_role('button',name='Bỏ duyệt track',exact=True)).to_be_visible()
                first=page.locator('.track-select option').first.get_attribute('value')
                page.get_by_label('Track phụ đề',exact=True).select_option(first)
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Giọng đọc',exact=True).click()
                page.get_by_role('button',name='Lấy danh sách giọng từ provider',exact=True).click()
                expect(page.get_by_label('Giọng provider',exact=True)).to_have_value('fixture-vi')
                page.get_by_role('button',name='Tạo mẫu nghe chuẩn',exact=True).click()
                expect(page.locator('.voice-panel audio')).to_have_count(1,timeout=15000)
                old_audio=page.locator('.voice-panel audio').element_handle()
                old_audio.evaluate('(a)=>a.play()')
                page.get_by_label('Ngôn ngữ giọng',exact=True).select_option('en')
                assert old_audio.evaluate('(a)=>a.paused')
                expect(page.get_by_label('Giọng provider',exact=True)).to_have_value('fixture-en')
                page.get_by_label('Ngôn ngữ giọng',exact=True).select_option('vi')
                expect(page.locator('.voice-panel audio')).to_have_count(1)
                page.locator('.voice-panel audio').evaluate('(a)=>a.play()')
                assert stats['speech_calls']==1
                # Controlled cloning contract + actual FFmpeg reference extraction/mix/export.
                # Fixture audio is synthetic, not evidence of live voice similarity.
                panel=page.locator('.dubbing-panel')
                panel.get_by_role('button',name='Kiểm tra VieNeu & lấy giọng',exact=True).click()
                expect(panel.get_by_text('vieneu-v3-turbo',exact=True)).to_be_visible()
                panel.get_by_text('Lấy giọng mẫu từ media (3–8 giây)',exact=True).click()
                panel.get_by_label('Mẫu giọng từ giây',exact=True).fill('0')
                panel.get_by_label('Mẫu giọng đến giây',exact=True).fill('3')
                panel.get_by_label('Tên hồ sơ giọng',exact=True).fill('Synthetic fixture reference')
                panel.get_by_label('Tôi sở hữu hoặc được phép sử dụng giọng mẫu này.',exact=True).check()
                panel.get_by_label('Tôi đã nghe lại: đoạn sạch, chỉ một người nói.',exact=True).check()
                panel.get_by_role('button',name='Cắt & lưu hồ sơ giọng',exact=True).click()
                expect(panel.locator('.reference-card')).to_have_count(1,timeout=15000)
                panel.get_by_label('Nguồn giọng',exact=True).select_option('profile')
                expect(panel.get_by_label('Giọng lồng tiếng',exact=True)).not_to_have_value('')
                panel.locator('.dubbing-consent').filter(has_text='Tôi đồng ý gửi văn bản').locator('input').check()
                panel.get_by_role('button',name='Tạo mẫu nghe / đọc văn bản',exact=True).click()
                expect(panel.locator('.narration-result')).to_have_count(1,timeout=20000)
                panel.get_by_text('Nhân vật & đọc track phụ đề',exact=True).click()
                panel.get_by_role('button',name='Thêm nhân vật',exact=True).click()
                panel.locator('.narration-cues select').first.select_option('Nhân vật 1')
                panel.get_by_label('Xuất thêm MP4 dùng video gốc và giọng đọc mới (thay audio gốc).',exact=True).check()
                panel.get_by_role('button',name='Đọc track đã chọn',exact=True).click()
                expect(panel.locator('.narration-result')).to_have_count(2,timeout=25000)
                expect(panel.get_by_text('Tải MP4 có giọng đọc',exact=True)).to_be_visible()
                with page.expect_download() as narrated:
                    panel.get_by_text('Tải MP4 có giọng đọc',exact=True).click()
                assert Path(narrated.value.path()).stat().st_size>100
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Phụ đề',exact=True).click()
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Giọng đọc',exact=True).click()
                expect(panel.locator('.narration-cues select').first).to_have_value('Nhân vật 1')
                panel.get_by_role('button',name='Kiểm tra VieNeu & lấy giọng',exact=True).click()
                expect(panel.get_by_text('vieneu-v3-turbo',exact=True)).to_be_visible()
                panel.locator('.dubbing-consent').filter(has_text='Tôi đồng ý gửi văn bản').locator('input').check()
                panel.get_by_text('Nhân vật & đọc track phụ đề',exact=True).click()
                panel.get_by_role('button',name='Tạo lại riêng câu',exact=True).first.click()
                expect(panel.locator('.narration-result')).to_have_count(3,timeout=20000)
                assert panel.locator('.narration-warning').count()>0
                page.screenshot(path='test-results/studio-clone-fixture.png',full_page=True)
                page.once('dialog',lambda dialog:dialog.accept())
                panel.get_by_role('button',name='Xóa hồ sơ & dữ liệu mẫu',exact=True).click()
                expect(panel.locator('.reference-card')).to_have_count(0,timeout=15000)
                expect(panel.locator('.narration-result')).to_have_count(0)

                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Phụ đề',exact=True).click()
                page.get_by_role('button',name='Auto',exact=True).click()
                auto=page.get_by_role('dialog',name='Xử lý video tự động',exact=True)
                auto.get_by_role('button',name='6. Đầu ra',exact=True).click()
                auto.get_by_label('Đầu ra Auto',exact=True).select_option('subtitles')
                auto.get_by_role('button',name='7. Xem & chạy',exact=True).click()
                auto.get_by_role('button',name='Lập kế hoạch Auto',exact=True).click()
                auto.get_by_label('Tôi xác nhận nguồn, pipeline',exact=False).check()
                auto.get_by_role('button',name='Chạy Auto',exact=True).click()
                expect(auto.locator('.auto-runs a')).to_have_count(3,timeout=25000)
                with page.expect_download() as auto_sub:
                    auto.locator('.auto-runs a').filter(has_text='SRT').click()
                assert 'fixture-vi:' in Path(auto_sub.value.path()).read_text(encoding='utf-8')
                auto.get_by_role('button',name='2. Mục tiêu',exact=True).click()
                auto.get_by_label('Chế độ Auto',exact=True).select_option('review')
                auto.get_by_role('button',name='6. Đầu ra',exact=True).click()
                auto.get_by_label('Đầu ra Auto',exact=True).select_option('draft')
                auto.get_by_role('button',name='7. Xem & chạy',exact=True).click()
                auto.get_by_role('button',name='Lập kế hoạch Auto',exact=True).click()
                auto.get_by_label('Tôi xác nhận nguồn, pipeline',exact=False).check()
                auto.get_by_role('button',name='Chạy Auto',exact=True).click()
                expect(auto.locator('.auto-runs article').filter(has_text='draft')).to_have_count(1,timeout=20000)
                auto.get_by_role('button',name='Đóng Auto',exact=True).click()
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Review',exact=True).click()
                analysis=page.locator('.analysis-panel')
                expect(analysis.get_by_text('Chỉ phân tích transcript',exact=True)).to_be_visible()
                analysis.get_by_role('button',name='Duyệt nội dung',exact=True).click()
                expect(analysis.locator('summary')).to_contain_text('Đã duyệt')
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Giọng đọc',exact=True).click()
                panel=page.locator('.dubbing-panel')
                panel.get_by_role('button',name='Kiểm tra VieNeu & lấy giọng',exact=True).click()
                expect(panel.get_by_text('Đã đọc khả năng provider. Chưa gửi audio mẫu.',exact=True)).to_be_visible()
                panel.get_by_label('Nguồn giọng',exact=True).select_option('preset')
                panel.get_by_label('Giọng lồng tiếng',exact=True).select_option('preset|fixture-vi')
                panel.get_by_label('Tôi đồng ý gửi văn bản',exact=False).check()
                panel.locator('summary').filter(has_text='Đọc kịch bản / dựng video review').click()
                panel.get_by_label('Kịch bản lời dẫn',exact=True).select_option(index=1)
                panel.get_by_label('Xuất MP4 review 640',exact=False).check()
                panel.get_by_role('button',name='Tạo lời dẫn / review đã duyệt',exact=True).click()
                expect(panel.locator('.narration-result').filter(has_text='Lời dẫn / review theo timeline mới')).to_have_count(1,timeout=25000)
                review_track=page.locator('.track-select option').filter(has_text='Lời dẫn review').get_attribute('value')
                page.get_by_label('Track phụ đề',exact=True).select_option(review_track)
                expect(page.get_by_role('region',name='Timeline review',exact=True)).to_be_visible()
                assert '/narrations/' in page.locator('video').get_attribute('src')
                page.get_by_label('Track phụ đề',exact=True).select_option(first)
                page.get_by_role('navigation',name='Công cụ studio').get_by_role('button',name='Phụ đề',exact=True).click()

                page.get_by_label('Câu 1',exact=True).focus()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement !== document.body')
                Path('test-results').mkdir(exist_ok=True)
                page.screenshot(path='test-results/studio-desktop.png',full_page=True)
                page.get_by_role('button',name='Chuyển sang giao diện sáng',exact=True).click()
                page.wait_for_function("getComputedStyle(document.querySelector('.new-project')).backgroundColor==='rgb(238, 235, 255)'")
                page.screenshot(path='test-results/studio-light-auto.png',full_page=True)
                page.get_by_role('button',name='Chuyển sang giao diện tối',exact=True).click()
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path='test-results/studio-mobile.png',full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                assert not errors, errors
                page.set_viewport_size({'width':1440,'height':1000})
                page.get_by_role('button',name='Sửa dự án Bản dịch thử nghiệm',exact=True).click()
                edit=page.get_by_role('dialog',name='Sửa dự án',exact=True)
                edit.get_by_label('Tên dự án mới',exact=True).fill('Bản dịch đã sửa')
                edit.get_by_role('button',name='Lưu thay đổi',exact=True).click()
                expect(page.get_by_role('heading',name='Bản dịch đã sửa',exact=True)).to_be_visible()
                page.get_by_role('button',name='Xóa dự án Bản dịch đã sửa',exact=True).click()
                remove=page.get_by_role('dialog',name='Xóa dự án',exact=True)
                remove.get_by_role('button',name='Hủy',exact=True).click()
                expect(page.get_by_role('heading',name='Bản dịch đã sửa',exact=True)).to_be_visible()
                page.get_by_role('button',name='Xóa dự án Bản dịch đã sửa',exact=True).click()
                remove.get_by_role('button',name='Xóa dự án',exact=True).click()
                expect(page.get_by_role('button',name='Khôi phục dự án',exact=True)).to_be_visible()
                expect(page.locator('.project-open').filter(has_text='Bản dịch đã sửa')).to_have_count(0)
                page.get_by_role('button',name='Khôi phục dự án',exact=True).click()
                page.locator('.project-open').filter(has_text='Bản dịch đã sửa').click()
                expect(page.get_by_label('Câu 1',exact=True)).to_have_value('Chào DubiSub — tiếng Việt 世界')
                page.screenshot(path='test-results/studio-dark-managed.png',full_page=True)
                page.get_by_role('button',name='Cài đặt studio',exact=True).click()
                page.screenshot(path='test-results/studio-settings.png',full_page=True)
                page.get_by_role('button',name='Đóng cài đặt',exact=True).click()
                page.get_by_label('Link YouTube hoặc file trực tiếp',exact=True).fill(f'http://127.0.0.1:{fixture.server_port}/fixture.mp4')
                page.get_by_role('button',name='Phân tích liên kết',exact=True).click()
                expect(page.locator('.link-details').get_by_text('fixture.mp4',exact=True)).to_be_visible(timeout=15000)
                page.get_by_role('button',name='Nhập vào dự án',exact=True).click()
                expect(page.get_by_role('button',name='Đã nhập vào dự án',exact=True)).to_be_visible(timeout=15000)
                expect(page.locator('.asset-list .asset')).to_have_count(3,timeout=15000)
                page.screenshot(path='test-results/studio-link-import.png',full_page=True)
                browser.close()
                print('PASS: real upload/probe, video seek, Unicode/RTL edit, autosave, undo/redo, reopen, SRT/VTT downloads, keyboard focus, mobile width; no browser errors')
        except Exception:
            if 'page' in locals():
                try: print(page.locator('body').inner_text().encode('ascii','backslashreplace').decode())
                except Exception: pass
            log.flush()
            print((work/'servers.log').read_text(encoding='utf-8',errors='replace')[-6000:])
            raise
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in processes:
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close()
            fixture.shutdown();fixture.server_close();fixture_thread.join()


if __name__=='__main__':main()
