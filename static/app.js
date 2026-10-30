const $ = id => document.getElementById(id);
let busy = false;
function element(tag, text, cls) { const n=document.createElement(tag); n.textContent=text; if(cls)n.className=cls; return n; }
async function refresh(){
 if(busy)return; busy=true; $('refresh').disabled=true; $('refresh').textContent='获取中…';
 try{
  const response=await fetch('/api/route',{signal:AbortSignal.timeout(40000)});
  const data=await response.json();
  if(!Array.isArray(data.stops))throw new Error('invalid data');
  $('count').textContent=data.stops.length||'—'; $('vehicles').textContent=data.updated_at?data.vehicle_count:'—';
  $('updated').textContent=data.updated_at?new Date(data.updated_at).toLocaleTimeString('zh-CN',{timeZone:'Asia/Macau',hour12:false}):'尚未获取';
  $('status').textContent=data.error?(data.error+(data.updated_at?' 当前保留上次结果，数据已过期。':'')):'● 已获取官方数据 · 每 30 秒更新';
  $('status').className='notice'+(data.stale?' warning':'');
  $('stops').replaceChildren();
  for(const stop of data.stops){
   const row=element('li',''); row.append(element('span',String(stop.number).padStart(2,'0'),'number'));
   const info=element('div','','stop-info'); info.append(element('h3',stop.name),element('p',stop.code+(stop.lane?' · '+stop.lane:'')));
   if(stop.suspended)info.append(element('span','暂不停靠','warning'));
   row.append(info); const buses=element('div','','buses');
   for(const bus of stop.buses)buses.append(element('span','▣ '+(bus.code||bus.plate)+(bus.code&&bus.plate?' · '+bus.plate:''),'bus'));
   row.append(buses); $('stops').append(row);
  }
  if(!data.stops.length)$('stops').append(element('li','暂无数据，请稍后重试。','empty'));
 }catch(e){$('status').textContent='连接失败，请稍后重试。已有结果可能已过期。';$('status').className='notice warning';}
 finally{busy=false;$('refresh').disabled=false;$('refresh').textContent='刷新数据 ↻';}
}
$('refresh').addEventListener('click',refresh); refresh(); setInterval(()=>{if(!document.hidden)refresh();},30000);
