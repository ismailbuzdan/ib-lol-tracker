"use strict";
const $=id=>document.getElementById(id);
const demo={rank:{tier:"EMERALD",division:"III",lp:72},season_win_rate:60,session:{wins:4,losses:2,lp_delta:48},matches:[["Ahri",11,3,8,true,29],["Yasuo",5,7,6,false,34],["Jinx",13,2,10,true,31],["Zed",9,6,4,true,26],["Lux",2,8,12,false,37]].map(([champion,k,d,a,win,duration])=>({champion,k,d,a,win,duration,queue:"SOLO"}))};
function render(s){
 const d=s.mode==="demo"?demo:s;
 $("mode").textContent=s.mode.toUpperCase();$("mode").classList.toggle("active",s.mode==="live");
 $("tier").textContent=d.rank?d.rank.tier+" "+d.rank.division:"UNRANKED";
 $("lp").textContent=d.rank?d.rank.lp+" LP":"— LP";
 const change=d.session?.lp_delta;
 $("delta").textContent=change==null?"LP TRACKING":(change>0?"+":"")+change+" LP";
 $("delta").style.color=change<0?"#ff709e":"#6bebbb";
 $("wins").textContent=d.session?.wins??0;$("losses").textContent=d.session?.losses??0;
 $("rate").textContent=d.season_win_rate==null?"—":d.season_win_rate+"%";
 $("matchScope").textContent=s.match_scope==="ranked"?"RANKED / LAST 5":"SOLO / LAST 5";
 const box=$("matches");box.replaceChildren();
 if(!d.matches?.length){const empty=document.createElement("p");empty.textContent="Henüz dereceli maç yok";box.append(empty);}
 for(const m of d.matches??[]){
  const item=document.createElement("div");item.className="match "+(m.win?"win":"loss");
  const info=document.createElement("div");info.className="match-info";
  const name=document.createElement("b");name.textContent=m.champion;
  const score=document.createElement("small");score.textContent=m.k+" / "+m.d+" / "+m.a;
  info.append(name,score);
  const result=document.createElement("div");result.className="result";
  const outcome=document.createElement("b");outcome.textContent=m.win?"VICTORY":"DEFEAT";
  const mins=document.createElement("small");mins.textContent=m.duration+" MIN";
  result.append(outcome,mins);item.append(info,result);box.append(item);
 }
 $("updated").textContent=s.updated?new Date(s.updated).toLocaleTimeString("tr-TR",{hour:"2-digit",minute:"2-digit"}):"PREVIEW ONLY";
 if($("notice"))$("notice").textContent=s.error||(s.mode==="demo"?"Demo mode: add .env API key":"Riot API updating automatically");
}
async function poll(){try{const r=await fetch("/api/state",{cache:"no-store"});if(!r.ok)throw Error("Local server unavailable");render(await r.json());}catch(e){if($("notice"))$("notice").textContent=e.message;}}
$("reset")?.addEventListener("click",async()=>{if(!confirm("Yeni yayın oturumu başlatılsın mı?"))return;await fetch("/api/session/reset",{method:"POST"});poll();});poll();setInterval(poll,15000);
