import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import logoUrl from '../../assets/logo.svg';
import wordmarkUrl from '../../assets/wordmark.svg';
import bannerUrl from '../../assets/banner.svg';
import {Icon, Timeline, ToolInfo, tools, type Tool} from './StudioParts';

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
  const [tool,setTool]=useState<Tool>('media'),[showCreate,setShowCreate]=useState(true),[aspect,setAspect]=useState('16/9'),[activeAssetId,setActiveAssetId]=useState('');
  const [trackId,setTrackId]=useState(''),[cues,setCues]=useState<Cue[]>([]);
  const [status,setStatus]=useState('Sẵn sàng'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [conflict,setConflict]=useState(false);
  const [dirty,setDirty]=useState(false),[history,setHistory]=useState<Cue[][]>([]),[future,setFuture]=useState<Cue[][]>([]);
  const [name,setName]=useState(''),[mode,setMode]=useState('full'),[target,setTarget]=useState('vi');
  const video=useRef<HTMLVideoElement>(null),saving=useRef(false),generation=useRef(0);
  const projectRef=useRef(project); projectRef.current=project;
  const selected=project?.tracks.find(t=>t.id===trackId);
  const refreshLibrary=()=>api<Project[]>('/api/projects').then(setLibrary);
  useEffect(()=>{refreshLibrary().catch(e=>setError(e.message));},[]);
  function load(p:Project){setProject(p);setActiveAssetId('');const t=p.tracks[0];setTrackId(t?.id||'');setCues(t?.cues||[]);setDirty(false);setHistory([]);setFuture([]);setError('');setConflict(false);setStatus('Đã mở dự án');}
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
    }catch(e){setError(String(e));setConflict(String(e).includes('Project changed elsewhere'));setStatus('Chưa lưu được — hãy kiểm tra và lưu lại');}
    finally{saving.current=false;}
  }
  useEffect(()=>{if(!dirty)return;const timer=setTimeout(()=>{void save();},700);return()=>clearTimeout(timer);},[cues,dirty,project?.revision]);
  useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(dirty||saving.current){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[dirty]);
  function change(next:Cue[]){setHistory(h=>[...h.slice(-49),cues]);setFuture([]);setCues(next);generation.current++;setDirty(true);setStatus('Có thay đổi');}
  function undo(){if(!history.length)return;setFuture(f=>[...f,cues]);setCues(history[history.length-1]);setHistory(h=>h.slice(0,-1));generation.current++;setDirty(true);}
  function redo(){if(!future.length)return;setHistory(h=>[...h,cues]);setCues(future[future.length-1]);setFuture(f=>f.slice(0,-1));generation.current++;setDirty(true);}
  async function upload(file:File,kind:string){
    setBusy(true);setError('');
    try{
      let destination=project;
      if(!destination){destination=await api<Project>('/api/projects',{method:'POST',...json({name:file.name.replace(/\.[^.]+$/,''),mode,target_language:target})});await refreshLibrary();}
      const body=new FormData();body.append('file',file);body.append('kind',kind);
      await api(`/api/projects/${destination.id}/upload`,{method:'POST',body});
      load(await api<Project>('/api/projects/'+destination.id));setShowCreate(false);
      setStatus(kind==='media'?'Đã nhập, đang chờ worker kiểm tra':'Đã nhập phụ đề');
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }

  const availableMedia=project?.assets?.filter(a=>a.kind==='media'&&a.metadata)||[];
  const media=availableMedia.find(a=>a.id===activeAssetId)||availableMedia[0];
  const mediaMeta=media?.metadata?JSON.parse(media.metadata):null;
  const duration=Number(mediaMeta?.format?.duration||0);
  function seek(seconds:number){if(video.current)video.current.currentTime=seconds;}
  function configure(){const settings=document.querySelector<HTMLDetailsElement>('.provider-settings');if(settings){settings.open=true;settings.scrollIntoView({behavior:'smooth',block:'nearest'});}}
  const uploadInput=(kind:'media'|'subtitle')=><input type="file" accept={kind==='subtitle'?'.srt,.vtt,.ass':undefined} aria-label={kind==='media'?'Nhập video hoặc audio':'Nhập phụ đề'} disabled={busy||dirty} onChange={e=>{if(e.target.files?.[0])void upload(e.target.files[0],kind);e.target.value='';}}/>;
  return <div className="studio">
    <header className="appbar">
      <a className="brand" href="/" aria-label="DubiSub Studio"><img className="brand-wordmark" src={wordmarkUrl} alt="DubiSub"/><small>studio</small></a>
      <div className="project-heading"><Icon name="folder" size={17}/><h1>{project?.name||'Dự án chưa đặt tên'}</h1><span className="project-state">{project?'Lưu cục bộ':'Không gian sáng tạo của bạn'}</span></div>
      <div className="header-actions"><span className="badge"><i/> AI chưa kết nối</span><button className="icon-button" aria-label="Cấu hình studio" onClick={configure}><Icon name="settings"/></button><button className="primary" onClick={()=>{setTool('export');document.querySelector('.export-panel')?.scrollIntoView({behavior:'smooth',block:'nearest'});}}><Icon name="export" size={16}/> Xuất phụ đề</button></div>
    </header>
    <nav className="toolrail" aria-label="Công cụ studio">{tools.map(t=><button key={t.id} aria-pressed={tool===t.id} className={tool===t.id?'selected':''} onClick={()=>setTool(t.id)}><Icon name={t.icon} size={23}/><span>{t.label}</span></button>)}<button className="rail-settings" aria-label="Mở cấu hình provider" onClick={configure}><Icon name="settings"/><span>Cài đặt</span></button></nav>
    <aside className="library-panel">
      <div className="panel-heading"><h2>Kho dự án</h2><span className="count">{library.length}</span></div>
      <button className="new-project" onClick={()=>setShowCreate(v=>!v)} aria-expanded={showCreate}><Icon name="plus" size={17}/> Dự án mới</button>
      {showCreate?<section className="create"><h2>Tạo dự án</h2><form onSubmit={async e=>{e.preventDefault();setBusy(true);try{const p=await api<Project>('/api/projects',{method:'POST',...json({name,mode,target_language:target})});load(p);await refreshLibrary();setName('');setShowCreate(false);}catch(e){setError(String(e));}finally{setBusy(false);}}}>
        <label>Tên dự án<input required maxLength={160} value={name} onChange={e=>setName(e.target.value)} placeholder="Câu chuyện tiếp theo…"/></label>
        <label>Chế độ<select aria-label="Chế độ" value={mode} onChange={e=>setMode(e.target.value)}><option value="full">Dịch / lồng tiếng toàn bộ</option><option value="review">Review tóm tắt</option></select></label>
        <label>Ngôn ngữ đích (BCP 47)<input value={target} onChange={e=>setTarget(e.target.value)} required aria-describedby="language-help"/></label><button className="primary" disabled={busy||dirty} type="submit">Tạo dự án</button>
      </form><small id="language-help">Mặc định tiếng Việt (vi). English: en.</small></section>:null}
      <nav className="project-list" aria-label="Dự án">{library.length?library.map(p=><button key={p.id} disabled={dirty||busy} className={project?.id===p.id?'active':''} onClick={()=>{void open(p.id);setShowCreate(false);}}><span className="project-icon"><Icon name="folder" size={17}/></span><span>{p.name}<small>{p.mode==='review'?'Review tóm tắt':'Dịch / lồng tiếng'}</small></span></button>):<p className="muted library-empty">Tất cả dự án của bạn sẽ ở đây.</p>}</nav>
      <div className="panel-heading media-heading"><h2>Phương tiện</h2><span className="count">{project?.assets?.length||0}</span></div>
      <label className="file media-upload"><Icon name="cloud" size={24}/><strong>Nhập video hoặc audio</strong><span>Kéo thả hoặc chọn từ máy</span>{uploadInput('media')}</label>
      <div className="asset-list">{project?.assets?.map(a=><button key={a.id} className={media?.id===a.id?'asset active':'asset'} disabled={a.kind!=='media'||!a.metadata} onClick={()=>setActiveAssetId(a.id)}><span className="asset-icon"><Icon name={a.kind==='media'?'media':'captions'} size={19}/></span><span>{a.filename}<small>{a.kind==='subtitle'?'Phụ đề nguồn':a.metadata?`${Number(JSON.parse(a.metadata).format?.duration||0).toFixed(1)} giây`:'Đang kiểm tra…'}</small></span></button>)}</div>
      <div className="jobs">{project?.jobs?.map(j=><div key={j.id}><span className={'job-dot '+j.state}/><strong>Kiểm tra media</strong><small>{j.state} · {j.progress}%</small>{j.error?<p role="alert">{j.error}</p>:null}{['queued','running'].includes(j.state)?<button onClick={()=>api(`/api/jobs/${j.id}/cancel`,{method:'POST'}).then(()=>open(project!.id)).catch(e=>setError(String(e)))}>Hủy</button>:null}{['failed','canceled'].includes(j.state)?<button onClick={()=>api(`/api/jobs/${j.id}/retry`,{method:'POST'}).then(()=>open(project!.id)).catch(e=>setError(String(e)))}>Thử lại</button>:null}</div>)}</div>
      <ProviderSettings/>
      <div className="storage-note"><img src={logoUrl} width="25" height="25" alt=""/><span>Media gốc luôn được giữ nguyên.<small>Dữ liệu lưu trên máy của bạn.</small></span></div>
    </aside>
    <main className="stage">
      <div className="stage-topbar"><div><span className="live-dot"/> Preview <span className="stage-project-mode">{project?.mode==='review'?'Review tóm tắt':'Dịch & biên tập'}</span></div><div><label className="aspect-picker"><span>Tỷ lệ xem</span><select aria-label="Tỷ lệ preview" value={aspect} onChange={e=>setAspect(e.target.value)}><option value="16/9">16:9</option><option value="9/16">9:16</option><option value="1/1">1:1</option></select></label><button className="icon-button" disabled={!media} aria-label="Toàn màn hình video" onClick={()=>video.current?.requestFullscreen().catch(e=>setError(String(e)))}><Icon name="expand" size={17}/></button></div></div>
      <div className="preview-canvas" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!busy&&!dirty&&e.dataTransfer.files[0])void upload(e.dataTransfer.files[0],'media');}}>
        <div className={'preview-frame '+(!media?'no-media':'')} style={{aspectRatio:aspect}}>
        {media&&project?<video key={media.id} ref={video} controls onError={()=>setStatus('Trình duyệt chưa hỗ trợ định dạng này. Bạn vẫn có thể sửa và xuất phụ đề.')} src={`/api/projects/${project.id}/assets/${media.id}/content`}>{selected?<track key={`${selected.id}-${project.revision}`} kind="subtitles" label="Phụ đề nguồn" srcLang={selected.language} src={`/api/projects/${project.id}/tracks/${selected.id}/export?format=vtt&revision=${project.revision}`} default/>:null}</video>:<div className="canvas-empty"><img className="studio-banner" src={bannerUrl} alt="DubiSub — Translate. Dub. Create."/><h2>Không gian cho câu chuyện tiếp theo.</h2><p>Thả video vào đây để bắt đầu.<br/>Không gian biên tập đã sẵn sàng.</p><button className="canvas-import" onClick={()=>document.querySelector<HTMLInputElement>('.media-upload input')?.click()}><Icon name="plus" size={17}/> Nhập phương tiện</button><span className="canvas-footnote">Video · Audio · Phụ đề đa ngôn ngữ</span></div>}
        </div>
      </div>
      <div className="stage-bottom"><span>{media?.filename||'Chưa có phương tiện'}{mediaMeta?` · ${mediaMeta.streams?.find((s:{codec_type:string})=>s.codec_type==='video')?.width||'Audio'}${mediaMeta.streams?.find((s:{codec_type:string})=>s.codec_type==='video')?.height?` × ${mediaMeta.streams.find((s:{codec_type:string})=>s.codec_type==='video').height}`:''}`:''}</span><span>Preview từ nguồn gốc</span></div>
      <div className="capability-strip">{[{id:'subtitles',name:'Phụ đề',text:'Sửa & xuất SRT/VTT',icon:'captions'},{id:'translation',name:'Dịch thuật',text:'Chưa khả dụng',icon:'languages'},{id:'voice',name:'Giọng đọc',text:'Chưa khả dụng',icon:'wave'},{id:'review',name:'Review',text:'Chưa khả dụng',icon:'script'}].map(t=><button key={t.id} className={tool===t.id?'active':''} onClick={()=>setTool(t.id as Tool)}><Icon name={t.icon} size={19}/><span>{t.name}<small>{t.text}</small></span></button>)}</div>
    </main>
    <aside className="inspector">
      {tool!=='media'&&tool!=='subtitles'&&tool!=='export'?<ToolInfo tool={tool} onConfigure={configure}/>:null}
      <section className="editor"><div className="panel-heading"><h2>Phụ đề nguồn</h2><span className="count">{cues.length} câu</span></div><label className="file subtitle-upload"><Icon name="plus" size={16}/><span>Nhập SRT / VTT / ASS</span>{uploadInput('subtitle')}</label>
      {project?.tracks.length?<><label className="track-select">Track<select aria-label="Track phụ đề" value={trackId} disabled={dirty} onChange={e=>{const t=project.tracks.find(t=>t.id===e.target.value)!;setTrackId(t.id);setCues(t.cues);setHistory([]);setFuture([]);}}>{project.tracks.map((t,i)=><option key={t.id} value={t.id}>Track {i+1} · {t.language} · {t.cues.length} câu</option>)}</select></label><div className="toolbar"><button disabled={!history.length} onClick={undo} aria-label="Hoàn tác" title="Hoàn tác"><Icon name="undo" size={16}/></button><button disabled={!future.length} onClick={redo} aria-label="Làm lại" title="Làm lại"><Icon name="redo" size={16}/></button><button onClick={()=>void save()} disabled={!dirty}><Icon name="check" size={15}/> Lưu ngay</button><span>{dirty?'Chưa lưu':'Đã lưu'}</span></div>
      <div className="cues">{cues.map((c,i)=><article key={c.id}><button className="seek" aria-label={`Tới câu ${i+1}`} onClick={()=>seek(c.start_ms/1000)}>{String(i+1).padStart(2,'0')}</button><div className="cue-body"><div className="times"><label>Bắt đầu (ms)<input type="number" min="0" value={c.start_ms} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,start_ms:Number(e.target.value)}:x))}/></label><span className="time-divider">—</span><label>Kết thúc (ms)<input type="number" min="1" value={c.end_ms} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,end_ms:Number(e.target.value)}:x))}/></label></div><label className="text-label">Câu {i+1}<textarea aria-label={`Câu ${i+1}`} dir="auto" value={c.text} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,text:e.target.value}:x))}/></label>{c.end_ms<=c.start_ms?<p className="error">Kết thúc phải sau bắt đầu.</p>:null}</div></article>)}</div><small className="editor-note">Tự lưu sau khi sửa. ASS chuyển thành chữ thuần.</small></>:<div className="subtitle-empty"><div className="subtitle-lines"><span/><span/><span/></div><h3>Lời thoại nằm ở đây</h3><p>Nhập phụ đề hoặc trích track chữ từ video để sửa từng câu.</p><span>Hỗ trợ tiếng Việt, CJK & RTL</span></div>}
      </section>
      <section className={'export-panel '+(tool==='export'?'highlighted':'')}><div className="panel-heading"><h2>Xuất phụ đề</h2><Icon name="export" size={17}/></div><p>Bản phụ đề của bạn, sẵn sàng mang đi.</p><div className="export-options">{['srt','vtt'].map(f=>project&&selected?<a key={f} aria-disabled={dirty} onClick={e=>{if(dirty)e.preventDefault();}} href={`/api/projects/${project.id}/tracks/${trackId}/export?format=${f}`} download><Icon name="export" size={15}/> Xuất {f.toUpperCase()}</a>:<button key={f} disabled><Icon name="export" size={15}/> Xuất {f.toUpperCase()}</button>)}</div><small>{selected?(dirty?'Đợi tự lưu trước khi xuất.':'Xuất trực tiếp, không cần dựng video.'):'Nhập phụ đề để mở xuất SRT/VTT.'}</small><small className="video-export-note">Xuất video & lồng tiếng chưa khả dụng.</small></section>
    </aside>
    <Timeline key={media?.id||'empty'} video={video} cues={cues} duration={duration} filename={media?.filename} onSeek={seek}/>
    <div className="appstatus"><span className="save-indicator"><i className={dirty?'unsaved':''}/><span role="status">{busy?'Đang nhập file…':status}</span></span><span className="status-right">DubiSub Studio <span>•</span> Cục bộ <span>•</span> {project?.target_language||target}</span></div>
    {error?<div className="error-toast" role="alert"><div><strong>Không thể hoàn tất thao tác</strong><button className="icon-button" aria-label="Đóng thông báo" onClick={()=>setError('')}>×</button></div><p>{error}</p>{conflict?<><p>Tải bản sửa dự phòng trước khi mở phiên bản mới.</p><button onClick={()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema_version:1,project_id:project?.id,track_id:trackId,cues},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='dubisub-unsaved-cues.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Tải bản sửa dự phòng</button><button onClick={async()=>{if(project)load(await api<Project>('/api/projects/'+project.id));}}>Mở phiên bản mới</button></>:null}</div>:null}
  </div>;
}

createRoot(document.getElementById('root')!).render(<App/>);
