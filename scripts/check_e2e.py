"""Launch owned API/worker/Vite processes, run a real browser flow, then stop them."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
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
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=24:d=3','-c:v','libx264','-pix_fmt','yuv420p','-y',str(sample)],check=True)
        env = dict(os.environ, DUBISUB_DATA_DIR=str(work/'dữ liệu riêng'))
        processes = []
        log = (work/'servers.log').open('w',encoding='utf-8')
        try:
            for args in ([sys.executable,'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','6060'],
                         [sys.executable,'-m','backend.worker'],
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
                expect(page.get_by_role('heading',name='Tạo dự án',exact=True)).to_be_visible()
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
                page.get_by_role('button',name='Bản dịch thử nghiệm',exact=False).click()
                expect(page.get_by_label('Câu 1',exact=True)).to_have_value('Chào DubiSub — tiếng Việt 世界')
                expect(page.get_by_label('Câu 2',exact=True)).to_have_value('مرحبا 世界')
                page.wait_for_function('document.querySelector("video")?.textTracks[0]?.cues?.length === 2')
                for fmt in ('SRT','VTT'):
                    with page.expect_download() as download:
                        page.get_by_role('link',name='Xuất '+fmt,exact=True).click()
                    content=Path(download.value.path()).read_text(encoding='utf-8')
                    assert 'Chào DubiSub — tiếng Việt 世界' in content
                    assert 'مرحبا 世界' in content
                    assert ('00:00:00,100' if fmt=='SRT' else '00:00:00.100') in content
                page.get_by_label('Câu 1',exact=True).focus()
                page.keyboard.press('Tab')
                assert page.evaluate('document.activeElement !== document.body')
                Path('test-results').mkdir(exist_ok=True)
                page.screenshot(path='test-results/studio-desktop.png',full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                page.screenshot(path='test-results/studio-mobile.png',full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                assert not errors, errors
                browser.close()
                print('PASS: real upload/probe, video seek, Unicode/RTL edit, autosave, undo/redo, reopen, SRT/VTT downloads, keyboard focus, mobile width; no browser errors')
        except Exception:
            if 'page' in locals():
                print(page.locator('body').inner_text().encode('ascii','backslashreplace').decode())
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


if __name__=='__main__':main()
