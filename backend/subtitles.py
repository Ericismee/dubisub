"""All source cue times are integer milliseconds; lossy style conversion is explicit."""
import pysubs2
from .store import uid

MAX_CUES = 20000


def parse(text: str, extension: str):
    if len(text.encode('utf-8')) > 8 * 1024 * 1024:
        raise ValueError('Subtitle exceeds 8 MiB')
    subtitles = pysubs2.SSAFile.from_string(text.lstrip('\ufeff'), format_=extension)
    if not subtitles or len(subtitles) > MAX_CUES:
        raise ValueError('Subtitle must contain 1–20000 cues')
    cues = [dict(id=uid(), start_ms=int(c.start), end_ms=int(c.end), text=c.plaintext)
            for c in subtitles if not c.is_comment]
    validate(cues)
    return cues


def validate(cues):
    if len(cues) > MAX_CUES or len({c['id'] for c in cues}) != len(cues):
        raise ValueError('Too many cues or duplicate IDs')
    for c in cues:
        if not 0 <= c['start_ms'] < c['end_ms'] <= 604800000:
            raise ValueError('Each cue needs 0 ≤ start < end ≤ 7 days')
        if len(c['text']) > 10000 or '\x00' in c['text']:
            raise ValueError('Invalid cue text')


def export(cues, format_):
    # Write literal text ourselves: ASS braces and HTML never become instructions/styles.
    def clock(ms):
        h, rest = divmod(ms, 3600000)
        m, rest = divmod(rest, 60000)
        s, milli = divmod(rest, 1000)
        return f'{h:02}:{m:02}:{s:02}{"," if format_ == "srt" else "."}{milli:03}'
    blocks = []
    for i, c in enumerate(cues, 1):
        text = c['text'].replace('\r\n', '\n').replace('\r', '\n')
        # Escape VTT markup while retaining displayed text.
        if format_ == 'vtt':
            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        blocks.append(f'{i}\n{clock(c["start_ms"])} --> {clock(c["end_ms"])}\n{text}')
    return ('WEBVTT\n\n' if format_ == 'vtt' else '') + '\n\n'.join(blocks) + '\n'
