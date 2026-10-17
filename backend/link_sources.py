"""YouTube extraction and direct-file inspection using only the safe HTTP transport."""
import io
import json
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit, parse_qs

from yt_dlp import YoutubeDL
from yt_dlp.networking.common import RequestHandler, Response
from yt_dlp.networking.exceptions import HTTPError, RequestError
from .safe_http import SafeHTTP, NetworkPolicyError, redact

MAX_INFO = 8*1024**2
EXTENSIONS = {'mp4','mkv','mov','webm','mp3','m4a','wav','ogg','flac','srt','vtt','ass'}


class Quiet:
    def debug(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass


def youtube_url(url):
    p = urlsplit(url)
    host = (p.hostname or '').lower()
    if host not in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','www.youtube-nocookie.com'):
        return None
    query = parse_qs(p.query)
    if 'list' in query:
        raise ValueError('Hãy dán link một video; playlist chưa được hỗ trợ.')
    parts = p.path.strip('/').split('/')
    video_id = parts[0] if host == 'youtu.be' else (query.get('v',[''])[0] if p.path == '/watch' else (parts[1] if len(parts)>1 and parts[0] in ('shorts','embed','live') else ''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('Không tìm thấy ID video YouTube trong liên kết.')
    return 'https://www.youtube.com/watch?v='+video_id


def extractor(client):
    class GuardedRH(RequestHandler):
        _SUPPORTED_URL_SCHEMES = ('http','https')
        _SUPPORTED_PROXY_SCHEMES = ()

        def _check_extensions(self, extensions):
            for key in ('cookiejar','timeout','legacy_ssl','keep_header_casing'):
                extensions.pop(key, None)

        def _send(self, request):
            try:
                with client.open(request.url, method=request.method, headers=dict(self._merge_headers(request.headers)), data=request.data) as received:
                    if received.headers.get('Content-Encoding','identity') not in ('identity',''):
                        raise NetworkPolicyError('Nguồn trả nội dung nén không hỗ trợ.')
                    body = received.read(MAX_INFO+1)
                    if len(body)>MAX_INFO:
                        raise NetworkPolicyError('Thông tin nguồn vượt giới hạn 8 MiB.')
                    response=Response(io.BytesIO(body), url=received.url, headers=dict(received.headers), status=received.status)
                    if received.status>=400:
                        raise HTTPError(response)
                    return response
            except (NetworkPolicyError, OSError) as exc:
                raise RequestError('DubiSub: request nguồn bị chặn hoặc thất bại') from None

    class GuardedYDL(YoutubeDL):
        def build_request_director(self, handlers, preferences=None):
            # Replace every built-in/plugin handler: there is no network fallback.
            return super().build_request_director([GuardedRH], [])

    return GuardedYDL({'quiet':True,'no_warnings':True,'logger':Quiet(),'noplaylist':True,'skip_download':True,
                       'cachedir':False,'proxy':'','socket_timeout':15,'retries':1,'extractor_retries':1,
                       'js_runtimes':{},'remote_components':[], 'enable_file_urls':False,
                       'allowed_extractors':['youtube'], 'extract_flat':False})


def inspect_source(url, client=None):
    client = client or SafeHTTP()
    # Initial URL validation applies even before canonicalizing a YouTube URL.
    client.validate(url)
    canonical = youtube_url(url)
    if canonical:
        try:
            with extractor(client) as ydl:
                info=ydl.extract_info(canonical,download=False)
        except Exception:
            raise ValueError('Không đọc được YouTube. Video có thể yêu cầu đăng nhập, bị giới hạn, hoặc YouTube yêu cầu xác minh/runtime chưa hỗ trợ. Không có cookie nào được tự lấy.') from None
        if not info or info.get('_type') in ('playlist','multi_video') or info.get('is_live') or info.get('has_drm'):
            raise ValueError('Chưa hỗ trợ playlist, livestream hoặc nội dung DRM.')
        formats=[]
        for f in info.get('formats',[]):
            if f.get('has_drm') or f.get('protocol') not in ('http','https') or not str(f.get('url','')).startswith(('http://','https://')):
                continue
            formats.append({k:f.get(k) for k in ('format_id','url','ext','height','width','vcodec','acodec','filesize','filesize_approx','http_headers','language')})
        subtitles=[]
        for automatic, group in ((False,info.get('subtitles',{})),(True,info.get('automatic_captions',{}))):
            for language, entries in group.items():
                match=next((e for e in entries if e.get('ext') in ('vtt','srt') and str(e.get('url','')).startswith(('http://','https://'))),None)
                if match:
                    subtitles.append({'id':f'{"auto" if automatic else "manual"}:{language}', 'language':language,'automatic':automatic,'ext':match['ext'],'url':match['url']})
        if not formats and not subtitles:
            raise ValueError('YouTube không cung cấp file tải trực tiếp được hỗ trợ cho video này.')
        return {'title':str(info.get('title') or 'YouTube video')[:300], 'duration':info.get('duration'), 'source':'youtube',
                'source_url':canonical,'formats':formats[:100], 'subtitles':subtitles[:200], 'thumbnail_url':info.get('thumbnail')}
    response=client.open(url,method='HEAD')
    if response.status in (405,501):
        response.close();response=client.open(url,headers={'Range':'bytes=0-0'})
    with response:
        if response.status>=400:
            raise ValueError('Nguồn không hỗ trợ đọc thông tin file (HEAD) hoặc từ chối truy cập.')
        ext=PurePosixPath(urlsplit(response.url).path).suffix.lower().lstrip('.')
        content_type=response.headers.get('Content-Type','').split(';')[0].lower()
        if ext not in EXTENSIONS or content_type in ('text/html','application/xhtml+xml'):
            raise ValueError('Nguồn này chưa được hỗ trợ. Dùng link YouTube hoặc link file video/audio/SRT/VTT/ASS trực tiếp.')
        length=response.headers.get('Content-Length')
        size=int(length) if length and length.isdigit() else None
        content_range=response.headers.get('Content-Range','')
        if response.status==206 and re.fullmatch(r'bytes \d+-\d+/\d+',content_range):size=int(content_range.rsplit('/',1)[1])
        title=PurePosixPath(urlsplit(response.url).path).name[:300] or 'Media từ liên kết'
        if ext in ('srt','vtt','ass'):
            return {'title':title,'duration':None,'source':'direct','source_url':redact(url),'formats':[],
                    'subtitles':[{'id':'direct','language':'und','automatic':False,'ext':ext,'url':url}]}
        audio=ext in ('mp3','m4a','wav','ogg','flac')
        return {'title':title,'duration':None,'source':'direct','source_url':redact(url),'subtitles':[],
                'formats':[{'format_id':'direct','url':url,'ext':ext,'filesize':size,'height':None,'vcodec':'none' if audio else 'unknown','acodec':'unknown','http_headers':{}}]}


def public_info(info):
    # Never expose signed stream URLs or extractor headers/cookies to browser/logs.
    result={k:info.get(k) for k in ('title','duration','source','source_url')}
    result['has_thumbnail']=bool(info.get('has_thumbnail'))
    result['formats']=[{k:f.get(k) for k in ('format_id','ext','height','filesize','filesize_approx','vcodec','acodec','language')} for f in info.get('formats',[])]
    result['subtitles']=[{k:s[k] for k in ('id','language','automatic','ext')} for s in info.get('subtitles',[])]
    return result
