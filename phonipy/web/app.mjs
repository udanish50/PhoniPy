import {VERSION,preset,validateConfig,noteName} from './engine.mjs';
const $=id=>document.getElementById(id);
const state={items:[],selected:null,previewBuffer:null,previewItem:null,worker:null,cancelReject:null,epoch:0,viewEpoch:0,busy:false};
const metricInfo=[
 ['raw_duration','Recording duration','s','Total duration of the input recording.'],
 ['active_time','Active span','s','From the first stable interval onset to the final stable interval offset.'],
 ['valid_time','Stable voice time','s','Total duration of all qualifying stable-note intervals.'],
 ['average_offset','Pitch offset','st','Mean segment pitch relative to the reference note. Signed offsets can cancel.'],
 ['average_energy','Harmonic energy','ratio','Duration-weighted harmonic-series energy divided by total energy.'],
 ['hoarseness','Residual energy (hoarseness)','%','One minus harmonic energy, expressed as a percentage; not a perceptual rating.'],
 ['average_duration','Mean interval duration','s','Average duration of a qualifying stable-note interval.'],
 ['continuity','Continuity index','index','Mean interval duration divided by stable time; equals 1 / segment count.'],
 ['sparsity','Stable occupancy','ratio','Stable voice time divided by the active span.'],
 ['breakouts','Stable segments','count','Number of qualifying intervals, including the first acquisition.']
];
function visible(id,yes){$(id).classList.toggle('hidden',!yes);}
function showError(message){$('error').textContent=message;visible('error',!!message);}
function fmt(value,digits=3){return value===null||!Number.isFinite(value)?'—':value.toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});}
function seconds(value){return fmt(value,3)+' s';}
function fileSize(bytes){return bytes>1048576?(bytes/1048576).toFixed(1)+' MB':Math.ceil(bytes/1024)+' KB';}
function config(){return validateConfig({...preset($('preset').value),reference_key:+$('reference').value,min_frames:+$('min-frames').value,min_periodicity:+$('periodicity').value,fmin:+$('fmin').value,fmax:+$('fmax').value,window_ms:+$('window').value,hop_ms:+$('hop').value,harmonics:+$('harmonics').value,channel:$('channel').value});}
function setBusy(busy){state.busy=busy;$('analyze').disabled=busy||!state.items.length;$('cancel').classList.toggle('hidden',!busy);$('audio-input').disabled=busy;for(const el of document.querySelectorAll('.controls select,.controls input[type=number]'))el.disabled=busy;visible('progress-panel',busy);}
function refreshList(){
 const list=$('file-list');list.replaceChildren();
 for(const item of state.items){const b=document.createElement('button');b.className='file-item'+(item===state.selected?' selected':'')+(item.result?' complete':'')+(item.error?' failed':'');b.type='button';b.setAttribute('aria-label','Select '+item.file.name);b.setAttribute('aria-pressed',String(item===state.selected));const glyph=document.createElement('span');glyph.className='file-glyph';glyph.textContent='♫';const copy=document.createElement('span');copy.className='file-copy';const name=document.createElement('strong');name.textContent=item.file.name;const meta=document.createElement('small');meta.textContent=[fileSize(item.file.size),item.duration?fmt(item.duration,2)+' s':'',item.result?'Analyzed':item.error?'Could not analyze':'Ready to play'].filter(Boolean).join(' · ');copy.append(name,meta);const dot=document.createElement('span');dot.className='file-dot';b.append(glyph,copy,dot);b.addEventListener('click',()=>selectItem(item));list.append(b);}
 $('clear').disabled=!state.items.length;$('analyze').disabled=state.busy||!state.items.length;
}
function stopWorker(){if(state.worker){state.worker.terminate();state.worker=null;}if(state.cancelReject){state.cancelReject(new Error('Analysis cancelled.'));state.cancelReject=null;}}
function clearWorkspace(){state.epoch++;state.viewEpoch++;stopWorker();$('player').pause();$('player').removeAttribute('src');$('player').load();for(const item of state.items){URL.revokeObjectURL(item.url);item.result=null;}state.items=[];state.selected=null;state.previewBuffer=null;state.previewItem=null;$('audio-input').value='';$('waveform').replaceChildren();$('key-metrics').replaceChildren();$('metric-rows').replaceChildren();$('segment-rows').replaceChildren();$('pitch-chart').replaceChildren();$('energy-chart').replaceChildren();showError('');setBusy(false);visible('player-panel',false);visible('results',false);visible('empty-state',true);refreshList();}
async function decode(item){
 const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)throw Error('This browser does not support audio decoding. Please use a current version of Chrome, Edge, Firefox, or Safari.');
 const context=new Audio();try{const bytes=await item.file.arrayBuffer();const buffer=await context.decodeAudioData(bytes);if(!buffer.length||!Number.isFinite(buffer.duration))throw Error('This recording has no usable audio.');if(buffer.duration>300)throw Error('This recording is longer than five minutes. Select a shorter excerpt.');return buffer;}catch(e){if(e.message.includes('five minutes')||e.message.includes('usable audio'))throw e;throw Error('This audio format could not be decoded. Convert the recording to an uncompressed PCM WAV file and try again.');}finally{await context.close();}
}
function drawWaveform(buffer){
 const data=buffer.getChannelData(0),w=900,h=72,bars=360,step=Math.max(1,Math.floor(data.length/bars));let path='';let peak=0;const peaks=[];
 for(let i=0;i<bars;i++){let amplitude=0;for(let j=i*step;j<Math.min(data.length,(i+1)*step);j+=Math.max(1,Math.floor(step/60)))amplitude=Math.max(amplitude,Math.abs(data[j]));peaks.push(amplitude);peak=Math.max(peak,amplitude);}
 for(let i=0;i<bars;i++){const a=peak?Math.max(1,peaks[i]/peak*29):1,x=i*w/bars+1;path+=`M${x.toFixed(2)} ${(h/2-a).toFixed(2)}v${(2*a).toFixed(2)}`;}
 $('waveform').innerHTML=`<path d="${path}" stroke="#b4a4ec" stroke-width="1.4" stroke-linecap="round"/><line class="playhead" x1="0" y1="0" x2="0" y2="72"/>`;
}
async function selectItem(item){
 if(!state.items.includes(item))return;state.selected=item;const view=++state.viewEpoch;refreshList();showError(item.error||'');visible('player-panel',true);$('player-name').textContent=item.file.name;$('player-meta').textContent=fileSize(item.file.size)+' · Playback available before analysis';$('player').src=item.url;visible('results',!!item.result);visible('empty-state',!item.result);if(item.result)renderResult(item);
 try{if(state.previewItem!==item){state.previewBuffer=null;state.previewItem=null;const buffer=await decode(item);if(view!==state.viewEpoch||!state.items.includes(item))return;state.previewBuffer=buffer;state.previewItem=item;}const buffer=state.previewBuffer;item.duration=buffer.duration;$('player-meta').textContent=fmt(buffer.duration,2)+' seconds · '+buffer.numberOfChannels+' channel'+(buffer.numberOfChannels===1?'':'s')+' · '+fileSize(item.file.size);drawWaveform(buffer);refreshList();}catch(e){if(view!==state.viewEpoch)return;item.error=e.message;showError(e.message);refreshList();}
}
async function addFiles(files){
 if(state.busy)return;showError('');const incoming=Array.from(files);if(!incoming.length)return;
 if(state.items.length+incoming.length>10){showError('Load up to 10 recordings at a time. Clear this workspace before adding another batch.');return;}
 if([...state.items.map(x=>x.file),...incoming].reduce((s,x)=>s+x.size,0)>150*1024*1024){showError('This batch exceeds 150 MB. Select fewer recordings at a time.');return;}
 const invalid=incoming.find(x=>x.size>100*1024*1024||!x.size);if(invalid){showError(invalid.size?'Each recording must be smaller than 100 MB.':'The selected recording is empty.');return;}
 for(const file of incoming)state.items.push({file,url:URL.createObjectURL(file),result:null,error:null,duration:null});refreshList();await selectItem(state.items.at(-incoming.length));
}
async function prepare(buffer,c){
 const count=buffer.numberOfChannels;let selected=0;
 if(c.channel==='right'){if(count<2)throw Error('This recording has no right channel. Select Loudest or Left.');selected=1;}
 if(c.channel==='loudest'&&count>1){let best=-1;for(let ch=0;ch<count;ch++){const data=buffer.getChannelData(ch);let energy=0;for(const x of data)energy+=x*x;if(energy>best){best=energy;selected=ch;}}}
 const mono=new Float32Array(buffer.length);if(c.channel==='mix'){for(let ch=0;ch<count;ch++){const data=buffer.getChannelData(ch);for(let i=0;i<mono.length;i++)mono[i]+=data[i]/count;}}else mono.set(buffer.getChannelData(selected));
 const warnings=[];let mean=0,clipping=false;for(const x of mono){if(!Number.isFinite(x))throw Error('The recording contains invalid samples. Convert it to PCM WAV and try again.');mean+=x;if(Math.abs(x)>=.999)clipping=true;}
 if(clipping)warnings.push('Samples approach full scale. Clipping may affect the measurements.');if(Math.abs(mean/mono.length)>.01)warnings.push('A DC offset was detected. Analysis windows are mean-centered.');if(count>1)warnings.push(`Multichannel recording: ${c.channel} channel policy applied.`);
 if(buffer.sampleRate===c.sample_rate)return {samples:mono,warnings,selected};
 const Offline=window.OfflineAudioContext||window.webkitOfflineAudioContext;if(!Offline)throw Error('Audio resampling is unavailable in this browser. Try a current browser.');
 const offline=new Offline(1,Math.ceil(buffer.duration*c.sample_rate),c.sample_rate),input=offline.createBuffer(1,mono.length,buffer.sampleRate);input.getChannelData(0).set(mono);const source=offline.createBufferSource();source.buffer=input;source.connect(offline.destination);source.start();const rendered=await offline.startRendering();return {samples:rendered.getChannelData(0).slice(),warnings,selected};
}
function runWorker(samples,c,options,progress){return new Promise((resolve,reject)=>{state.cancelReject=reject;const worker=new Worker(new URL('./worker.mjs',import.meta.url),{type:'module'});state.worker=worker;const finish=()=>{worker.terminate();if(state.worker===worker)state.worker=null;state.cancelReject=null;};worker.onmessage=({data})=>{if(data.type==='progress')progress(data.value);else if(data.type==='result'){finish();resolve(data.result);}else{finish();reject(Error(data.message));}};worker.onerror=()=>{finish();reject(Error('The analysis worker could not start. Reload the page and try again.'));};worker.postMessage({samples,config:c,options},[samples.buffer]);});}
async function analyze(){
 let c;try{c=config();}catch(e){showError(e.message);return;}showError('');const epoch=++state.epoch;setBusy(true);let completed=0;
 for(const item of state.items){if(epoch!==state.epoch)break;$('progress-label').textContent=`Analyzing ${completed+1} of ${state.items.length}`;const started=performance.now();item.error=null;
  try{const buffer=state.previewItem===item&&state.previewBuffer?state.previewBuffer:await decode(item);if(epoch!==state.epoch)break;const prepared=await prepare(buffer,c);if(epoch!==state.epoch)break;item.duration=buffer.duration;const options={source:item.file.name,duration:buffer.duration,warnings:prepared.warnings,metadata:{decoded_sample_rate:buffer.sampleRate,channels:buffer.numberOfChannels,selected_channel:prepared.selected,sample_count:buffer.length}};
   const result=await runWorker(prepared.samples,c,options,value=>{const progress=(completed+value)/state.items.length;$('progress').value=progress;$('progress-number').textContent=Math.round(progress*100)+'%';});if(epoch!==state.epoch)break;result.metadata.processing_ms=performance.now()-started;item.result=result;
  }catch(e){if(epoch!==state.epoch)break;item.error=e.message;item.result=null;}
  completed++;$('progress').value=completed/state.items.length;$('progress-number').textContent=Math.round(completed/state.items.length*100)+'%';refreshList();if(item===state.selected){if(item.result)renderResult(item);else showError(item.error);}
 }
 if(epoch===state.epoch){setBusy(false);refreshList();const failed=state.items.filter(i=>i.error);if(failed.length)showError(failed.length===1?failed[0].error:`${failed.length} recordings could not be analyzed. Select a recording to view its details.`);}
}
function cell(text,className){const td=document.createElement('td');td.textContent=text;if(className)td.className=className;return td;}
function renderResult(item){
 const r=item.result;if(!r)return;visible('empty-state',false);visible('results',true);$('result-name').textContent=item.file.name;$('result-detail').textContent=`${seconds(r.metrics.raw_duration)} · Reference ${noteName(r.config.reference_key)} · ${fmt(r.metadata.processing_ms/1000,2)} s processing`;
 $('key-metrics').replaceChildren();for(const [label,value,unit,caption] of [['Stable voice time',r.metrics.valid_time,'s','Qualifying note intervals'],['Harmonic energy',r.metrics.average_energy===null?null:r.metrics.average_energy*100,'%','Series / total energy'],['Stable segments',r.metrics.breakouts,'','Separate note detections'],['Pitch offset',r.metrics.average_offset,'st','Relative to '+noteName(r.config.reference_key)]]){const card=document.createElement('article');card.className='metric-card';const l=document.createElement('span');l.className='metric-label';l.textContent=label;const v=document.createElement('span');v.className='metric-value';v.textContent=fmt(value,unit===''?0:2);const u=document.createElement('span');u.className='metric-unit';u.textContent=unit;v.append(u);const cap=document.createElement('span');cap.className='metric-caption';cap.textContent=caption;card.append(l,v,cap);$('key-metrics').append(card);}
 $('metric-rows').replaceChildren();for(const [key,label,unit,description] of metricInfo){const row=document.createElement('tr'),name=cell(label),api=document.createElement('span');api.className='api-name';api.textContent=key;name.append(api);const value=r.metrics[key];row.append(name,cell(value===null?'—':fmt(value,unit==='count'?0:unit==='%'?2:3)+(unit==='ratio'||unit==='index'||unit==='count'?'':' '+unit)),cell(description));$('metric-rows').append(row);}
 $('segment-rows').replaceChildren();if(!r.segments.length){const row=document.createElement('tr'),td=cell('No qualifying stable-note intervals.');td.colSpan=5;row.append(td);$('segment-rows').append(row);}else{for(const s of r.segments.slice(0,500)){const row=document.createElement('tr');row.append(cell(noteName(s.key)+' · '+s.key),cell(seconds(s.start)),cell(seconds(s.end)),cell(seconds(s.duration)),cell(fmt(s.mean_energy*100,2)+'%'));$('segment-rows').append(row);}if(r.segments.length>500){const row=document.createElement('tr'),td=cell(`Showing the first 500 of ${r.segments.length} intervals. The full report includes every interval.`);td.colSpan=5;row.append(td);$('segment-rows').append(row);}}
 $('warning-list').replaceChildren();for(const message of r.warnings){const li=document.createElement('li');li.textContent=message;$('warning-list').append(li);}visible('warnings',r.warnings.length>0);drawCharts(r);showError(item.error||'');
}
function drawCharts(r){
 const W=900,left=42,right=16,top=17,bottom=25,duration=r.metrics.raw_duration,plotW=W-left-right;
 const candidates=r.frames.filter(f=>f.accepted&&f.fractional_key!==null).map(f=>f.fractional_key),low=candidates.length?Math.floor(Math.min(...candidates))-1:r.config.reference_key-3,high=candidates.length?Math.max(low+4,Math.ceil(Math.max(...candidates))+1):r.config.reference_key+3;
 const x=t=>left+t/duration*plotW;
 function chart(kind,height){const energy=kind==='energy',plotH=height-top-bottom,y=v=>top+(energy?1-v:(high-v)/(high-low))*plotH;let svg=`<svg viewBox="0 0 ${W} ${height}" role="img" aria-label="${energy?'Harmonic energy ratio':'Detected pitch'} over time">`;
  for(let i=0;i<=4;i++){const yy=top+i*plotH/4;svg+=`<line x1="${left}" x2="${W-right}" y1="${yy}" y2="${yy}" stroke="#efecf5" stroke-dasharray="3 4"/><text x="${left-8}" y="${yy+3}" text-anchor="end">${energy?Math.round((1-i/4)*100)+'%':noteName(high-i*(high-low)/4)}</text>`;}
  for(let i=0;i<=5;i++){const xx=x(duration*i/5);svg+=`<text x="${xx}" y="${height-5}" text-anchor="middle">${(duration*i/5).toFixed(duration<10?1:0)}s</text>`;}
  for(const s of r.segments)svg+=`<rect x="${x(s.start)}" y="${top}" width="${Math.max(.5,x(s.end)-x(s.start))}" height="${plotH}" fill="#258c83" opacity=".055"/>`;
  const stride=Math.max(1,Math.ceil(r.frames.length/1200));let path='',connected=false;
  for(let i=0;i<r.frames.length;i+=stride){const f=r.frames[i],v=energy?f.energy_ratio:f.fractional_key;if(!energy&&!f.accepted){connected=false;continue;}if(v===null){connected=false;continue;}path+=(connected?'L':'M')+x(f.start).toFixed(2)+' '+y(v).toFixed(2);connected=true;}
  svg+=`<path d="${path}" fill="none" stroke="${energy?'#8b78cf':'#8067d7'}" stroke-width="1.45" stroke-linejoin="round"/>`;
  if(energy)for(const s of r.segments.slice(0,300))svg+=`<circle cx="${x(s.start)}" cy="${y(s.mean_energy)}" r="2.2" fill="#6f8fcf"><title>${noteName(s.key)} onset · ${s.start.toFixed(3)} s</title></circle><circle cx="${x(s.end)}" cy="${y(s.mean_energy)}" r="2.2" fill="#d68086"><title>${s.duration.toFixed(3)} s · ${s.frame_count} frames</title></circle>`;
  svg+=`<line class="playhead" x1="${left}" x2="${left}" y1="${top}" y2="${height-bottom}"/><rect class="chart-pointer" x="${left}" y="${top}" width="${plotW}" height="${plotH}" fill="transparent"/></svg>`;
  const container=$(energy?'energy-chart':'pitch-chart');container.innerHTML=svg;const tooltip=document.createElement('div');tooltip.className='chart-tooltip hidden';container.append(tooltip);const surface=container.querySelector('.chart-pointer');
  const hover=e=>{const bounds=container.querySelector('svg').getBoundingClientRect(),xx=(e.clientX-bounds.left)/bounds.width*W,time=Math.max(0,Math.min(duration,(xx-left)/plotW*duration)),f=r.frames[Math.min(r.frames.length-1,Math.floor(time/(r.metadata.effective_hop_ms/1000)))];tooltip.textContent=`${time.toFixed(2)} s · ${noteName(f.key)} · ${f.frequency?f.frequency.toFixed(1)+' Hz':'unvoiced'} · ${(f.energy_ratio*100).toFixed(1)}% energy`;tooltip.style.left=Math.min(container.clientWidth-185,Math.max(0,e.clientX-bounds.left-80))+'px';tooltip.style.top='1px';tooltip.classList.remove('hidden');return time;};
  surface.addEventListener('pointermove',hover);surface.addEventListener('pointerleave',()=>tooltip.classList.add('hidden'));surface.addEventListener('click',e=>{$('player').currentTime=hover(e);});
 }
 chart('pitch',190);chart('energy',130);
}
function download(name,text,mime){const blob=new Blob([text],{type:mime}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function csvValue(value){if(value===null||value===undefined)return '';let s=String(value);if(typeof value==='string'&&/^[=+\-@]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
$('export-csv').addEventListener('click',()=>{const items=state.items.filter(i=>i.result),columns=['file',...metricInfo.map(x=>x[0])],rows=[columns,...items.map(i=>[i.file.name,...metricInfo.map(([k])=>i.result.metrics[k])])];download('phonipy-metrics.csv',rows.map(row=>row.map(csvValue).join(',')).join('\r\n'),'text/csv;charset=utf-8');});
$('export-json').addEventListener('click',()=>download('phonipy-report.json',JSON.stringify({version:VERSION,results:state.items.filter(i=>i.result).map(i=>i.result),errors:state.items.filter(i=>i.error).map(i=>({source:i.file.name,error:i.error}))},null,2),'application/json'));
$('audio-input').addEventListener('change',e=>addFiles(e.target.files));
for(const type of ['dragenter','dragover'])$('dropzone').addEventListener(type,e=>{e.preventDefault();$('dropzone').classList.add('dragover');});for(const type of ['dragleave','drop'])$('dropzone').addEventListener(type,e=>{e.preventDefault();$('dropzone').classList.remove('dragover');if(type==='drop')addFiles(e.dataTransfer.files);});
$('analyze').addEventListener('click',analyze);$('cancel').addEventListener('click',()=>{state.epoch++;stopWorker();setBusy(false);showError('Analysis cancelled. Completed recordings remain available until you clear this workspace.');});
$('clear').addEventListener('click',clearWorkspace);$('clear-footer').addEventListener('click',clearWorkspace);window.addEventListener('pagehide',clearWorkspace);
$('player').addEventListener('timeupdate',()=>{const duration=state.selected?.duration;if(!duration)return;const fraction=$('player').currentTime/duration;for(const line of document.querySelectorAll('.chart .playhead')){const x=42+fraction*(900-42-16);line.setAttribute('x1',x);line.setAttribute('x2',x);}const wave=$('waveform').querySelector('.playhead');if(wave){wave.setAttribute('x1',fraction*900);wave.setAttribute('x2',fraction*900);}});
$('method-open').addEventListener('click',()=>$('method').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}));
function showTab(name){for(const id of ['metrics','segments']){const yes=id===name;$(id+'-tab').setAttribute('aria-selected',String(yes));$(id+'-tab').tabIndex=yes?0:-1;visible(id+'-view',yes);}}
for(const name of ['metrics','segments']){$(name+'-tab').addEventListener('click',()=>showTab(name));$(name+'-tab').addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const next=name==='metrics'?'segments':'metrics';showTab(next);$(next+'-tab').focus();}});}
function invalidate(){for(const item of state.items)item.result=null;visible('results',false);visible('empty-state',true);refreshList();const min=+$('min-frames').value*+$('hop').value;$('hold-note').textContent=Number.isFinite(min)?fmt(min,Math.abs(min-Math.round(min))<1e-8?0:2)+' ms minimum stable hold':'Set a valid minimum hold';}
$('preset').addEventListener('change',()=>{const c=preset($('preset').value);$('fmin').value=c.fmin;$('fmax').value=c.fmax;$('window').value=c.window_ms;invalidate();});
for(const id of ['reference','min-frames','periodicity','fmin','fmax','window','hop','harmonics','channel'])$(id).addEventListener('change',invalidate);
$('version').textContent=VERSION;$('footer-version').textContent=VERSION;
