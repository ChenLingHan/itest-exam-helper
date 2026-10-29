/* Transient notices stay above the page; confirmation prompts require a choice. */
window.Notifications = (() => {
  const root = document.getElementById('toastRegion');
  const active = new Map();
  const seen = new Set();
  const panel = document.getElementById('notice');
  let modalId=null;
  panel.addEventListener('cancel',event=>{
    event.preventDefault();
    document.getElementById('dismiss').click();
  });
  function show(text, {error=false, key=null, duration=error?8000:4200}={}) {
    if (!text || (key && seen.has(key))) return;
    if (key) { seen.add(key); if(seen.size>200) seen.delete(seen.values().next().value); }
    while(active.size>=3) active.values().next().value.close();
    const card=document.createElement('div');card.className='toast '+(error?'error':'success');
    card.setAttribute('role',error?'alert':'status');
    const mark=document.createElement('span');mark.className='toast-mark';mark.textContent=error?'!':'✓';mark.setAttribute('aria-hidden','true');
    const message=document.createElement('span');message.className='toast-text';message.textContent=text;
    const button=document.createElement('button');button.className='toast-close';button.type='button';button.textContent='×';button.setAttribute('aria-label','关闭提示');
    let timer,remaining=duration,started;
    function close(){clearTimeout(timer);active.delete(card);card.remove()}
    function pause(){clearTimeout(timer);if(started){remaining-=performance.now()-started;started=null}}
    function resume(){if(card.matches(':hover')||card.contains(document.activeElement))return;started=performance.now();timer=setTimeout(close,Math.max(0,remaining))}
    button.onclick=close;card.onmouseenter=pause;card.onmouseleave=resume;
    card.onfocusin=pause;card.onfocusout=()=>setTimeout(resume,0);
    card.append(mark,message,button);root.append(card);active.set(card,{close});resume();
  }
  function clear(){for(const item of active.values())item.close()}
  function backend(notice){
    if(!notice?.confirm){
      if(panel.open)panel.close();panel.hidden=true;modalId=null;
      if(notice)show(notice.text,{error:notice.error,key:'notice:'+notice.id});
      return;
    }
    if(notice.confirm){
      clear();panel.classList.toggle('error',notice.error);
      document.getElementById('noticeMessage').textContent=notice.text;
      document.getElementById('confirm').hidden=false;
      document.getElementById('confirm').textContent=notice.label;
      document.getElementById('dismiss').textContent='取消';
      panel.hidden=false;
      if(!panel.open)panel.showModal();
      if(modalId!==notice.id){modalId=notice.id;document.getElementById('dismiss').focus()}
    }
  }
  return {show,backend,clear};
})();
