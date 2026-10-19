"""Time-limited white rectangles on a black alpha matte, in source pixels."""


def timestamp(ms):
    cs=round(ms/10)
    return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'


def write_ass(path,regions,plan):
    width=plan.get('source_width');height=plan.get('source_height')
    if type(width) is not int or type(height) is not int or not 1<=width<=16384 or not 1<=height<=16384:raise ValueError('Thiếu kích thước nguồn để áp dụng mask đúng tọa độ.')
    lines=[f'[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nScaledBorderAndShadow: yes\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Mask,Arial,12,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    for r in regions:
        start=max(r['start_ms'],plan['in_ms'])-plan['in_ms'];end=min(r['end_ms'],plan['out_ms'])-plan['in_ms']
        if end<=start:continue
        x=round(r['x']*width);y=round(r['y']*height);right=round((r['x']+r['width'])*width);bottom=round((r['y']+r['height'])*height)
        drawing=f'{{\\an7\\pos(0,0)\\p1\\bord0\\shad0}}m {x} {y} l {right} {y} {right} {bottom} {x} {bottom}'
        lines.append(f'Dialogue: 0,{timestamp(start)},{timestamp(end)},Mask,,0,0,0,,{drawing}')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
