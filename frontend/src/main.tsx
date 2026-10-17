import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type Cue = {id:string;start_ms:number;end_ms:number;text:string};
type Track = {id:string;language:string;cues:Cue[]};
type Project = {id:string;name:string;mode:string;target_language:string;revision:number;tracks:Track[];assets?:{id:string;filename:string;kind:string;metadata:string|null}[];jobs?:{id:string;kind:string;state:string;progress:number;error:string|null}[]};
async function api<T>(path:string, options?:RequestInit):Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
const json = (value:unknown) => ({headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});

type Provider={kind:string;endpoint:string;model:string;key_env:string};
function ProviderSettings(){
  const [providers,setProviders]=useState<Provider[]>([]),[message,setMessage]=useState('');
  const [kind,setKind]=useState('translation'),[endpoint,setEndpoint]=useState(''),[model,setModel]=useState(''),[keyEnv,setKeyEnv]=useState('');
  useEffect(()=>{api<{providers:Provider[]}>('/api/settings').then(s=>setProviders(s.providers)).catch(e=>setMessage(String(e)));},[]);
  return <details className="provider-settings"><summary>Cấu hình AI · chưa xác minh kết nối</summary><p>M1 chỉ lưu cấu hình. Chưa có lời gọi ASR, dịch hoặc TTS. Khóa được đặt qua biến môi trường riêng của DubiSub.</p>{providers.map(p=><p key={p.kind}>{p.kind}: {p.endpoint} · {p.model||'Chưa chọn model'} · chưa xác minh</p>)}<form onSubmit={async e=>{e.preventDefault();try{const next=[...providers.filter(p=>p.kind!==kind),{kind,endpoint,model,key_env:keyEnv}];const saved=await api<{providers:Provider[]}>('/api/settings',{method:'PUT',...json({providers:next})});setProviders(saved.providers);setMessage('Đã lưu cấu hình; chưa kiểm tra provider.');}catch(e){setMessage(String(e));}}}><label>Loại provider<select value={kind} onChange={e=>setKind(e.target.value)}><option value="translation">Dịch</option><option value="asr">ASR</option><option value="tts">TTS</option></select></label><label>Endpoint<input type="url" required value={endpoint} onChange={e=>setEndpoint(e.target.value)}/></label><label>Model<input value={model} onChange={e=>setModel(e.target.value)}/></label><label>Tên biến môi trường khóa<input placeholder="DUBISUB_LLM_API_KEY" value={keyEnv} onChange={e=>setKeyEnv(e.target.value)}/></label><button>Lưu cấu hình</button></form><p role="status">{message}</p></details>;
}

