(function () {
  if (window.__ddMarriageMounted) return;
  window.__ddMarriageMounted = true;
  var token = null, model = null, tab = "marriage", timer = null, busy = false;
  var goods = ["سکه","چوب","سنگ","آهن","غذا","اسب جنگی","خز","پشم","شراب","ادویه","آهن سیاه","نمک"];
  var levels = {
    ordinary:{label:"🥂 معمولی",coins:200,food:150,wine:5,bonus:5,days:3},
    noble:{label:"🍷 اشرافی",coins:600,food:400,wine:15,bonus:12,days:6},
    royal:{label:"👑 سلطنتی",coins:1500,food:1000,wine:40,bonus:22,days:10}
  };
  function esc(v){return String(v==null?"":v).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
  function fmt(v){if(!v)return "تعیین نشده";var d=new Date(v);return isNaN(d.getTime())?"تعیین نشده":d.toLocaleString("fa-IR",{dateStyle:"medium",timeStyle:"short"});}
  function localDT(d){var x=new Date(d.getTime()-d.getTimezoneOffset()*60000);return x.toISOString().slice(0,16);}
  function savedToken(){
    try{
      var keys=["dd_marriage_token","authToken","auth_token","sessionToken","session_token","gameToken","game_token","token"];
      for(var i=0;i<keys.length;i++){var v=localStorage.getItem(keys[i]);if(v&&v.length>30)return v;}
      for(var j=0;j<localStorage.length;j++){var k=localStorage.key(j),v2=localStorage.getItem(k);if(/token/i.test(k||"")&&v2&&v2.length>30&&v2.length<500)return v2;}
    }catch(e){}
    return null;
  }
  async function auth(){
    if(token)return token;
    token=savedToken();
    var tg=window.Telegram&&window.Telegram.WebApp;
    if(tg&&tg.initData){
      try{tg.ready();}catch(e){}
      var r=await fetch("/api/auth/telegram",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({init_data:tg.initData})});
      var j=await r.json();
      if(!r.ok||!j.token)throw new Error(j.error==="account_not_found"?"حساب شما هنوز توسط مدیر فعال نشده است.":"ورود تلگرام ناموفق بود.");
      token=j.token;try{localStorage.setItem("dd_marriage_token",token);}catch(e){}
    }
    if(!token)throw new Error("برای استفاده از این بخش، بازی را از حساب تلگرام خود باز کنید.");
    return token;
  }
  async function api(path,opts){
    await auth();opts=opts||{};
    var r=await fetch(path,{method:opts.method||"GET",headers:{"Content-Type":"application/json","Authorization":"Bearer "+token},body:opts.body});
    var j=await r.json().catch(function(){return {};});
    if(r.status===401){token=null;throw new Error("نشست شما منقضی شده است؛ بازی را دوباره باز کنید.");}
    if(!r.ok||j.ok===false){
      var messages={insufficient_ceremony_resources:"منابع لازم برای این مراسم کافی نیست.",ceremony_must_be_at_least_10_minutes_ahead:"زمان مراسم باید دست‌کم ۱۰ دقیقه بعد باشد.",ceremony_date_too_far:"زمان مراسم نمی‌تواند بیش از ۳۰ روز آینده باشد.",ceremony_already_chosen:"مراسم قبلاً ثبت شده است.",insufficient_gift_stock:"موجودی کافی برای این هدیه ندارید.",male_to_female_only:"فقط شخصیت مرد می‌تواند درخواست ازدواج بفرستد."};
      throw new Error(messages[j.error]||j.error||"عملیات انجام نشد.");
    }
    return j;
  }
  var css = "#ddw-launch{position:fixed;z-index:2147483000;right:18px;bottom:92px;border:1px solid #caa85b;border-radius:999px;background:linear-gradient(135deg,#2d2118,#594021);color:#fff4d6;padding:12px 17px;font:700 14px system-ui;box-shadow:0 8px 28px #0007;cursor:pointer}"+
  "#ddw-back{position:fixed;inset:0;z-index:2147483001;background:#080706df;display:none;align-items:center;justify-content:center;padding:10px;font-family:system-ui}"+
  "#ddw-panel{width:min(920px,96vw);max-height:94vh;overflow:auto;background:linear-gradient(160deg,#211b16,#151310);color:#f8edda;border:1px solid #96743d;border-radius:18px;box-shadow:0 24px 80px #000b;direction:rtl}#ddw-panel *{box-sizing:border-box}"+
  ".ddw-head{position:sticky;top:0;background:#211b16f5;border-bottom:1px solid #5c482b;padding:14px 17px;display:flex;align-items:center;justify-content:space-between;z-index:2}.ddw-title{font-size:19px;font-weight:900;color:#f4d48b}.ddw-sub,.ddw-muted{font-size:12px;color:#b9a98d;line-height:1.9}.ddw-close,.ddw-tab,.ddw-btn{border:1px solid #79613a;border-radius:9px;padding:8px 12px;background:#33291d;color:#f8edda;cursor:pointer;font:inherit}.ddw-tabs{display:flex;gap:7px;padding:11px 15px;border-bottom:1px solid #443725;overflow:auto}.ddw-tab[aria-selected=true]{background:#88652d;color:white}.ddw-body{padding:14px;display:grid;gap:12px}.ddw-card,.ddw-item{border:1px solid #59472d;border-radius:13px;padding:12px;background:linear-gradient(145deg,#292117,#201a14)}.ddw-card h3{font-size:15px;margin:0 0 10px;color:#f2d69c}.ddw-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:9px}.ddw-field{display:grid;gap:5px;font-size:12px;color:#c9b895}.ddw-field input,.ddw-field select{width:100%;min-height:39px;border:1px solid #705a37;border-radius:8px;background:#15120f;color:#fff0d3;padding:7px;font:inherit}.ddw-btn{background:linear-gradient(135deg,#9a7434,#6e4e22);border-color:#c5a15a;font-weight:800;margin:4px 2px}.ddw-danger{background:#4a2621;border-color:#8e4b3c}.ddw-pill{display:inline-block;border:1px solid #79613a;border-radius:999px;padding:3px 8px;font-size:11px;color:#f4d99f}.ddw-empty{padding:15px;text-align:center;color:#b9aa91;border:1px dashed #655236;border-radius:11px;font-size:13px}.ddw-error{color:#ffb3a8;background:#47251f;border:1px solid #87483a;border-radius:9px;padding:9px;font-size:12px}.ddw-ok{color:#c7efc7;background:#1d3826;border:1px solid #416b4a;border-radius:9px;padding:9px;font-size:12px}.ddw-list{display:grid;gap:8px}@media(max-width:560px){#ddw-launch{right:12px;bottom:78px;padding:10px 13px}#ddw-panel{max-height:96vh}.ddw-body{padding:9px}.ddw-head{padding:11px}.ddw-title{font-size:16px}}";
  var style=document.createElement("style");style.textContent=css;document.head.appendChild(style);
  var launch=document.createElement("button");launch.id="ddw-launch";launch.textContent="💍 ازدواج";document.body.appendChild(launch);
  var back=document.createElement("div");back.id="ddw-back";
  back.innerHTML='<section id="ddw-panel" role="dialog" aria-modal="true"><header class="ddw-head"><div><div class="ddw-title">💍 تالار پیوند خاندان‌ها</div><div class="ddw-sub">خواستگاری، مراسم، مهمانان و پیشکش‌ها</div></div><button class="ddw-close" id="ddw-close">×</button></header><nav class="ddw-tabs" id="ddw-tabs"><button class="ddw-tab" data-tab="marriage">ازدواج و مراسم</button><button class="ddw-tab" data-tab="invitations">دعوت‌نامه‌های من</button><button class="ddw-tab" data-tab="gifts">پیشکش‌ها</button></nav><main class="ddw-body" id="ddw-content"><div class="ddw-empty">در حال بارگذاری...</div></main></section>';
  document.body.appendChild(back);
  function card(title,body){return '<section class="ddw-card"><h3>'+title+'</h3>'+body+'</section>';}
  function status(s){return ({planning:"در انتظار برنامه‌ریزی",scheduled:"زمان‌بندی‌شده",live:"در حال برگزاری",completed:"پایان‌یافته"})[s]||"در انتظار برنامه‌ریزی";}
  function renderMarriage(){
    var own=model.my_characters||[],men=own.filter(function(x){return x.gender==="male"&&!x.spouse;}),brides=model.available_brides||[],html="";
    var form=men.length&&brides.length?'<div class="ddw-grid"><label class="ddw-field">شخصیت مرد شما<select id="ddw-groom">'+men.map(function(x){return '<option value="'+x.id+'">'+esc(x.character_name)+'</option>';}).join("")+'</select></label><label class="ddw-field">شخصیت زن بازیکن دیگر<select id="ddw-bride">'+brides.map(function(x){return '<option value="'+x.id+'">'+esc(x.character_name)+' — '+esc(x.player_name)+'</option>';}).join("")+'</select></label></div><button class="ddw-btn" id="ddw-propose">ارسال درخواست ازدواج</button>':'<div class="ddw-empty">برای خواستگاری باید شخصیت مرد مجرد داشته باشید و بازیکن دیگری شخصیت زن آزاد داشته باشد.</div>';
    html+=card("ارسال درخواست ازدواج",form);
    var incoming=model.incoming||[];
    html+=card("درخواست‌های دریافتی",incoming.length?'<div class="ddw-list">'+incoming.map(function(x){return '<div class="ddw-item"><b>'+esc(x.groom_name)+'</b><div class="ddw-muted">از سوی '+esc(x.groom_player_name)+'</div><button class="ddw-btn" data-proposal="'+x.id+'" data-decision="accept">پذیرفتن</button><button class="ddw-btn ddw-danger" data-proposal="'+x.id+'" data-decision="reject">رد درخواست</button></div>';}).join("")+'</div>':'<div class="ddw-empty">درخواست جدیدی ندارید.</div>');
    var outgoing=model.outgoing||[];
    html+=card("درخواست‌های ارسال‌شده",outgoing.length?'<div class="ddw-list">'+outgoing.map(function(x){return '<div class="ddw-item"><b>'+esc(x.bride_name)+'</b><div class="ddw-muted">'+esc(x.bride_player_name)+' · '+esc(({pending:"در انتظار پاسخ",accepted:"پذیرفته‌شده",rejected:"ردشده"})[x.status]||x.status)+'</div></div>';}).join("")+'</div>':'<div class="ddw-empty">درخواستی ارسال نکرده‌اید.</div>');
    var marriages=model.marriages||[];
    html+=card("ازدواج‌ها و برنامه مراسم",marriages.length?'<div class="ddw-list">'+marriages.map(function(m){
      var c=levels[m.ceremony_level],guests=(model.guests||[]).filter(function(g){return Number(g.marriage_id)===Number(m.id);}),att=guests.filter(function(g){return g.response==="attending";});
      var schedule=!m.ceremony_level?'<div class="ddw-grid"><label class="ddw-field">سطح مراسم<select id="ddw-level-'+m.id+'"><option value="ordinary">🥂 معمولی — ۲۰۰ سکه</option><option value="noble">🍷 اشرافی — ۶۰۰ سکه</option><option value="royal">👑 سلطنتی — ۱۵۰۰ سکه</option></select></label><label class="ddw-field">تاریخ و ساعت<input type="datetime-local" id="ddw-date-'+m.id+'"></label><label class="ddw-field">مدت<select id="ddw-duration-'+m.id+'"><option value="30">۳۰ دقیقه</option><option value="60" selected>۱ ساعت</option><option value="120">۲ ساعت</option></select></label></div><div class="ddw-muted">زمان بر اساس ساعت محلی شما ثبت و با ساعت سرور برای همه مهمانان هماهنگ می‌شود. حداقل ۱۰ دقیقه تا شروع فاصله لازم است.</div><button class="ddw-btn" data-schedule="'+m.id+'">ثبت مراسم و زمان</button>':'';
      var details=c?c.label+' · '+c.coins+' سکه · '+c.food+' غذا · '+c.wine+' شراب · +'+c.bonus+'٪ رضایت به مدت '+c.days+' روز':"مراسم انتخاب نشده";
      var guestRows=guests.map(function(g){return '<div class="ddw-muted">• '+esc(g.player_name)+' — '+esc(({pending:"در انتظار پاسخ",attending:"حضور تأیید شد",declined:"رد کرده"})[g.response]||g.response)+'</div>';}).join("");
      return '<div class="ddw-item"><div><b>'+esc(m.groom_name)+' ♥ '+esc(m.bride_name)+'</b> <span class="ddw-pill">'+esc(status(m.ceremony_status))+'</span></div><div class="ddw-muted">'+esc(m.groom_house_name||"")+' × '+esc(m.bride_house_name||"")+'<br>'+details+'<br>زمان: '+fmt(m.scheduled_at||m.ceremony_at)+' · مدت: '+(m.duration_minutes||60)+' دقیقه<br>مهمانان تأییدشده: '+att.length+' از '+guests.length+'</div>'+schedule+(m.ceremony_level?'<button class="ddw-btn" data-invite="'+m.id+'">دعوت همه بازیکنان</button>'+guestRows+(m.ceremony_status==="live"?'<div class="ddw-ok">🎉 مراسم اکنون در حال برگزاری است.</div>':""):"")+'</div>';
    }).join("")+'</div>':'<div class="ddw-empty">پس از پذیرفته‌شدن درخواست، برنامه‌ریزی مراسم اینجا نمایش داده می‌شود.</div>');
    return html;
  }
  function renderInvitations(){
    var list=model.invitations||[];
    if(!list.length)return '<div class="ddw-empty">دعوت‌نامه‌ای برای شما ارسال نشده است.</div>';
    return '<div class="ddw-list">'+list.map(function(i){
      var c=levels[i.ceremony_level],details=c?c.label:"مراسم";
      var guests=(model.guests||[]).filter(function(g){return Number(g.marriage_id)===Number(i.marriage_id);});
      var attending=guests.filter(function(g){return g.response==="attending";});
      var guestRows=guests.map(function(g){return '<div class="ddw-muted">• '+esc(g.player_name)+' — '+esc(({pending:"در انتظار پاسخ",attending:"حاضر می‌شود",declined:"رد کرده"})[g.response]||g.response)+'</div>';}).join("");
      return '<div class="ddw-item"><b>'+esc(i.groom_name)+' ♥ '+esc(i.bride_name)+'</b> <span class="ddw-pill">'+esc(status(i.ceremony_status))+'</span><div class="ddw-muted">'+details+' · '+fmt(i.scheduled_at||i.ceremony_at)+' · مدت '+(i.duration_minutes||60)+' دقیقه<br>مهمانان تأییدشده: '+attending.length+' از '+guests.length+'</div>'+(i.response==="pending"?'<button class="ddw-btn" data-invitation="'+i.id+'" data-response="attending">قبول دعوت</button><button class="ddw-btn ddw-danger" data-invitation="'+i.id+'" data-response="declined">رد دعوت</button>':'<span class="ddw-pill">'+(i.response==="attending"?"حضور تأیید شده":"دعوت رد شده")+'</span>')+(i.ceremony_status==="live"?'<div class="ddw-ok">🎉 مراسم اکنون زنده است؛ مهمانان حاضر را در فهرست زیر ببینید.</div>':"")+'<div class="ddw-list">'+guestRows+'</div>'+(i.response!=="declined"?'<div class="ddw-grid"><label class="ddw-field">هدیه<select id="ddw-gift-item-'+i.id+'">'+goods.map(function(g){return '<option>'+esc(g)+'</option>';}).join("")+'</select></label><label class="ddw-field">تعداد<input id="ddw-gift-qty-'+i.id+'" type="number" min="1" max="1000000" value="1"></label></div><button class="ddw-btn" data-gift="'+i.id+'">ارسال پیشکش</button>':"")+'</div>';
    }).join("")+'</div>';
  }
  function renderGifts(){
    var gifts=model.gifts||[];
    return gifts.length?'<div class="ddw-list">'+gifts.map(function(g){return '<div class="ddw-item"><b>'+esc(g.sender_name)+'</b><div class="ddw-muted">'+esc(g.item_name)+' × '+Number(g.quantity).toLocaleString("fa-IR")+' · '+fmt(g.created_at)+'</div></div>';}).join("")+'</div>':'<div class="ddw-empty">هنوز پیشکشی ثبت نشده است.</div>';
  }
  function render(){
    document.querySelectorAll(".ddw-tab").forEach(function(b){b.setAttribute("aria-selected",String(b.dataset.tab===tab));});
    var content=document.getElementById("ddw-content");
    if(!model){content.innerHTML='<div class="ddw-empty">اطلاعات در دسترس نیست.</div>';return;}
    content.innerHTML=tab==="marriage"?renderMarriage():(tab==="invitations"?renderInvitations():renderGifts());
    content.querySelectorAll('input[type="datetime-local"]').forEach(function(input){
      if(!input.value){var d=new Date(Date.now()+60*60*1000);d.setMinutes(Math.ceil(d.getMinutes()/5)*5,0,0);input.value=localDT(d);input.min=localDT(new Date(Date.now()+10*60*1000));}
    });
  }
  async function refresh(){model=await api("/api/marriage");render();}
  function error(e){var box=document.getElementById("ddw-content");box.insertAdjacentHTML("afterbegin",'<div class="ddw-error">'+esc(e.message||e)+'</div>');}
  async function action(fn){
    if(busy)return;busy=true;
    try{await fn();await refresh();}catch(e){error(e);}finally{busy=false;}
  }
  launch.addEventListener("click",async function(){
    back.style.display="flex";document.getElementById("ddw-content").innerHTML='<div class="ddw-empty">در حال دریافت اطلاعات...</div>';
    try{await refresh();}catch(e){error(e);}
    if(timer)clearInterval(timer);timer=setInterval(function(){if(back.style.display==="flex"&&!busy)refresh().catch(function(){});},12000);
  });
  document.getElementById("ddw-close").addEventListener("click",function(){back.style.display="none";if(timer)clearInterval(timer);});
  back.addEventListener("click",function(e){if(e.target===back){back.style.display="none";if(timer)clearInterval(timer);}});
  document.getElementById("ddw-tabs").addEventListener("click",function(e){var b=e.target.closest("[data-tab]");if(!b)return;tab=b.dataset.tab;render();});
  document.getElementById("ddw-content").addEventListener("click",function(e){
    var b=e.target.closest("button");if(!b)return;
    if(b.id==="ddw-propose")return action(function(){return api("/api/marriage/proposals",{method:"POST",body:JSON.stringify({groom_profile_id:Number(document.getElementById("ddw-groom").value),bride_profile_id:Number(document.getElementById("ddw-bride").value)})});});
    if(b.dataset.proposal)return action(function(){return api("/api/marriage/proposals/"+b.dataset.proposal+"/respond",{method:"POST",body:JSON.stringify({decision:b.dataset.decision})});});
    if(b.dataset.invitation&&b.dataset.response)return action(function(){return api("/api/marriage/invitations/"+b.dataset.invitation+"/respond",{method:"POST",body:JSON.stringify({response:b.dataset.response})});});
    if(b.dataset.schedule)return action(function(){
      var id=b.dataset.schedule,raw=document.getElementById("ddw-date-"+id).value;
      if(!raw)throw new Error("تاریخ و ساعت مراسم را انتخاب کنید.");
      return api("/api/marriage/"+id+"/ceremony",{method:"POST",body:JSON.stringify({level:document.getElementById("ddw-level-"+id).value,scheduled_at:new Date(raw).toISOString(),duration_minutes:Number(document.getElementById("ddw-duration-"+id).value)})});
    });
    if(b.dataset.invite)return action(function(){return api("/api/marriage/"+b.dataset.invite+"/invite",{method:"POST",body:"{}"});});
    if(b.dataset.gift)return action(function(){
      var id=b.dataset.gift,q=Number(document.getElementById("ddw-gift-qty-"+id).value);
      if(!Number.isInteger(q)||q<1||q>1000000)throw new Error("تعداد هدیه معتبر نیست.");
      return api("/api/marriage/invitations/"+id+"/gift",{method:"POST",body:JSON.stringify({item_name:document.getElementById("ddw-gift-item-"+id).value,quantity:q})});
    });
  });
})();