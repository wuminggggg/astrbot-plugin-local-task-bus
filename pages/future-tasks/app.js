const bridge = window.AstrBotPluginPage;
const $ = id => document.getElementById(id);
async function api(path, method='GET', body) {
  const fn = method === 'GET' ? bridge.apiGet : bridge.apiPost;
  return fn(path, body);
}
async function refresh() {
  const [callbacks, jobs] = await Promise.all([api('callbacks'), api('future-tasks')]);
  $('callback').innerHTML = (callbacks.callbacks || []).map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join('');
  $('jobs').innerHTML = (jobs.tasks || []).map(t => `<div class="job"><b>${esc(t.name)}</b> <span class="muted">${esc(t.mode)} · ${esc(t.summary)} · ${t.enabled?'启用':'停用'}</span><button data-del="${esc(t.id)}">删除</button></div>`).join('') || '<p>暂无任务</p>';
  document.querySelectorAll('[data-del]').forEach(b => b.onclick = async () => { await api(`future-tasks/${encodeURIComponent(b.dataset.del)}`,'POST',{action:'delete'}); refresh(); });
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
$('mode').onchange=()=>{$('timeFields').hidden=$('mode').value!=='time';$('behaviorFields').hidden=$('mode').value!=='behavior'};
$('refresh').onclick=()=>refresh().catch(e=>$('status').textContent=String(e));
$('create').onclick=async()=>{try{const payload=JSON.parse($('payload').value||'{}');const body={name:$('name').value,mode:$('mode').value,callback:$('callback').value,payload};if(body.mode==='time'){body.run_at=new Date($('runAt').value).toISOString();body.timezone=$('timezone').value}else{body.match_type=$('matchType').value;body.pattern=$('pattern').value;body.cooldown=Number($('cooldown').value);body.max_runs=Number($('maxRuns').value)}const r=await api('future-tasks','POST',body);$('status').textContent=r.error||'任务已创建';await refresh()}catch(e){$('status').textContent='创建失败：'+e}};
await bridge.ready();
refresh().catch(e=>$('status').textContent=String(e));
