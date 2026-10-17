import {useEffect, useRef, useState} from 'react';

export type Tool = 'media'|'subtitles'|'translation'|'voice'|'review'|'effects'|'export';
export const tools: {id:Tool;label:string;icon:string}[] = [
  {id:'media',label:'Phương tiện',icon:'media'}, {id:'subtitles',label:'Phụ đề',icon:'captions'},
  {id:'translation',label:'Dịch thuật',icon:'languages'}, {id:'voice',label:'Giọng đọc',icon:'wave'},
  {id:'review',label:'Review',icon:'script'}, {id:'effects',label:'Hiệu ứng',icon:'sparkles'},
  {id:'export',label:'Xuất file',icon:'export'},
];
const paths:Record<string,string>={
  moon:'M20.5 13a8.5 8.5 0 0 1-9.5-9.5A8.5 8.5 0 1 0 20.5 13z',
  sun:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2 M12 20v2 M2 12h2 M20 12h2 M5 5l1.5 1.5 M17.5 17.5L19 19 M5 19l1.5-1.5 M17.5 6.5L19 5',
  trash:'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
  media:'M3 5h18v14H3z M8 5v14 M16 5v14 M3 10h5 M3 14h5 M16 10h5 M16 14h5',
  captions:'M3 5h18v14H3z M6 10h4 M6 14h6 M14 10h4 M15 14h3',
  languages:'M3 5h12 M9 3v2 M5 8c2 5 6 7 9 8 M13 5c-1 6-5 10-10 12 M13 21l4-10 4 10 M15 17h4',
  wave:'M3 10v4 M7 6v12 M11 3v18 M15 7v10 M19 5v14 M23 10v4',
  script:'M5 3h14v18H5z M9 7h6 M9 11h6 M9 15h4',
  sparkles:'M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z M20 2v4 M18 4h4',
  export:'M12 16V3 M7 8l5-5 5 5 M4 14v6h16v-6',
  plus:'M12 5v14 M5 12h14', folder:'M3 7h7l2-3h9v16H3z',
  play:'M8 4l12 8-12 8z', pause:'M8 5v14 M16 5v14',
  undo:'M8 4L3 9l5 5 M3 9h10a7 7 0 0 1 7 7', redo:'M16 4l5 5-5 5 M21 9H11a7 7 0 0 0-7 7',
  settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',
  expand:'M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5',
  check:'M5 12l4 4L19 6', chevron:'M9 5l7 7-7 7', cloud:'M7 18a5 5 0 1 1 0-10 6 6 0 0 1 11 0 5 5 0 0 1-1 10 M12 11v10 M8 17l4 4 4-4',
  cursor:'M5 3l14 10-7 1-3 7z', volume:'M3 9h4l5-4v14l-5-4H3z M16 8a6 6 0 0 1 0 8',
};
export function Icon({name,size=20}:{name:string;size?:number}){
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]||paths.media}/></svg>;
}
export function timecode(seconds:number){
  const ms=Math.max(0,Math.round(seconds*1000));
  return `${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
}

export function Timeline({video,cues,duration,filename,onSeek}:{video:React.RefObject<HTMLVideoElement|null>;cues:{id:string;start_ms:number;end_ms:number;text:string}[];duration:number;filename?:string;onSeek:(time:number)=>void}){
  const [zoom,setZoom]=useState(1),[playing,setPlaying]=useState(false);
  const clock=useRef<HTMLSpanElement>(null),needle=useRef<HTMLDivElement>(null),range=useRef<HTMLInputElement>(null);
  const end=Math.max(duration,...cues.map(c=>c.end_ms/1000),10);
  useEffect(()=>{
    const player=video.current;if(!player)return;
    const update=()=>{const time=player.currentTime;if(clock.current)clock.current.textContent=timecode(time);if(needle.current)needle.current.style.left=`${time/end*100}%`;if(range.current)range.current.value=String(time);};
    const play=()=>setPlaying(true),pause=()=>setPlaying(false);
    player.addEventListener('timeupdate',update);player.addEventListener('play',play);player.addEventListener('pause',pause);update();setPlaying(!player.paused);
    return()=>{player.removeEventListener('timeupdate',update);player.removeEventListener('play',play);player.removeEventListener('pause',pause);setPlaying(false);};
  },[video,filename,end]);
  return <section className="timeline-panel" aria-label="Timeline nguồn"><div className="timeline-toolbar"><div><Icon name="cursor" size={16}/><strong>Timeline nguồn</strong><span className="muted">Video & phụ đề</span></div><div className="transport"><button className="icon-button play-button" disabled={!filename} aria-label={playing?'Tạm dừng':'Phát video'} onClick={()=>{if(!video.current)return;if(video.current.paused)video.current.play().catch(()=>{});else video.current.pause();}}><Icon name={playing?'pause':'play'} size={15}/></button><span ref={clock}>00:00.000</span><span className="muted">/ {timecode(duration)}</span></div><div className="zoom-controls" role="group" aria-label="Thu phóng timeline"><button type="button" className="icon-button zoom-step" aria-label="Thu nhỏ timeline" title="Thu nhỏ timeline" disabled={zoom<=1} onClick={()=>setZoom(v=>Math.max(1,v-.5))}>−</button><label className="zoom-label"><span className="zoom-caption">Thu phóng</span><input aria-label="Thu phóng timeline" type="range" min="1" max="5" step=".5" value={zoom} onChange={e=>setZoom(Number(e.target.value))}/><span className="zoom-value">{zoom*100}%</span></label><button type="button" className="icon-button zoom-step" aria-label="Phóng to timeline" title="Phóng to timeline" disabled={zoom>=5} onClick={()=>setZoom(v=>Math.min(5,v+.5))}>+</button></div></div>
  <div className="timeline-body"><div className="track-labels"><span>Thời gian</span><span><Icon name="media" size={15}/> Video</span><span><Icon name="captions" size={15}/> Phụ đề</span></div><div className="timeline-scroll"><div className="timeline-content" style={{width:`${zoom*100}%`}}><div className="ruler">{Array.from({length:11},(_,i)=><span key={i}>{timecode(end*i/10).slice(0,5)}</span>)}</div><input ref={range} className="timeline-seek" type="range" aria-label="Vị trí phát" min="0" max={end} step=".01" defaultValue="0" disabled={!filename} onChange={e=>onSeek(Number(e.target.value))}/><div className="timeline-lane">{filename?<button className="video-clip" style={{width:`${duration/end*100}%`}} onClick={()=>onSeek(0)}><Icon name="media" size={14}/>{filename}</button>:<span className="lane-hint">Nhập video để bắt đầu câu chuyện của bạn</span>}</div><div className="timeline-lane subtitles-lane">{cues.length?cues.map(c=><button key={c.id} title={c.text} aria-label={`Đến phụ đề: ${c.text}`} className="subtitle-clip" style={{left:`${c.start_ms/1000/end*100}%`,width:`${(c.end_ms-c.start_ms)/1000/end*100}%`}} onClick={()=>onSeek(c.start_ms/1000)}>{c.text}</button>):<span className="lane-hint">Phụ đề đã nhập sẽ xuất hiện đúng mốc thời gian</span>}</div><div ref={needle} className="playhead"/></div></div></div></section>;
}

export function ToolInfo({tool,onConfigure}:{tool:Tool;onConfigure:()=>void}){
  const content:Record<string,{title:string;description:string;items:string[]}>={
    translation:{title:'Dịch đa ngôn ngữ',description:'Không gian dành cho bản dịch, thuật ngữ và các ngôn ngữ đích. Dịch tự động chưa khả dụng trong bản hiện tại.',items:['Giữ nguyên phụ đề gốc','Duyệt bản dịch theo từng câu','Từ điển tên riêng & cách xưng hô']},
    voice:{title:'Giọng kể cho câu chuyện',description:'Chọn giọng, nghe mẫu và gán người nói sẽ xuất hiện tại đây khi tích hợp TTS hoàn tất. Hiện chưa có giọng hoặc mẫu nghe được kết nối.',items:['Giọng đọc theo ngôn ngữ','Nghe thử trước khi tạo','Gán giọng theo nhân vật']},
    review:{title:'Từ bộ phim đến góc nhìn riêng',description:'Dự án hỗ trợ lựa chọn review tóm tắt. Soạn kịch bản AI và dựng review chưa khả dụng; video và phụ đề gốc vẫn có thể biên tập ở các bảng bên cạnh.',items:['Kịch bản & lời bình','Liên kết cảnh nguồn','Duyệt trước khi tạo giọng']},
    effects:{title:'Hoàn thiện từng khung hình',description:'Bộ công cụ hiệu ứng, chuyển cảnh và chỉnh màu chưa khả dụng. Tỷ lệ khung hình hiện chỉ thay đổi cách xem preview.',items:['Chữ, tiêu đề & lớp phủ','Màu sắc & chuyển cảnh','Âm lượng & phối âm']},
  };
  const data=content[tool];if(!data)return null;
  return <section className="tool-info"><span className="tool-info-icon"><Icon name={tools.find(t=>t.id===tool)?.icon||'sparkles'} size={28}/></span><span className="availability">Chưa khả dụng</span><h2>{data.title}</h2><p>{data.description}</p><ul>{data.items.map(item=><li key={item}><span/>{item}</li>)}</ul>{tool==='translation'||tool==='voice'?<button onClick={onConfigure}><Icon name="settings" size={16}/> Cấu hình provider</button>:null}</section>;
}