function App(){
  const [library,setLibrary]=useState<Project[]>([]), [project,setProject]=useState<Project|null>(null);
  const [trackId,setTrackId]=useState(''),[cues,setCues]=useState<Cue[]>([]);
  const [status,setStatus]=useState('Sẵn sàng'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [dirty,setDirty]=useState(false),[history,setHistory]=useState<Cue[][]>([]),[future,setFuture]=useState<Cue[][]>([]);
  const [name,setName]=useState(''),[mode,setMode]=useState('full'),[target,setTarget]=useState('vi');
  const video=useRef<HTMLVideoElement>(null),saving=useRef(false),generation=useRef(0);
  const projectRef=useRef(project); projectRef.current=project;
  const selected=project?.tracks.find(t=>t.id===trackId);
  const refreshLibrary=()=>api<Project[]>('/api/projects').then(setLibrary);
  useEffect(()=>{refreshLibrary().catch(e=>setError(e.message));},[]);
  function load(p:Project){setProject(p);const t=p.tracks[0];setTrackId(t?.id||'');setCues(t?.cues||[]);setDirty(false);setHistory([]);setFuture([]);setError('');setStatus('Đã mở dự án');}
  async function open(id:string){if(dirty||saving.current)return;try{load(await api<Project>('/api/projects/'+id));}catch(e){setError(String(e));}}
  useEffect(()=>{
    if(!project)return;
    const timer=setInterval(async()=>{
      if(dirty||saving.current)return;
      const version=generation.current;
      try{const p=await api<Project>('/api/projects/'+project.id);
        if(projectRef.current?.id!==p.id||saving.current||generation.current!==version)return;
        if(trackId&&p.revision!==projectRef.current?.revision){
          const changed=p.tracks.find(t=>t.id===trackId);
          if(changed){setCues(changed.cues);setHistory([]);setFuture([]);}
        }
        setProject(p);
        if(!trackId&&p.tracks[0]){setTrackId(p.tracks[0].id);setCues(p.tracks[0].cues);}
      }catch(e){setError(String(e));}
    },1500);return()=>clearInterval(timer);
  },[project?.id,dirty,trackId]);
  async function save(){
    if(!project||!selected||saving.current)return;
    saving.current=true;const version=generation.current;setStatus('Đang lưu…');
    try{const p=await api<Project>(`/api/projects/${project.id}/tracks/${trackId}`,{method:'PUT',...json({revision:project.revision,cues})});
      setProject(old=>old?{...old,...p}:p);
      if(generation.current===version){setDirty(false);setStatus('Đã tự lưu');}
      setError('');
    }catch(e){setError(String(e));setStatus('Chưa lưu được — hãy kiểm tra và lưu lại');}
    finally{saving.current=false;}
  }
  useEffect(()=>{if(!dirty)return;const timer=setTimeout(()=>{void save();},700);return()=>clearTimeout(timer);},[cues,dirty,project?.revision]);
  useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(dirty||saving.current){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[dirty]);
  function change(next:Cue[]){setHistory(h=>[...h.slice(-49),cues]);setFuture([]);setCues(next);generation.current++;setDirty(true);setStatus('Có thay đổi');}
  function undo(){if(!history.length)return;setFuture(f=>[...f,cues]);setCues(history[history.length-1]);setHistory(h=>h.slice(0,-1));generation.current++;setDirty(true);}
  function redo(){if(!future.length)return;setHistory(h=>[...h,cues]);setCues(future[future.length-1]);setFuture(f=>f.slice(0,-1));generation.current++;setDirty(true);}
  async function upload(file:File,kind:string){if(!project)return;setBusy(true);setError('');try{const body=new FormData();body.append('file',file);body.append('kind',kind);await api(`/api/projects/${project.id}/upload`,{method:'POST',body});load(await api<Project>('/api/projects/'+project.id));setStatus(kind==='media'?'Đã nhập, đang chờ worker kiểm tra':'Đã nhập phụ đề');}catch(e){setError(String(e));}finally{setBusy(false);}}
  const media=project?.assets?.find(a=>a.kind==='media'&&a.metadata);
  return <div className="shell"><aside><a className="brand" href="/">Dubi<span>Sub</span><small>Video & subtitle studio</small></a><h2>Thư viện</h2><nav aria-label="Dự án">{library.map(p=><button key={p.id} disabled={dirty||busy} className={project?.id===p.id?'active':''} onClick={()=>open(p.id)}>{p.name}<small>{p.mode==='review'?'Review tóm tắt':'Dịch / lồng tiếng'}</small></button>)}</nav><p className="local">Lưu trên máy của bạn<br/>M1 · Nền tảng phụ đề</p></aside>
  <main><header><div><p className="eyebrow">Không gian làm việc</p><h1>{project?.name||'Mỗi câu chữ, một câu chuyện.'}</h1></div><span className="badge">AI chưa cấu hình</span></header>
  <section className="create"><h2>Tạo dự án</h2><form onSubmit={async e=>{e.preventDefault();setBusy(true);try{const p=await api<Project>('/api/projects',{method:'POST',...json({name,mode,target_language:target})});load(p);await refreshLibrary();setName('');}catch(e){setError(String(e));}finally{setBusy(false);}}}>
  <label>Tên dự án<input required maxLength={160} value={name} onChange={e=>setName(e.target.value)} placeholder="Ví dụ: Chuyến đi đầu tiên"/></label>
  <label>Chế độ<select aria-label="Chế độ" value={mode} onChange={e=>setMode(e.target.value)}><option value="full">Dịch / lồng tiếng toàn bộ</option><option value="review">Review tóm tắt</option></select></label>
  <label>Ngôn ngữ đích (BCP 47)<input value={target} onChange={e=>setTarget(e.target.value)} required aria-describedby="language-help"/></label><button className="primary" disabled={busy||dirty} type="submit">Tạo dự án</button></form><small id="language-help">Tiếng Việt: vi · English: en. Chế độ và đích được lưu; dịch, review và giọng đọc thuộc các mốc sau.</small></section>
  {error?<p className="error" role="alert">{error}</p>:null}<p className="status" role="status">{busy?'Đang nhập file…':status}</p>
  {project?<><div className="workspace"><section className="preview"><div className="section-head"><h2>Nguồn video</h2><span>Giữ nguyên bản gốc</span></div>{media?<video ref={video} controls onError={()=>setStatus("Trình duyệt không phát được định dạng này. Vẫn có thể sửa và xuất phụ đề; proxy sẽ có ở M4.")} src={`/api/projects/${project.id}/assets/${media.id}/content`}>{selected?<track key={`${selected.id}-${project.revision}`} kind="subtitles" label="Phụ đề nguồn" srcLang={selected.language} src={`/api/projects/${project.id}/tracks/${selected.id}/export?format=vtt&revision=${project.revision}`} default/>:null}</video>:<div className="empty"><span className="film">▤</span><h3>Nhập cảnh quay của bạn</h3><p>Video được kiểm tra bằng FFprobe.<br/>Chưa nhập link ở mốc này.</p></div>}
  <label className="file">Nhập video hoặc audio<input type="file" aria-label="Nhập video hoặc audio" disabled={busy||dirty} onChange={e=>{if(e.target.files?.[0])void upload(e.target.files[0],'media');e.target.value='';}}/></label>
  {project.assets?.filter(a=>a.metadata).map(a=>{const m=JSON.parse(a.metadata!);return <p className="metadata" key={a.id}>{a.filename} · {Number(m.format?.duration||0).toFixed(2)} giây · {m.streams?.length} track</p>;})}
  <div className="jobs">{project.jobs?.map(j=><div key={j.id}><strong>{j.kind}</strong> · {j.state} · {j.progress}% {j.error?<p role="alert">{j.error}</p>:null}{['queued','running'].includes(j.state)?<button onClick={async()=>{await api(`/api/jobs/${j.id}/cancel`,{method:'POST'});await open(project.id);}}>Hủy</button>:null}{['failed','canceled'].includes(j.state)?<button onClick={()=>api(`/api/jobs/${j.id}/retry`,{method:'POST'}).then(()=>open(project.id)).catch(e=>setError(String(e)))}>Thử lại</button>:null}</div>)}</div></section>
  <section className="editor"><div className="section-head"><h2>Phụ đề nguồn</h2><label className="file compact">Nhập SRT / VTT / ASS<input type="file" accept=".srt,.vtt,.ass" aria-label="Nhập phụ đề" disabled={busy||dirty} onChange={e=>{if(e.target.files?.[0])void upload(e.target.files[0],'subtitle');e.target.value='';}}/></label></div>
  {project.tracks.length?<><label>Track<select value={trackId} disabled={dirty} onChange={e=>{const t=project.tracks.find(t=>t.id===e.target.value)!;setTrackId(t.id);setCues(t.cues);setHistory([]);setFuture([]);}}>{project.tracks.map((t,i)=><option key={t.id} value={t.id}>Track {i+1} · {t.language} · {t.cues.length} câu</option>)}</select></label><div className="toolbar"><button disabled={!history.length} onClick={undo}>Hoàn tác</button><button disabled={!future.length} onClick={redo}>Làm lại</button><button onClick={()=>void save()} disabled={!dirty}>Lưu ngay</button><span>{cues.length} câu</span></div>
  <div className="cues">{cues.map((c,i)=><article key={c.id}><button className="seek" aria-label={`Tới câu ${i+1}`} onClick={()=>{if(video.current)video.current.currentTime=c.start_ms/1000;}}>{i+1}</button><div className="cue-body"><div className="times"><label>Bắt đầu (ms)<input type="number" min="0" value={c.start_ms} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,start_ms:Number(e.target.value)}:x))}/></label><label>Kết thúc (ms)<input type="number" min="1" value={c.end_ms} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,end_ms:Number(e.target.value)}:x))}/></label></div><label className="text-label">Câu {i+1}<textarea aria-label={`Câu ${i+1}`} dir="auto" value={c.text} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,text:e.target.value}:x))}/></label>{c.end_ms<=c.start_ms?<p className="error">Kết thúc phải sau bắt đầu.</p>:null}</div></article>)}</div>
  <footer><span>Xuất phụ đề đã chỉnh sửa</span>{['srt','vtt'].map(f=><a key={f} aria-disabled={dirty} onClick={e=>{if(dirty)e.preventDefault();}} href={`/api/projects/${project.id}/tracks/${trackId}/export?format=${f}`} download>Xuất {f.toUpperCase()}</a>)}</footer><small>ASS được nhập dạng chữ thuần; SRT/VTT không giữ hiệu ứng ASS. Phụ đề chưa được dịch tự động.</small></>:<div className="empty"><h3>Bắt đầu từ lời thoại</h3><p>Nhập phụ đề hoặc chờ trích track chữ trong video.<br/>ASR sẽ được bổ sung khi có provider.</p></div>}</section></div></>:<section className="welcome"><h2>Chọn một dự án hoặc tạo dự án đầu tiên.</h2><p>Nhập video, sửa từng câu và xuất phụ đề ngay trên máy.</p></section>}
  <ProviderSettings/></main></div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
