/** PhoniPy nsdf-harmonic-v2. Pure numeric functions; no storage or network access. */
export const VERSION = '0.2.0';
export const DEFAULT_CONFIG = Object.freeze({sample_rate:16000,hop_ms:17.25,window_ms:69,min_frames:8,fmin:65,fmax:1100,reference_key:69,harmonics:12,min_rms_db:-60,min_periodicity:.65,min_energy_ratio:.15,max_flatness:.6,harmonic_bandwidth_hz:22,channel:'loudest',nonfinite:'error',max_duration:300});
export function preset(name='general') {
  const choices={general:{},low:{fmin:50,fmax:500,window_ms:86.25},high:{fmin:130,fmax:1400},speech:{fmin:65,fmax:600},singing:{fmin:50,fmax:1600,window_ms:86.25}};
  if(!(name in choices))throw Error('Unknown voice range.');
  return {...DEFAULT_CONFIG,...choices[name]};
}
export function validateConfig(config={}) {
  const c={...DEFAULT_CONFIG,...config};
  for(const [name,value] of Object.entries(c))if(typeof value==='number'&&!Number.isFinite(value))throw Error(`${name} must be finite.`);
  for(const k of ['sample_rate','min_frames','harmonics'])if(!Number.isInteger(c[k])||c[k]<1)throw Error(`${k} must be a positive integer.`);
  if(c.sample_rate<4000||c.sample_rate>192000)throw Error('Analysis sample rate is outside the supported range.');
  if(!(0<c.hop_ms&&c.hop_ms<=c.window_ms&&c.window_ms<=500)||Math.round(c.hop_ms*c.sample_rate/1000)<1)throw Error('Require 0 < hop ≤ window ≤ 500 ms.');
  if(!(20<=c.fmin&&c.fmin<c.fmax&&c.fmax<c.sample_rate/2))throw Error('Pitch range must lie between 20 Hz and the analysis Nyquist frequency.');
  if(c.window_ms*c.fmin/1000<2)throw Error('The window must contain at least two cycles of the lowest pitch.');
  for(const k of ['min_periodicity','min_energy_ratio','max_flatness'])if(c[k]<0||c[k]>1)throw Error(`${k} must be between 0 and 1.`);
  if(c.min_rms_db < -160||c.min_rms_db>0||c.harmonics>128||c.harmonic_bandwidth_hz<=0||c.max_duration<=0)throw Error('An advanced setting is outside its supported range.');
  if(!['loudest','mix','left','right'].includes(c.channel))throw Error('Invalid channel selection.');
  return c;
}
export const frequencyToKey=f=>69+12*Math.log2(f/440);
export const keyToFrequency=k=>440*2**((k-69)/12);
export function noteName(key) {if(key===null||!Number.isFinite(key))return '—';const n=Math.round(key), names=['C','C♯','D','E♭','E','F','F♯','G','A♭','A','B♭','B'];return names[((n%12)+12)%12]+(Math.floor(n/12)-1);}
export function fft(real, imag, inverse=false) {
  const n=real.length;
  for(let i=1,j=0;i<n;i++){let b=n>>1;for(;j&b;b>>=1)j^=b;j^=b;if(i<j){[real[i],real[j]]=[real[j],real[i]];[imag[i],imag[j]]=[imag[j],imag[i]];}}
  for(let size=2;size<=n;size*=2){const angle=(inverse?2:-2)*Math.PI/size, wr0=Math.cos(angle),wi0=Math.sin(angle),half=size>>1;
    for(let i=0;i<n;i+=size){let wr=1,wi=0;for(let j=0;j<half;j++){const a=i+j,b=a+half,tr=wr*real[b]-wi*imag[b],ti=wr*imag[b]+wi*real[b];real[b]=real[a]-tr;imag[b]=imag[a]-ti;real[a]+=tr;imag[a]+=ti;const next=wr*wr0-wi*wi0;wi=wr*wi0+wi*wr0;wr=next;}}}
  if(inverse)for(let i=0;i<n;i++){real[i]/=n;imag[i]/=n;}
}
function detector(c) {
  const size=Math.round(c.window_ms*c.sample_rate/1000),nfft=2**Math.ceil(Math.log2(4*size)),window=Float64Array.from({length:size},(_,i)=>.5-.5*Math.cos(2*Math.PI*i/(size-1)));
  const minLag=Math.max(1,Math.ceil(c.sample_rate/c.fmax)),maxLag=Math.min(size-2,Math.floor(c.sample_rate/c.fmin)),bandwidth=Math.max(c.harmonic_bandwidth_hz,1.5*c.sample_rate/size);
  const real=new Float64Array(nfft),imag=new Float64Array(nfft),centered=new Float64Array(size),cumulative=new Float64Array(size+1),nsdf=new Float64Array(size),power=new Float64Array(nfft/2+1),mask=new Uint8Array(power.length);
  function detect(samples,start){
    let mean=0;for(let i=0;i<size;i++)mean+=samples[start+i]??0;mean/=size;
    let energy=0;cumulative[0]=0;for(let i=0;i<size;i++){const v=(samples[start+i]??0)-mean;centered[i]=v;energy+=v*v;cumulative[i+1]=energy;}
    const rms_db=Math.max(-300,20*Math.log10(Math.max(Math.sqrt(energy/size),1e-15)));
    const empty=(periodicity=0)=>({frequency:null,key:null,fractional_key:null,energy_ratio:0,periodicity,rms_db,accepted:false});
    if(rms_db<c.min_rms_db)return empty();
    real.fill(0);imag.fill(0);real.set(centered);fft(real,imag);
    for(let i=0;i<nfft;i++){real[i]=real[i]*real[i]+imag[i]*imag[i];imag[i]=0;}fft(real,imag,true);
    for(let i=0;i<size;i++){const d=cumulative[size-i]+energy-cumulative[i];nsdf[i]=d>1e-20?2*real[i]/d:0;}
    const peaks=[];for(let lag=minLag;lag<=maxLag;lag++){if(nsdf[lag]>nsdf[lag-1]){let right=lag;while(right+1<size&&nsdf[right+1]===nsdf[lag])right++;if(right+1<size&&nsdf[right]>nsdf[right+1]){const p=Math.floor((lag+right)/2);if(p<=maxLag)peaks.push(p);}lag=right;}}
    if(!peaks.length)return empty();
    const best=Math.max(...peaks.map(i=>nsdf[i]));if(best<c.min_periodicity)return empty(Math.max(0,best));
    const lag=peaks.find(i=>nsdf[i]>=Math.max(c.min_periodicity,.9*best)),a=nsdf[lag-1],b=nsdf[lag],d=nsdf[lag+1],divisor=a-2*b+d;
    const adjustment=Math.abs(divisor)>1e-15?.5*(a-d)/divisor:0,frequency=c.sample_rate/(lag+Math.max(-.5,Math.min(.5,adjustment)));
    real.fill(0);imag.fill(0);for(let i=0;i<size;i++)real[i]=centered[i]*window[i];fft(real,imag);
    let total=0;for(let i=0;i<power.length;i++){power[i]=(real[i]*real[i]+imag[i]*imag[i])*(i>0&&i<power.length-1?2:1);total+=power[i];}
    if(total<=1e-20)return empty(best);
    mask.fill(0);const width=Math.min(bandwidth,.35*frequency),step=c.sample_rate/nfft;
    for(let h=1;h<=c.harmonics;h++){const target=h*frequency;if(target>=c.sample_rate/2)break;const left=Math.max(0,Math.ceil((target-width)/step)),right=Math.min(power.length-1,Math.floor((target+width)/step));for(let i=left;i<=right;i++)mask[i]=1;}
    let series=0,sum=0,logs=0,count=0;for(let i=0;i<power.length;i++){if(mask[i])series+=power[i];if(i*step>=c.fmin){sum+=power[i];logs+=Math.log(power[i]+1e-30);count++;}}
    const ratio=Math.max(0,Math.min(1,series/total)),flatness=Math.exp(logs/count)/(sum/count+1e-30),fractional_key=frequencyToKey(frequency);
    return {frequency,key:Math.floor(fractional_key+.5),fractional_key,energy_ratio:ratio,periodicity:Math.min(1,best),rms_db,accepted:frequency>=c.fmin&&frequency<=c.fmax&&ratio>=c.min_energy_ratio&&flatness<=c.max_flatness};
  }
  return {size,nfft,detect};
}
export function segmentFrames(frames,minFrames=8){
  const segments=[];let run=[];
  const close=()=>{if(run.length>=minFrames){let energy=0,pitch=0,weight=0;for(const f of run){const d=f.end-f.start;energy+=d*f.energy_ratio;pitch+=d*f.fractional_key;weight+=d;}segments.push({key:run[0].key,start:run[0].start,end:run.at(-1).end,duration:run.at(-1).end-run[0].start,mean_energy:energy/weight,mean_fractional_key:pitch/weight,frame_count:run.length});}run=[];};
  for(const f of frames){if(run.length&&(!f.accepted||f.key!==run.at(-1).key||Math.abs(f.start-run.at(-1).end)>1e-8))close();if(f.accepted)run.push(f);}close();return segments;
}
export function computeMetrics(segments,rawDuration,reference=69){
  const n=segments.length;
  if(!n)return {raw_duration:rawDuration,active_time:0,valid_time:0,average_offset:null,average_energy:null,hoarseness:null,average_duration:null,continuity:0,sparsity:0,breakouts:0};
  const valid=segments.reduce((s,x)=>s+x.duration,0),active=segments.at(-1).end-segments[0].start,energy=segments.reduce((s,x)=>s+x.duration*x.mean_energy,0)/valid,average=valid/n;
  return {raw_duration:rawDuration,active_time:active,valid_time:valid,average_offset:segments.reduce((s,x)=>s+x.mean_fractional_key-reference,0)/n,average_energy:energy,hoarseness:(1-energy)*100,average_duration:average,continuity:average/valid,sparsity:Math.min(1,valid/active),breakouts:n};
}
export function analyzeSamples(samples,config={},options={}){
  const c=validateConfig(config),duration=options.duration??samples.length/c.sample_rate;
  if(!samples.length||!Number.isFinite(duration)||duration<=0)throw Error('The recording is empty.');
  if(duration>c.max_duration)throw Error(`The recording exceeds the ${c.max_duration/60}-minute analysis limit.`);
  for(const x of samples)if(!Number.isFinite(x))throw Error('The audio contains invalid samples. Convert it to PCM WAV and try again.');
  const d=detector(c),hop=Math.round(c.sample_rate*c.hop_ms/1000),frames=[];
  for(let start=0;start<samples.length;start+=hop){const time=start/c.sample_rate;if(time>=duration)break;frames.push({start:time,end:Math.min((start+hop)/c.sample_rate,duration),...d.detect(samples,start)});if(options.progress&&frames.length%80===0)options.progress(Math.min(1,start/samples.length));}
  const segments=segmentFrames(frames,c.min_frames),warnings=[...(options.warnings??[])];
  if(!segments.length)warnings.push('No stable-note intervals met these settings. Try a longer vowel hold or adjust the pitch range. Undefined averages are shown as a dash.');
  return {source:options.source??'<array>',metrics:computeMetrics(segments,duration,c.reference_key),segments,frames,config:c,metadata:{version:VERSION,detector:'nsdf-harmonic-v2',analysis_sample_rate:c.sample_rate,effective_hop_ms:1000*hop/c.sample_rate,effective_window_ms:1000*d.size/c.sample_rate,fft_size:d.nfft,key_numbering:'MIDI: A4=69',frame_count:frames.length,...options.metadata},warnings};
}
