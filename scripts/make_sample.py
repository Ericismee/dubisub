"""Generate owned, synthetic fixtures; never presented as real AI output."""
import subprocess
from pathlib import Path

directory = Path('data/samples')
directory.mkdir(parents=True, exist_ok=True)
(directory/'mẫu phụ đề.srt').write_text('1\n00:00:00,200 --> 00:00:01,500\nXin chào Việt Nam!\n\n2\n00:00:01,600 --> 00:00:02,800\nمرحبا 世界\n', encoding='utf-8-sig')
subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=24:duration=3',
                '-f','lavfi','-i','sine=frequency=440:duration=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',
                '-n',str(directory/'video mẫu.mp4')],check=True)
print(directory.resolve())
