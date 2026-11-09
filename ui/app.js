// Pure journal view: both storage protocols remain intact in their original records.
globalThis.LocalLensJournal = (() => {
 const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const positive = n => typeof n === 'number' && Number.isFinite(n) && n > 0;
 function entries(state) {
  const rows = (state.history || []).map(r => ({
   id: 'manual:' + r.id, finished: r.finished_at, model: r.model.path.split(/[\\/]/).pop(),
   target: (r.target_requested || 'unknown').toUpperCase(), protocol: 'llama-bench',
   recommended: false, metrics: r.metrics.map(m => ({value: m.tokens_per_second, unit: 'tok/s', label: m.test + (typeof m.stddev === 'number' ? ` · ± ${m.stddev.toFixed(2)}` : '')})),
   note: /stories15m/i.test(r.model.path) ? 'Tiny integration-test model · not representative of a usable assistant.' : 'Synthetic token workload · excludes tokenization and sampling.',
   evidence: r
  }));
  for (const scan of state.scans || []) {
   (scan.attempts || []).forEach((a, i) => {
    if (a.status !== 'completed' || a.evidence !== 'measured' || !positive(a.generation_tokens_per_second)) return;
    const recommended = scan.device_scope === "current" && !!scan.recommendation && scan.recommendation.target === a.target && scan.recommendation.model.sha256 === a.model.sha256;
    const metrics = [{value: a.generation_tokens_per_second, unit: 'tok/s', label: 'Generation · average of 2 prompt tests'}];
    if (typeof a.minimum_free_ram_gib === 'number' && Number.isFinite(a.minimum_free_ram_gib)) metrics.push({value: a.minimum_free_ram_gib, unit: 'GiB free', label: 'Lowest system-memory headroom'});
    rows.push({id: 'scan:' + scan.id + ':' + i, finished: scan.finished_at, model: a.model.name + ' · ' + a.model.quantization,
     target: a.target.toUpperCase(), protocol: 'Real prompt · automatic scan', recommended, metrics,
     note: `${scan.device_scope==='current'?'This computer':scan.device_scope==='other'?'Other computer':'Device unverified'} · ${a.status_label || (a.comfortable ? 'Comfortable' : 'Below comfort target')} · 128 output tokens × 2 · ${a.context_tokens || 4096}-token context. ${scan.cleanup?.status === 'deleted' ? 'Temporary test files deleted; results retained.' : 'See evidence for cleanup status.'}`,
     evidence: {scan_id: scan.id, scan_status: scan.status, hardware: scan.hardware, prompt: scan.prompt, formatted_prompt: scan.formatted_prompt, cleanup: scan.cleanup, attempt: a}
    });
   });
  }
  return rows.sort((a,b) => (Date.parse(b.finished) || 0) - (Date.parse(a.finished) || 0));
 }
 function render(rows) {
  if (!rows.length) return '<div class="empty"><b>A clean slate.</b>Your measured manual and automatic tests will appear here. Compatibility estimates are never saved as scores.</div>';
  return rows.map(r => `<article class="card result ${r.recommended ? 'journal-recommended' : ''}"><div class="result-top"><div><h3>${escape(r.model)}</h3><span class="model-meta">${escape(new Date(r.finished).toLocaleString())} · ${escape(r.target)} · ${escape(r.protocol)}</span></div><span class="tag">${r.recommended ? 'MEASURED · RECOMMENDED' : 'MEASURED'}</span></div><div class="scores">${r.metrics.map(m => `<div><strong>${m.value.toFixed(2)}</strong> <span class="model-meta">${escape(m.unit)}</span><small>${escape(m.label)}</small></div>`).join('')}</div><p class="scan-note">${escape(r.note)}</p><details><summary>Inspect saved evidence & raw engine output</summary><pre>${escape(JSON.stringify(r.evidence,null,2))}</pre></details></article>`).join('');
 }
 return {entries, render};
})();
/* APPLICATION UI */
const $=id=>document.getElementById(id);let latest=null,first=true,historyKey=null,scanKey=null;
const esc=s=>String(s??'Unknown').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path,data){const r=await fetch('/api/'+path,{method:data?'POST':'GET',headers:{'X-LocalLens-Token':document.querySelector('meta[name=session-token]').content,'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});const j=await r.json();if(!r.ok)throw Error(j.error||r.statusText);return j}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,8000)}
function stat(label,value,detail){return `<div class="stat"><span class="label">${label}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></div>`}
function render(s){latest=s;const h=s.hardware; $('cpu-name').textContent=h.cpu;$('system-info').textContent=`${h.threads} logical processors · ${h.os}`;
$('stats').innerHTML=stat('SYSTEM MEMORY',h.ram_gib?`${h.ram_gib} GiB`:'Unavailable',`${h.available_gib??'Unknown'} GiB currently available`)+stat('GRAPHICS',h.gpus.length?`${h.gpus.length} detected`:'Unavailable',h.gpus.map(g=>g.Name).join(' · ')||'No adapter reported')+stat('NEURAL PROCESSOR',h.npus.length?'Detected':'Not detected',h.npus.map(n=>n.FriendlyName).join(' · ')||'Runtime check available below')+stat('MEASURED RUNS',s.history.length+(s.scans||[]).reduce((n,r)=>n+(r.attempts||[]).filter(a=>a.status==='completed').length,0),'Successful local measurements');
$('warnings').innerHTML=h.warnings.map(w=>`<p>${esc(w)}</p>`).join('');if(first){$('threads').value=Math.min(h.threads||4,16);first=false}
$('model-cards').innerHTML=s.advisor.map(m=>`<article class="model-card"><h3>${esc(m.name)}</h3><span class="model-meta">${m.parameters_b}B parameters · Q4-class assumption</span><span class="fit ${m.status==='Tight fit'?'tight':m.status==='Likely fits'?'':'no'}">${m.status==='Likely fits'?'◉':'◌'} ${esc(m.status)} · Estimated</span><div class="memory"><span>Approx. memory budget</span><b>${m.required_gib} GiB</b></div></article>`).join('');
const j=s.job,running=!!s.busy; renderAutomatic(s);$('run').disabled=running;$('cancel').disabled=!running;$('job-tag').textContent=running?'MEASURING · NO SCORE YET':j.status==='completed'?'MEASURED · SAVED':j.status==='failed'?'RUN FAILED':j.status==='cancelled'?'CANCELLED':'READY WHEN YOU ARE';$('status-icon').classList.toggle('running',running);$('job-title').textContent=running?'Let the model do the talking.':j.status==='completed'?'Evidence, now on record.':j.status==='failed'?'This run could not complete.':j.status==='cancelled'?'Run stopped.':'Your first result starts here.';if(j.message)$('job-message').textContent=j.message;
const journal=LocalLensJournal.entries(s);const hk=JSON.stringify(journal);if(hk!==historyKey){historyKey=hk;$('results').innerHTML=LocalLensJournal.render(journal);}
$('export').disabled=!s.history.length&&!(s.scans||[]).length}
async function refresh(){try{render(await api('state'))}catch(e){toast('Connection unavailable. Keep the LocalLens launcher running. '+e.message)}}
$('bench-form').onsubmit=async e=>{e.preventDefault();try{await api('run',{executable:$('executable').value.trim().replace(/^"|"$/g,''),model:$('model').value.trim().replace(/^"|"$/g,''),threads:Number($('threads').value),target:$('target').value});await refresh()}catch(e){toast(e.message)}};
$('cancel').onclick=async()=>{try{await api('cancel',{});await refresh()}catch(e){toast(e.message)}};
$('refresh').onclick=async()=>{const b=$('refresh');b.disabled=true;b.textContent='Reading hardware…';try{await api('refresh',{});await refresh()}catch(e){toast(e.message)}finally{b.disabled=false;b.textContent='↻ Refresh hardware'}};
$('probe').onclick=async()=>{const b=$('probe');b.disabled=true;$('npu-message').textContent='Checking the optional OpenVINO runtime…';try{const p=await api('openvino');$('npu-message').textContent=`${p.status.toUpperCase()}: ${p.message} Devices: ${(p.devices||[]).join(', ')||'none'}. NPU benchmarking is not implemented in this MVP.`}catch(e){$('npu-message').textContent=e.message}finally{b.disabled=false}};
$('export').onclick=()=>{const blob=new Blob([JSON.stringify({schema_version:'1.0',results:latest.history,automatic_scans:latest.scans||[]},null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='locallens-results.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
document.querySelectorAll('nav a').forEach(a=>a.onclick=()=>{document.querySelector('nav .active')?.classList.remove('active');a.classList.add('active')});refresh();setInterval(refresh,2500);

function renderAutomatic(s){
const p=$('auto-thorough').checked?s.thorough_plan:s.auto_plan;if(!p)return;const scans=s.scans||[],j=s.job,isAuto=j.kind==='automatic',busy=!!s.busy;
$('auto-start').disabled=busy||!p.candidates.length;$('hero-auto').disabled=busy||!p.candidates.length;$('auto-thorough').disabled=busy;$('auto-cancel').disabled=!busy||!isAuto||j.status==='cancelled';
$('auto-plan').textContent=p.candidates.length?`Starts with ${p.candidates[0].name} · ${(p.first_download_bytes/1e9).toFixed(2)} GB first download · up to ${(p.max_download_bytes/1e9).toFixed(2)} GB if smaller models are needed. Keeps at least ${p.reserve_gib.toFixed(1)} GiB free. Downloads from GitHub and Hugging Face; inference stays on your PC. Temporary files are deleted; the small report stays.`:'Close other apps to free enough memory for a comfortable test.';
$('auto-stage').textContent=isAuto?(j.status==='running'?(j.stage||j.status):j.status).toUpperCase():'READY TO DISCOVER';
$('auto-message').textContent=isAuto?(j.status==='cancelled'&&scans.some(r=>r.device_scope==='current'&&r.recommendation)?'Test stopped. Your last measured recommendation is kept below.':j.message):'No file paths. No manual setup.';
const progress=$('auto-progress');progress.hidden=!isAuto||!busy||j.download_percent==null;if(!progress.hidden)progress.value=j.download_percent;
const key=JSON.stringify(scans.map(r=>[r.id,r.finished_at]));if(key===scanKey)return;scanKey=key;
$('auto-results').innerHTML=scans.slice(0,3).map(r=>{const rec=r.device_scope==='current'?r.recommendation:null,clean=r.cleanup?.status==='deleted';return `<article class="card recommendation"><span class="tag">${rec?'MEASURED · RECOMMENDED':esc((r.status||'finished').toUpperCase())}</span><h3>${rec?esc(rec.model.name)+' · '+esc(rec.model.quantization):r.device_scope!=='current'?'Saved scan · device unverified or different':'No comfortable model confirmed.'}</h3>${rec?`<div class="scores"><div><strong>${rec.generation_tokens_per_second.toFixed(1)}</strong> <span class="model-meta">tok/s</span><small>Measured generation · ${esc(rec.target.toUpperCase())}</small></div><div><strong>${rec.minimum_free_ram_gib.toFixed(1)}</strong> <span class="model-meta">GiB free</span><small>Lowest system headroom during test</small></div></div><p class="scan-note">${esc(rec.reason)}<br>${esc(rec.scope)}</p>`:`<p class="scan-note">${esc(r.outcome||'The test did not finish.')}</p>`}<p class="scan-note">${clean?'✓ Test models and engine deleted.':r.cleanup?.status==='failed'?'Cleanup needs attention: '+esc(r.cleanup.path)+' · '+esc(r.cleanup.message):'No temporary downloads left by this attempt.'} Only your results and engine logs are retained.</p>${(r.attempts||[]).map(a=>`<div class="scan-row"><span>${esc(a.model.name)} · ${esc(a.target.toUpperCase())}</span><b>${a.status==='completed'?a.generation_tokens_per_second.toFixed(1)+' tok/s · '+esc(a.status_label):'Unavailable · '+esc(a.error)}</b></div>`).join('')}<details class="scan-details"><summary>Prompt, generated samples & full evidence</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details></article>`}).join('');
}
async function startAutomatic(){const b=$('auto-start');b.disabled=true;try{$('automatic').scrollIntoView({behavior:'smooth'});await api('auto',{mode:$('auto-thorough').checked?'thorough':'quick'});await refresh()}catch(e){toast(e.message);b.disabled=false}};
$('auto-cancel').onclick=async()=>{try{await api('cancel',{});await refresh()}catch(e){toast(e.message)}};

$('auto-thorough').onchange=()=>{if(latest)renderAutomatic(latest)};

$('auto-start').onclick=startAutomatic; $('hero-auto').onclick=startAutomatic;

function syncNavigation(){document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.getAttribute('href')===(location.hash||'#overview')))}
window.addEventListener('hashchange',syncNavigation);syncNavigation();
