window.AppUpdates=(()=>{
  const $=id=>document.getElementById(id);
  let bridge,lastStatus=null,lastVersion=null;
  async function call(method,...args){try{const r=await bridge[method](...args);if(r?.message)Notifications.show(r.message,{error:!r.ok})}catch(_){Notifications.show('更新操作未能完成，请重试。',{error:true})}}
  function init(api){bridge=api;$('checkUpdates').onclick=()=>call('check_updates');$('getUpdate').onclick=()=>call('download_update');$('cancelUpdate').onclick=()=>call('cancel_update');$('installUpdate').onclick=()=>call('install_update');$('openWebsite').onclick=()=>call('open_website');$('automaticUpdates').onchange=()=>call('set_update_automatic',$('automaticUpdates').checked)}
  function render(state){
    const u=state.updates;if(!u)return;
    $('appVersion').textContent='v'+u.current;$('updateMessage').textContent=u.message;
    $('automaticUpdates').checked=u.automatic;
    const downloading=u.status==='downloading',checking=u.status==='checking';
    $('checkUpdates').disabled=downloading||checking;$('checkUpdates').textContent=checking?'检查中…':'检查更新';
    $('checkUpdates').setAttribute('aria-busy',String(checking));
    $('getUpdate').hidden=!u.latest||!['available','error'].includes(u.status);
    $('getUpdate').textContent='下载 v'+u.latest;$('cancelUpdate').hidden=!downloading;
    $('installUpdate').hidden=u.status!=='ready';$('installUpdate').disabled=Boolean(state.busy);
    $('updateProgress').hidden=!downloading;$('updateFill').style.width=(u.progress||0)+'%';
    $('updateProgress').setAttribute('aria-valuenow',String(u.progress||0));
    $('updateNumbers').textContent=downloading?Math.round((u.received||0)/1048576)+' / '+Math.round(u.size/1048576)+' MB · '+(u.progress||0)+'%':'';
    $('updateNotes').hidden=!u.notes;$('updateNotesText').textContent=u.notes||'';
    if(u.status!==lastStatus||u.latest!==lastVersion){
      if(u.status==='ready')Notifications.show('新版已下载并通过校验，可在设置中安装。');
      else if(u.status==='error')Notifications.show(u.message,{error:true});
      lastStatus=u.status;lastVersion=u.latest;
    }
  }
  return {init,render};
})();
