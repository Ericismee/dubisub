import {useEffect,useState,type RefObject} from 'react';
import type {SubtitleMask} from './RenderPanel';
export function MaskOverlay({video,mask,contentWidth,contentHeight}:{video:RefObject<HTMLVideoElement|null>;mask:SubtitleMask;contentWidth:number;contentHeight:number}){
 const [time,setTime]=useState(0);
 useEffect(()=>{const v=video.current;if(!v)return;const update=()=>setTime(v.currentTime*1000);update();v.addEventListener('timeupdate',update);v.addEventListener('seeked',update);return()=>{v.removeEventListener('timeupdate',update);v.removeEventListener('seeked',update);};},[video,mask]);
 const boxes=mask.mode==='tracked'?(mask.regions||[]).filter(r=>r.start_ms<=time&&r.end_ms>time):[mask];
 return <>{boxes.map((box,i)=><div key={i} className="subtitle-mask-preview" aria-label="Vùng làm mờ phụ đề cũ" style={{left:`${((1-contentWidth)/2+box.x*contentWidth)*100}%`,top:`${((1-contentHeight)/2+box.y*contentHeight)*100}%`,width:`${box.width*contentWidth*100}%`,height:`${box.height*contentHeight*100}%`,backdropFilter:`blur(${mask.strength}px)`}}/>)}</>;
}
