const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const sessionId = (() => {
  try { let id=sessionStorage.getItem("agri_session"); if(!id){id=(crypto.randomUUID?.() || String(Date.now()));sessionStorage.setItem("agri_session",id)} return id; }
  catch { return "browser-session"; }
})();

const panel=$("#chatPanel"), launcher=$("#chatLauncher"), messages=$("#chatMessages");
function openChat(){panel?.classList.add("open");panel?.setAttribute("aria-hidden","false");launcher?.classList.add("hidden");setTimeout(()=>$("#chatInput")?.focus(),180)}
function closeChat(){panel?.classList.remove("open");panel?.setAttribute("aria-hidden","true");launcher?.classList.remove("hidden")}
launcher?.addEventListener("click",openChat);$("#chatClose")?.addEventListener("click",closeChat);
$$("[data-open-chat]").forEach(el=>el.addEventListener("click",e=>{e.preventDefault();openChat()}));
$("#menuToggle")?.addEventListener("click",()=>$("#mainNav")?.classList.toggle("nav-open"));
$$("[data-prompt]").forEach(b=>b.addEventListener("click",()=>{openChat();$("#chatInput").value=b.dataset.prompt;$("#chatForm").requestSubmit()}));

function addMessage(text, role, extra={}) {
  const div=document.createElement("div");div.className=`message ${role}`;
  // Text-only rendering avoids injecting model output as HTML.
  div.textContent=text;messages.appendChild(div);
  if(extra.ticket){const b=document.createElement("button");b.className="ticket-offer";b.textContent="Create a support ticket ↗";b.onclick=()=>showTicketForm(extra.question);div.appendChild(b)}
  messages.scrollTop=messages.scrollHeight;
}
$("#chatForm")?.addEventListener("submit",async e=>{
  e.preventDefault();const input=$("#chatInput"), message=input.value.trim();if(!message)return;
  addMessage(message,"user");input.value="";
  const pending=document.createElement("div");pending.className="message bot typing";pending.textContent="Looking into that…";messages.appendChild(pending);messages.scrollTop=messages.scrollHeight;
  try{
    const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message,session_id:sessionId})});
    const data=await r.json();pending.remove();addMessage(data.answer,"bot",{ticket:data.offer_ticket,question:message});
  }catch{pending.remove();addMessage("I couldn't reach the support service just now. Please retry, or create a support ticket.", "bot",{ticket:true,question:message})}
});
function showTicketForm(question){
  const wrap=document.createElement("form");wrap.className="ticket-form";
  wrap.innerHTML='<strong>Create a support ticket</strong><input name="name" placeholder="Your name (optional)" maxlength="120"><input name="email" type="email" placeholder="Email (optional)" maxlength="254"><textarea name="question" maxlength="2000" required></textarea><button class="btn btn-primary" type="submit">Submit ticket ↗</button>';
  wrap.elements.question.value=question;messages.appendChild(wrap);messages.scrollTop=messages.scrollHeight;
  wrap.addEventListener("submit",async e=>{e.preventDefault();const b=wrap.querySelector("button");b.disabled=true;b.textContent="Submitting…";
    try{const r=await fetch("/api/tickets",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:wrap.elements.name.value,email:wrap.elements.email.value,question:wrap.elements.question.value})});const d=await r.json();if(!r.ok)throw Error();wrap.remove();addMessage(`Ticket #${d.ticket_id} created. Status: ${d.status}. Keep this number for reference.`,"bot")}
    catch{b.disabled=false;b.textContent="Try again ↗";addMessage("The ticket could not be saved. Please try again later.","bot")}
  });
}
async function loadFaqs(){
  const list=$("#faqList");if(!list)return;let rows=[];
  try{const r=await fetch("/api/faqs");if(!r.ok)throw Error();rows=await r.json()}catch{list.textContent="The FAQ service is unavailable. Please try again later.";return}
  const categories=["all",...new Set(rows.map(x=>x.category))];let active="all";
  const cats=$("#faqCategories");cats.innerHTML="";
  categories.forEach(cat=>{const b=document.createElement("button");b.className="category"+(cat==="all"?" active":"");b.dataset.category=cat;b.innerHTML=`<span>${cat==="all"?"All topics":escapeHtml(cat)}</span><span>↗</span>`;b.addEventListener("click",()=>{active=cat;$$(".category",cats).forEach(x=>x.classList.toggle("active",x===b));render()});cats.appendChild(b)});
  function render(){const term=($("#faqSearch").value||"").toLowerCase();const filtered=rows.filter(x=>(active==="all"||x.category===active)&&`${x.question} ${x.answer} ${x.category}`.toLowerCase().includes(term));$("#faqCount").textContent=`${filtered.length} ANSWERS / ${rows.length} TOTAL`;list.innerHTML="";
    if(!filtered.length){list.innerHTML='<div class="loading-card">No matches yet. Try another search or ask Agri AI.</div>';return}
    filtered.forEach((x,i)=>{const d=document.createElement("details");d.className="faq-item";const s=document.createElement("summary");s.innerHTML=`<span class="faq-index">${String(i+1).padStart(2,"0")}</span><span class="faq-question">${escapeHtml(x.question)}<small>${escapeHtml(x.category)}</small></span><span class="faq-plus">+</span>`;const p=document.createElement("p");p.textContent=x.answer;d.append(s,p);list.appendChild(d)});
  }
  $("#faqSearch").addEventListener("input",render);render();
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function loadErrors(){
  const grid=$("#errorGrid");if(!grid)return;let rows=[];
  try{const r=await fetch("/api/errors");if(!r.ok)throw Error();rows=await r.json()}catch{grid.textContent="The error library is unavailable. Please try again later.";return}
  function render(){const q=($("#errorSearch").value||"").toLowerCase();const filtered=rows.filter(x=>`${x.code} ${x.title} ${x.explanation} ${x.solution}`.toLowerCase().includes(q));grid.innerHTML="";
    filtered.forEach(x=>{const card=document.createElement("article");card.className="error-card";const code=document.createElement("div");code.className="error-code";code.textContent=x.code;const label=document.createElement("span");label.className="error-label";label.textContent=x.code===460?"SITE-SPECIFIC":"HTTP STATUS";const h=document.createElement("h3");h.textContent=x.title;const p=document.createElement("p");p.textContent=x.explanation;const sol=document.createElement("div");sol.className="error-solution";const strong=document.createElement("strong");strong.textContent="TRY THIS";const sp=document.createElement("span");sp.textContent=x.solution;sol.append(strong,sp);card.append(code,label,h,p,sol);grid.appendChild(card)});
    if(!filtered.length)grid.textContent="No matching codes. Ask Agri AI for help.";
  }
  $("#errorSearch").addEventListener("input",render);render();
}
async function loadWeather(){const el=$("#weatherSummary");if(!el)return;try{const r=await fetch("/api/weather?city=Coimbatore");const d=await r.json();el.textContent=d.temperature_c==null?d.summary:`${d.temperature_c}°C · ${d.summary}`}catch{el.textContent="Live forecast unavailable · use local forecast"}}
$("#weatherRefresh")?.addEventListener("click",loadWeather);
loadFaqs();loadErrors();loadWeather();

const observer=new IntersectionObserver(entries=>entries.forEach(e=>{if(e.isIntersecting){e.target.classList.add("revealed");observer.unobserve(e.target)}}),{threshold:.08});
$$(".reveal, .feature-card, .faq-item, .error-card").forEach(el=>observer.observe(el));
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeChat();if(e.key==="/"&&!["INPUT","TEXTAREA"].includes(document.activeElement.tagName)){e.preventDefault();$("#faqSearch")?.focus()}});
