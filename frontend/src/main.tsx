import {AnalysisPanel,type Analysis} from './AnalysisPanel';
import {AutoWizard} from './AutoWizard';
import {httpError} from './httpError';
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import {DubbingPanel,type Dubbing,type NarrationSettings} from './DubbingPanel';
import {VoicePanel} from './VoicePanel';
import {RenderPanel} from './RenderPanel';
import {WorkflowPanel} from './WorkflowPanel';
import {SubtitleTools} from './SubtitleTools';
import {SettingsDialog, type Theme} from './SettingsDialog';
import {ProjectLibrary} from './ProjectLibrary';
import {ProjectDialog} from './ProjectDialog';
import {LinkImport} from './LinkImport';
import logoUrl from '../../assets/logo.svg';
import logoDarkUrl from '../../assets/logo-dark.svg';
import wordmarkUrl from '../../assets/wordmark-compact.svg';
import wordmarkDarkUrl from '../../assets/wordmark-compact-dark.svg';
import bannerUrl from '../../assets/banner.svg';
import {Icon, Timeline, ToolInfo, tools, type Tool} from './StudioParts';

type Cue = {review_reasons?:string[];id:string;start_ms:number;end_ms:number;text:string};
type Track = {id:string;language:string;kind?:string;reviewed?:boolean;source_changed?:boolean;source_track_id?:string;cues:Cue[]};
type Project = {analyses?:Record<string,Analysis>;id:string;name:string;mode:string;target_language:string;revision:number;tracks:Track[];glossary?:Record<string,string>;voice_profiles?:Record<string,{name:string;start_ms:number;end_ms:number}>;dubbings?:Dubbing[];narration_settings?:Record<string,NarrationSettings>;voice_samples?:Record<string,{voice_id:string;language:string;text:string}>;artifacts?:{id:string;filename:string;size:number;source_revision:number}[];links?:{id:string;filename:string}[];assets?:{id:string;filename:string;kind:string;metadata:string|null}[];jobs?:{id:string;kind:string;state:string;progress:number;error:string|null}[]};
async function api<T>(path:string, options?:RequestInit):Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) throw await httpError(response);
  return response.json();
}
const json = (value:unknown) => ({headers:{'Content-Type':'application/json'},body:JSON.stringify(value)});

function App(){
  const [libraryOpen,setLibraryOpen]=useState(false),[autoOpen,setAutoOpen]=useState(false),[settingsTab,setSettingsTab]=useState('appearance');
  const [theme,setTheme]=useState<Theme>(()=>{try{return localStorage.getItem('dubisub.ui.v1.theme')==='light'?'light':'dark';}catch{return 'dark';}});
  const [customCursor,setCustomCursor]=useState(()=>{try{return localStorage.getItem('dubisub.ui.v1.cursor')!=='system';}catch{return true;}});
  const [settingsOpen,setSettingsOpen]=useState(false),[projectAction,setProjectAction]=useState<{kind:'edit'|'delete';project:Project}|null>(null),[removed,setRemoved]=useState<{id:string;name:string}|null>(null);
  useEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('dubisub.ui.v1.theme',theme);}catch{}},[theme]);
  useEffect(()=>{document.documentElement.dataset.cursor=customCursor?'custom':'system';try{localStorage.setItem('dubisub.ui.v1.cursor',customCursor?'custom':'system');}catch{}},[customCursor]);
  const [library,setLibrary]=useState<Project[]>([]), [project,setProject]=useState<Project|null>(null);
  const [tool,setTool]=useState<Tool>('media'),[showCreate,setShowCreate]=useState(true),[aspect,setAspect]=useState('16/9'),[activeAssetId,setActiveAssetId]=useState('');
  const [trackId,setTrackId]=useState(''),[cues,setCues]=useState<Cue[]>([]);
  const [status,setStatus]=useState('Sẵn sàng'),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [conflict,setConflict]=useState(false);
  const [dirty,setDirty]=useState(false),[history,setHistory]=useState<Cue[][]>([]),[future,setFuture]=useState<Cue[][]>([]);
  const [renderPlan,setRenderPlan]=useState<{in_ms:number;out_ms:number;speed:number;volume:number;aspect:string}|null>(null);
  const [projectSearch,setProjectSearch]=useState(''),[trash,setTrash]=useState<Project[]>([]),[showTrash,setShowTrash]=useState(false);
  const [cueError,setCueError]=useState('');
  const [name,setName]=useState(''),[mode,setMode]=useState('full'),[target,setTarget]=useState('vi');
  const pendingSeek=useRef<number|null>(null);
  const video=useRef<HTMLVideoElement>(null),saving=useRef(false),generation=useRef(0);
  const projectRef=useRef(project); projectRef.current=project;
  const selected=project?.tracks.find(t=>t.id===trackId);
  const refreshLibrary=()=>api<Project[]>('/api/projects').then(setLibrary);
  useEffect(()=>{refreshLibrary().catch(e=>setError(e.message));},[]);
  function load(p:Project){setProject(p);setActiveAssetId('');const t=p.tracks[0];setTrackId(t?.id||'');setCues(t?.cues||[]);setDirty(false);setHistory([]);setFuture([]);setError('');setConflict(false);setStatus('Đã mở dự án');}
  async function open(id:string){if(dirty||busy||saving.current)return false;try{load(await api<Project>('/api/projects/'+id));setRenderPlan(null);return true;}catch(e){setError(String(e));return false;}}
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
  const reviewPreview=selected?.kind==='review'?project?.dubbings?.find(d=>d.track_id===selected.id&&d.analysis_id):undefined;
  const previewDuration=reviewPreview?Math.max(...reviewPreview.segments.map(s=>s.end_ms))/1000:duration;
  const previewName=reviewPreview?'Review · timeline lời dẫn':media?.filename;
  const previewSrc=reviewPreview?`/api/projects/${project?.id}/narrations/${reviewPreview.id}/${reviewPreview.video?'video':'audio'}`:`/api/projects/${project?.id}/assets/${media?.id}/content`;
  useEffect(()=>{if(!video.current)return;if(reviewPreview){video.current.playbackRate=1;video.current.volume=1;return;}video.current.playbackRate=renderPlan?.speed||1;video.current.volume=Math.min(renderPlan?.volume??1,1);if(renderPlan){video.current.currentTime=renderPlan.in_ms/1000;setAspect(renderPlan.aspect.replace(':','/'));}},[renderPlan,media?.id,reviewPreview?.id]);
  async function refreshWorkflow(){if(!project||dirty||saving.current)return;const p=await api<Project>('/api/projects/'+project.id);setProject(p);const t=p.tracks.find(t=>t.id===trackId);if(t)setCues(t.cues);}
  function splitCue(cue:Cue){const cursor=Array.from(document.querySelectorAll<HTMLTextAreaElement>('textarea[data-cue-id]')).find(e=>e.dataset.cueId===cue.id)?.selectionStart??Math.floor(cue.text.length/2);const textIndex=cursor>0&&cursor<cue.text.length?cursor:Math.floor(cue.text.length/2);const now=Math.round((video.current?.currentTime||0)*1000);const middle=now>cue.start_ms&&now<cue.end_ms?now:Math.floor((cue.start_ms+cue.end_ms)/2);if(middle<=cue.start_ms||middle>=cue.end_ms||cues.length>=20000){setCueError('Không thể tách câu tại mốc này.');return;}change(cues.flatMap(c=>c.id===cue.id?[{...c,end_ms:middle,text:c.text.slice(0,textIndex)},{...c,id:crypto.randomUUID(),start_ms:middle,text:c.text.slice(textIndex)}]:[c]));}
  function mergeCue(index:number){const a=cues[index],b=cues[index+1];if(!b)return;change(cues.flatMap((c,i)=>i===index?[{...a,start_ms:Math.min(a.start_ms,b.start_ms),end_ms:Math.max(a.end_ms,b.end_ms),text:a.text+'\n'+b.text}]:i===index+1?[]:[c]));}
  function seek(seconds:number){if(video.current)video.current.currentTime=seconds;}
  function seekSource(seconds:number){if(!reviewPreview){seek(seconds);return;}if(dirty){setError('Lưu phụ đề trước khi chuyển về mốc nguồn.');return;}pendingSeek.current=seconds;const t=project?.tracks.find(t=>t.kind!=='review');setTrackId(t?.id||'');setCues(t?.cues||[]);setHistory([]);setFuture([]);setRenderPlan(null);}
  function workspace(view:string){if(dirty||busy)return;if(view==='source'||view==='translation'){const t=project?.tracks.find(t=>view==='translation'?t.kind==='translation':!['translation','review','description'].includes(t.kind||'source'));if(t){setTrackId(t.id);setCues(t.cues);setHistory([]);setFuture([]);}setTool(view==='source'?'subtitles':'translation');}else if(view==='voice')setTool('voice');else if(view==='analysis'||view==='script')setTool('review');else if(view==='export')setTool('export');const selector=view==='timeline'?'.timeline-panel':view==='export'?'.export-panel':view==='analysis'||view==='script'?'.analysis-panel':'.inspector';requestAnimationFrame(()=>document.querySelector(selector)?.scrollIntoView({behavior:'smooth',block:'nearest'}));}
  function configure(role?:unknown){setSettingsTab(typeof role==='string'?role:'appearance');setSettingsOpen(true);}
  async function manageProject(kind:'edit'|'delete',id:string){if(dirty||busy||saving.current)return;try{setProjectAction({kind,project:await api<Project>('/api/projects/'+id)});}catch(e){setError(String(e));}}

  const uploadInput=(kind:'media'|'subtitle')=><input type="file" accept={kind==='subtitle'?'.srt,.vtt,.ass':undefined} aria-label={kind==='media'?'Nhập video hoặc audio':'Nhập phụ đề'} disabled={busy||dirty} onChange={e=>{if(e.target.files?.[0])void upload(e.target.files[0],kind);e.target.value='';}}/>;
  return <div className="studio">
    <header className="appbar">
      <a className="brand" href="/" aria-label="DubiSub Studio"><img className="brand-wordmark" src={theme==='dark'?wordmarkDarkUrl:wordmarkUrl} alt="DubiSub"/><small>studio</small></a>
      <div className="project-heading"><Icon name="folder" size={17}/><h1>{project?.name||'Dự án chưa đặt tên'}</h1><button className="icon-button project-edit" disabled={!project||dirty||busy} aria-label={project?`Sửa dự án ${project.name}`:'Sửa dự án'} title="Sửa dự án đang mở" onClick={()=>{if(project)void manageProject('edit',project.id);}}><Icon name="edit" size={17}/></button><span className="project-state">{project?'Lưu cục bộ':'Không gian sáng tạo của bạn'}</span></div>
      <div className="header-actions"><button className="auto-launch" onClick={()=>setAutoOpen(true)}><Icon name="sparkles" size={16}/> Auto</button><button className="icon-button project-delete delete-action" disabled={!project||dirty||busy} aria-label={project?`Xóa dự án ${project.name}`:'Xóa dự án'} title="Xóa dự án đang mở" onClick={()=>{if(project)void manageProject('delete',project.id);}}><Icon name="trash" size={18}/></button><span className="badge"><i/> AI tùy cấu hình</span><button className="icon-button theme-toggle" aria-label={theme==='dark'?'Chuyển sang giao diện sáng':'Chuyển sang giao diện tối'} title={theme==='dark'?'Chuyển sang giao diện sáng':'Chuyển sang giao diện tối'} aria-pressed={theme==='dark'} onClick={()=>setTheme(t=>t==='dark'?'light':'dark')}><Icon name={theme==='dark'?'moon':'sun'}/></button><button className="primary" onClick={()=>{setTool('export');document.querySelector('.export-panel')?.scrollIntoView({behavior:'smooth',block:'nearest'});}}><Icon name="export" size={16}/> Xuất phụ đề</button></div>
    </header>
    <nav className="toolrail" aria-label="Công cụ studio"><button className="rail-library" aria-label="Kho dự án" aria-haspopup="dialog" aria-expanded={libraryOpen} onClick={()=>setLibraryOpen(true)}><Icon name="folder" size={23}/><span>Kho dự án</span></button>{tools.map(t=><button key={t.id} aria-pressed={tool===t.id} className={tool===t.id?'selected':''} onClick={()=>setTool(t.id)}><Icon name={t.icon} size={23}/><span>{t.label}</span></button>)}<button className="rail-settings" aria-label="Cài đặt studio" title="Cài đặt studio" onClick={configure}><Icon name="settings"/><span>Cài đặt</span></button></nav>
    <aside className="library-panel">
      <div className="panel-heading"><h2>Kho dự án</h2><span className="count">{library.length}</span></div>
      <button className="new-project" onClick={()=>setShowCreate(v=>!v)} aria-expanded={showCreate}><Icon name="plus" size={17}/> Dự án mới</button>
      {showCreate?<section className="create"><h2>Tạo dự án</h2><form onSubmit={async e=>{e.preventDefault();setBusy(true);try{const p=await api<Project>('/api/projects',{method:'POST',...json({name,mode,target_language:target})});load(p);await refreshLibrary();setName('');setShowCreate(false);}catch(e){setError(String(e));}finally{setBusy(false);}}}>
        <label>Tên dự án<input required maxLength={160} value={name} onChange={e=>setName(e.target.value)} placeholder="Câu chuyện tiếp theo…"/></label>
        <label>Chế độ<select aria-label="Chế độ" value={mode} onChange={e=>setMode(e.target.value)}><option value="full">Dịch / lồng tiếng toàn bộ</option><option value="review">Review tóm tắt</option></select></label>
        <label>Ngôn ngữ đích (BCP 47)<input value={target} onChange={e=>setTarget(e.target.value)} required aria-describedby="language-help"/></label><button className="primary" disabled={busy||dirty} type="submit">Tạo dự án</button>
      </form><small id="language-help">Mặc định tiếng Việt (vi). English: en.</small></section>:null}
      <label className="project-search">Tìm dự án<input aria-label="Tìm dự án" value={projectSearch} onChange={e=>setProjectSearch(e.target.value)} placeholder="Tên dự án…"/></label><nav className="project-list" aria-label="Dự án">{library.length?library.filter(p=>p.name.toLocaleLowerCase().includes(projectSearch.toLocaleLowerCase())).map(p=><div className="project-row" key={p.id}><button disabled={dirty||busy} className={project?.id===p.id?'project-open active':'project-open'} onClick={()=>{void open(p.id);setShowCreate(false);}}><span className="project-icon"><Icon name="folder" size={17}/></span><span>{p.name}<small>{p.mode==='review'?'Review tóm tắt':'Dịch / lồng tiếng'}</small></span></button></div>):<p className="muted library-empty">Tất cả dự án của bạn sẽ ở đây.</p>}</nav>
      <button className="trash-toggle" aria-expanded={showTrash} onClick={async()=>{try{const p=await api<Project[]>('/api/projects?deleted=true');setTrash(p);setShowTrash(v=>!v);}catch(e){setError(String(e));}}}>Dự án đã xóa</button>
      {showTrash?<section className="trash-list"><h3>Thùng rác dự án</h3>{trash.length?trash.map(p=><div key={p.id}><span>{p.name}</span><button disabled={dirty||busy} onClick={async()=>{try{await api(`/api/projects/${p.id}/restore`,{method:'POST'});setTrash(old=>old.filter(t=>t.id!==p.id));await refreshLibrary();}catch(e){setError(String(e));}}}>Khôi phục {p.name}</button></div>):<p>Chưa có dự án đã xóa.</p>}</section>:null}
      {removed?<div className="restore-notice"><span>Đã xóa {removed.name} khỏi thư viện.</span><button onClick={async()=>{try{await api('/api/projects/'+removed.id+'/restore',{method:'POST'});await refreshLibrary();setRemoved(null);}catch(e){setError(String(e));}}}>Khôi phục dự án</button></div>:null}
      <div className="panel-heading media-heading"><h2>Phương tiện</h2><span className="count">{project?.assets?.length||0}</span></div>
      <label className="file media-upload"><Icon name="cloud" size={24}/><strong>Nhập video hoặc audio</strong><span>Kéo thả hoặc chọn từ máy</span>{uploadInput('media')}</label>
      <LinkImport projectId={project?.id} links={project?.links||[]} locked={busy||dirty} ensureProject={async()=>{if(project)return project.id;const p=await api<Project>('/api/projects',{method:'POST',...json({name:'Video từ liên kết',mode,target_language:target})});load(p);setShowCreate(false);await refreshLibrary();return p.id;}} onImported={async id=>{if(!dirty&&!saving.current)load(await api<Project>('/api/projects/'+id));}}/>
      <div className="asset-list">{project?.assets?.map(a=><button key={a.id} className={media?.id===a.id?'asset active':'asset'} disabled={a.kind!=='media'||!a.metadata} onClick={()=>setActiveAssetId(a.id)}><span className="asset-icon"><Icon name={a.kind==='media'?'media':'captions'} size={19}/></span><span>{a.filename}<small>{a.kind==='subtitle'?'Phụ đề nguồn':a.metadata?`${Number(JSON.parse(a.metadata).format?.duration||0).toFixed(1)} giây`:'Đang kiểm tra…'}</small></span></button>)}</div>
      <div className="jobs">{project?.jobs?.map(j=><div key={j.id}><span className={'job-dot '+j.state}/><strong>{j.kind==='inspect_link'?'Phân tích link':j.kind==='download_link'?'Nhập link':j.kind==='translate'?'Dịch phụ đề':j.kind==='transcribe'?'Nhận dạng lời thoại':j.kind==='render'?'Xuất MP4':j.kind==='voice_sample'?'Tạo mẫu giọng':j.kind==='voice_extract'?'Cắt hồ sơ giọng':j.kind==='narrate'?'Tạo lời đọc / lồng tiếng':'Kiểm tra media'}</strong><small>{j.state} · {j.progress}%</small>{j.error?<p role="alert">{j.error}</p>:null}{['queued','running'].includes(j.state)?<button onClick={()=>api(`/api/jobs/${j.id}/cancel`,{method:'POST'}).then(()=>open(project!.id)).catch(e=>setError(String(e)))}>Hủy</button>:null}{['failed','canceled'].includes(j.state)?<button onClick={()=>api(`/api/jobs/${j.id}/retry`,{method:'POST'}).then(()=>open(project!.id)).catch(e=>setError(String(e)))}>Thử lại</button>:null}</div>)}</div>

      <div className="storage-note"><img src={theme==='dark'?logoDarkUrl:logoUrl} width="25" height="25" alt=""/><span>Media gốc luôn được giữ nguyên.<small>Dữ liệu lưu trên máy của bạn.</small></span></div>
    </aside>
    <main className="stage">
      <div className="stage-topbar"><div><span className="live-dot"/> Preview <span className="stage-project-mode">{project?.mode==='review'?'Review tóm tắt':'Dịch & biên tập'}</span></div><div><label className="aspect-picker"><span>Tỷ lệ xem</span><select aria-label="Tỷ lệ preview" value={aspect} onChange={e=>setAspect(e.target.value)}><option value="16/9">16:9</option><option value="9/16">9:16</option><option value="1/1">1:1</option></select></label><button className="icon-button" disabled={!media} aria-label="Toàn màn hình video" onClick={()=>video.current?.requestFullscreen().catch(e=>setError(String(e)))}><Icon name="expand" size={17}/></button></div></div>
      <div className="preview-canvas" onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(!busy&&!dirty&&e.dataTransfer.files[0])void upload(e.dataTransfer.files[0],'media');}}>
        <div className={'preview-frame '+(!media?'no-media':'')} style={{aspectRatio:aspect}}>
        {media&&project?<video key={reviewPreview?.id||media.id} ref={video} controls onLoadedMetadata={()=>{if(pendingSeek.current!==null&&video.current){video.current.currentTime=pendingSeek.current;pendingSeek.current=null;}}} onTimeUpdate={()=>{if(!reviewPreview&&renderPlan&&video.current){if(video.current.currentTime>=renderPlan.out_ms/1000){video.current.pause();video.current.currentTime=renderPlan.in_ms/1000;}else if(video.current.currentTime<renderPlan.in_ms/1000)video.current.currentTime=renderPlan.in_ms/1000;}}} onError={()=>setStatus('Trình duyệt chưa hỗ trợ định dạng này. Bạn vẫn có thể sửa và xuất phụ đề.')} src={previewSrc}>{selected?<track key={`${selected.id}-${project.revision}`} kind="subtitles" label="Phụ đề nguồn" srcLang={selected.language} src={`/api/projects/${project.id}/tracks/${selected.id}/export?format=vtt&revision=${project.revision}`} default/>:null}</video>:<div className="canvas-empty"><img className="studio-banner" src={bannerUrl} alt="DubiSub — Translate. Dub. Create."/><h2>Không gian cho câu chuyện tiếp theo.</h2><p>Thả video vào đây để bắt đầu.<br/>Không gian biên tập đã sẵn sàng.</p><button className="canvas-import" onClick={()=>document.querySelector<HTMLInputElement>('.media-upload input')?.click()}><Icon name="plus" size={17}/> Nhập phương tiện</button><span className="canvas-footnote">Video · Audio · Phụ đề đa ngôn ngữ</span></div>}
        </div>
      </div>
      <div className="stage-bottom"><span>{media?.filename||'Chưa có phương tiện'}{mediaMeta?` · ${mediaMeta.streams?.find((s:{codec_type:string})=>s.codec_type==='video')?.width||'Audio'}${mediaMeta.streams?.find((s:{codec_type:string})=>s.codec_type==='video')?.height?` × ${mediaMeta.streams.find((s:{codec_type:string})=>s.codec_type==='video').height}`:''}`:''}</span><span>{reviewPreview?'Preview review · timeline lời dẫn mới':'Preview từ nguồn gốc'}</span></div>
      <div className="capability-strip">{[{id:'subtitles',name:'Phụ đề',text:'Sửa & xuất SRT/VTT',icon:'captions'},{id:'translation',name:'Dịch thuật',text:'Provider & glossary',icon:'languages'},{id:'voice',name:'Giọng đọc',text:'Giọng & mẫu nghe',icon:'wave'},{id:'review',name:'Review',text:'Kịch bản & cảnh nguồn',icon:'script'}].map(t=><button key={t.id} className={tool===t.id?'active':''} onClick={()=>setTool(t.id as Tool)}><Icon name={t.icon} size={19}/><span>{t.name}<small>{t.text}</small></span></button>)}</div>
    </main>
    <aside className="inspector">
      <div className="inspector-guide"><strong>Công cụ xử lý</strong><small>1. Transcript → 2. Dịch → 3. Giọng → 4. Xuất</small><button onClick={()=>setAutoOpen(true)}>Mở hướng dẫn Auto</button><nav className="workspace-tabs" aria-label="Các vùng studio">{[{id:'source',label:'Transcript gốc'},{id:'translation',label:'Bản dịch'},{id:'analysis',label:'Phân tích cảnh'},{id:'script',label:'Tóm tắt/kịch bản'},{id:'voice',label:'Giọng & nhân vật'},{id:'timeline',label:'Timeline'},{id:'export',label:'Xuất'}].map(v=><button key={v.id} disabled={dirty||busy} onClick={()=>workspace(v.id)}>{v.label}</button>)}</nav></div>
      {tool==='review'||Object.keys(project?.analyses||{}).length?<AnalysisPanel projectId={project?.id} revision={project?.revision||0} analyses={project?.analyses||{}} locked={dirty||busy} onSeek={seekSource} onRefresh={refreshWorkflow}/>:null}
      {tool!=='media'&&tool!=='subtitles'&&tool!=='export'&&tool!=='translation'&&tool!=='voice'&&tool!=='review'?<ToolInfo tool={tool} onConfigure={configure}/>:null}
      <WorkflowPanel projectId={project?.id} revision={project?.revision||0} target={project?.target_language||target} trackId={trackId} tracks={project?.tracks||[]} assetId={media?.id} audioStreams={mediaMeta?.streams?.filter((s:{codec_type:string})=>s.codec_type==='audio')||[]} glossary={project?.glossary||{}} locked={dirty||busy} onRefresh={refreshWorkflow} onConfigure={configure}/>
      {tool==='voice'?<DubbingPanel analyses={project?.analyses||{}} projectId={project?.id} revision={project?.revision||0} assetId={media?.id} duration={duration} trackId={trackId} cues={cues} profiles={project?.voice_profiles||{}} dubbings={project?.dubbings||[]} savedSettings={project?.narration_settings?.[trackId]} locked={dirty||busy} onRefresh={refreshWorkflow} onEdit={change}/>:null}
      {tool==='voice'?<VoicePanel projectId={project?.id} samples={project?.voice_samples||{}} jobs={project?.jobs||[]} locked={dirty||busy} onRefresh={refreshWorkflow} onConfigure={configure}/>:null}
      <section className="editor"><div className="panel-heading"><h2>{selected?.kind==='review'?'Phụ đề review':selected?.kind==='translation'?'Bản dịch':'Phụ đề nguồn'}</h2><span className="count">{cues.length} câu</span></div><button className="new-track" disabled={!project||dirty||busy} onClick={async()=>{if(!project)return;try{const result=await api<{project:Project;track_id:string}>(`/api/projects/${project.id}/tracks`,{method:'POST',...json({revision:project.revision,language:'und'})});setProject({...project,...result.project});setTrackId(result.track_id);setCues([]);setHistory([]);setFuture([]);}catch(e){setError(String(e));}}}>Tạo track phụ đề trống</button><label className="file subtitle-upload"><Icon name="plus" size={16}/><span>Nhập SRT / VTT / ASS</span>{uploadInput('subtitle')}</label>
      {project?.tracks.length?<><label className="track-select">Track<select aria-label="Track phụ đề" value={trackId} disabled={dirty} onChange={e=>{const t=project.tracks.find(t=>t.id===e.target.value)!;setTrackId(t.id);setCues(t.cues);setHistory([]);setFuture([]);}}>{project.tracks.map((t,i)=><option key={t.id} value={t.id}>Track {i+1} · {t.language} · {t.kind==='translation'?'Bản dịch':t.kind==='asr'?'ASR':t.kind==='review'?'Lời dẫn review (timeline mới)':'Nguồn'} · {t.cues.length} câu</option>)}</select></label><div className="toolbar"><button disabled={!history.length} onClick={undo} aria-label="Hoàn tác" title="Hoàn tác"><Icon name="undo" size={16}/></button><button disabled={!future.length} onClick={redo} aria-label="Làm lại" title="Làm lại"><Icon name="redo" size={16}/></button><button onClick={()=>void save()} disabled={!dirty}><Icon name="check" size={15}/> Lưu ngay</button><span>{dirty?'Chưa lưu':'Đã lưu'}</span></div>
      <SubtitleTools cues={cues} onChange={change} playhead={()=>video.current?.currentTime||0}/>{cueError?<p className="link-error" role="alert">{cueError}</p>:null}<div className="cues">{cues.map((c,i)=><article key={c.id}><button className="seek" aria-label={`Tới câu ${i+1}`} onClick={()=>seek(c.start_ms/1000)}>{String(i+1).padStart(2,'0')}</button><div className="cue-body"><div className="times"><label>Bắt đầu (ms)<input type="number" min="0" value={c.start_ms} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,start_ms:Number(e.target.value)}:x))}/></label><span className="time-divider">—</span><label>Kết thúc (ms)<input type="number" min="1" value={c.end_ms} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,end_ms:Number(e.target.value)}:x))}/></label></div><label className="text-label">Câu {i+1}<textarea data-cue-id={c.id} aria-label={`Câu ${i+1}`} dir="auto" value={c.text} onChange={e=>change(cues.map(x=>x.id===c.id?{...x,text:e.target.value}:x))}/></label><div className="cue-actions"><button type="button" aria-label={`Tách câu ${i+1}`} onClick={()=>splitCue(c)}>Tách</button><button type="button" aria-label={`Gộp câu ${i+1} với câu sau`} disabled={i===cues.length-1} onClick={()=>mergeCue(i)}>Gộp</button><button type="button" aria-label={`Xóa câu ${i+1}`} onClick={()=>change(cues.filter(x=>x.id!==c.id))}>Xóa</button><span>{(c.text.length/((c.end_ms-c.start_ms)/1000)).toFixed(1)} ký tự/s</span></div>{c.review_reasons?.length?<p className="narration-warning">Cần nghe đối chiếu: {c.review_reasons.join('; ')}</p>:null}{c.end_ms<=c.start_ms?<p className="error">Kết thúc phải sau bắt đầu.</p>:null}</div></article>)}</div><small className="editor-note">Tự lưu sau khi sửa. ASS chuyển thành chữ thuần.</small></>:<div className="subtitle-empty"><div className="subtitle-lines"><span/><span/><span/></div><h3>Lời thoại nằm ở đây</h3><p>Nhập phụ đề hoặc trích track chữ từ video để sửa từng câu.</p><span>Hỗ trợ tiếng Việt, CJK & RTL</span></div>}
      </section>
      <section className={'export-panel '+(tool==='export'?'highlighted':'')}><div className="panel-heading"><h2>Xuất phụ đề</h2><Icon name="export" size={17}/></div><p>Bản phụ đề của bạn, sẵn sàng mang đi.</p><div className="export-options">{['srt','vtt','ass'].map(f=>project&&selected?<a key={f} aria-disabled={dirty} onClick={e=>{if(dirty)e.preventDefault();}} href={`/api/projects/${project.id}/tracks/${trackId}/export?format=${f}`} download><Icon name="export" size={15}/> Xuất {f.toUpperCase()}</a>:<button key={f} disabled><Icon name="export" size={15}/> Xuất {f.toUpperCase()}</button>)}</div><small>{selected?(dirty?'Đợi tự lưu trước khi xuất.':'Xuất trực tiếp, không cần dựng video.'):'Nhập phụ đề để mở xuất SRT/VTT.'}</small><small className="video-export-note">Tạo giọng preset/giọng mẫu và gán nhân vật tại công cụ Giọng đọc.</small></section>
      <RenderPanel projectId={project?.id} revision={project?.revision||0} assetId={reviewPreview?undefined:media?.id} duration={duration} trackId={selected?.id} locked={dirty||busy} artifacts={project?.artifacts||[]} onPlan={setRenderPlan} onRefresh={refreshWorkflow}/>
    </aside>
    <Timeline output={!!reviewPreview} key={reviewPreview?.id||media?.id||'empty'} video={video} cues={cues} duration={previewDuration} filename={previewName} onSeek={seek}/>
    <div className="appstatus"><span className="save-indicator"><i className={dirty?'unsaved':''}/><span role="status">{busy?'Đang nhập file…':status}</span></span><span className="status-right">DubiSub Studio <span>•</span> Cục bộ <span>•</span> {project?.target_language||target}</span></div>
    {error?<div className="error-toast" role="alert"><div><strong>Không thể hoàn tất thao tác</strong><button className="icon-button" aria-label="Đóng thông báo" onClick={()=>setError('')}>×</button></div><p>{error}</p>{conflict?<><p>Tải bản sửa dự phòng trước khi mở phiên bản mới.</p><button onClick={()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schema_version:1,project_id:project?.id,track_id:trackId,cues},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='dubisub-unsaved-cues.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}}>Tải bản sửa dự phòng</button><button onClick={async()=>{if(project)load(await api<Project>('/api/projects/'+project.id));}}>Mở phiên bản mới</button></>:null}</div>:null}
    <ProjectLibrary open={libraryOpen} onClose={()=>setLibraryOpen(false)} currentId={project?.id} locked={dirty||busy} onOpen={async id=>{const opened=await open(id);if(opened){setShowCreate(false);setTool('media');}return opened;}}/>
    <AutoWizard open={autoOpen} onClose={()=>setAutoOpen(false)} projectId={project?.id} revision={project?.revision||0} assets={project?.assets||[]} tracks={project?.tracks||[]} currentTrack={trackId} locked={dirty||busy} onConfigure={configure} onRefresh={refreshWorkflow}/>
    <SettingsDialog startTab={settingsTab} open={settingsOpen} onClose={()=>setSettingsOpen(false)} theme={theme} onTheme={setTheme} cursor={customCursor} onCursor={setCustomCursor}/>
    <ProjectDialog action={projectAction} onClose={()=>setProjectAction(null)} onSave={async p=>{await api<Project>('/api/projects/'+p.id,{method:'PATCH',...json({name:p.name,mode:p.mode,target_language:p.target_language,revision:p.revision})});if(project?.id===p.id)load(await api<Project>('/api/projects/'+p.id));await refreshLibrary();setStatus('Đã sửa thông tin dự án');}} onDelete={async p=>{await api('/api/projects/'+p.id,{method:'DELETE',...json({revision:p.revision})});if(project?.id===p.id){setProject(null);setTrackId('');setCues([]);setHistory([]);setFuture([]);setDirty(false);}setRemoved(p);await refreshLibrary();setStatus('Đã xóa dự án khỏi thư viện');}}/>
  </div>;
}

createRoot(document.getElementById('root')!).render(<App/>);
