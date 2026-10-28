/* Connection manager: local drafts never cross provider boundaries. */
window.ModelSettings = (() => {
  const $ = id => document.getElementById(id);
  let api, presets=[], catalog={connections:[]}, selectedId=null, category='all';
  let requestId=null, requestSignature=null, locked=false, changing=false;
  const drafts=new Map();
  const ai=()=>({provider:$('provider').value,base_url:$('base_url').value,model:$('model').value,apikey:$('apikey').value});
  const snapshot=()=>({ai:ai(),name:$('connectionName').value});
  const signature=()=>JSON.stringify(ai());
  const draftKey=()=>selectedId?'saved:'+selectedId:'preset:'+$('provider').value;
  const remember=()=>drafts.set(draftKey(),snapshot());
  function message(text,error=false){$('connectionResult').textContent=text;$('connectionResult').style.color=error?'#b42318':'';}
  function fill(value){
    for(const k of ['provider','base_url','model','apikey']) $(k).value=value.ai[k]??(k==='provider'?'custom':'');
    $('connectionName').value=value.name;
    $('base_url').readOnly=false;$('model').readOnly=false;
    $('advanced').open=$('provider').value==='custom';
    const preset=presets.find(p=>p.id===$('provider').value);
    $('providerHint').textContent=(preset?.hint||'使用兼容 OpenAI Chat Completions 的接口。')+' 模型和接口均可修改。';
    $('modelName').textContent=$('model').value||'选择模型';
    $('availableModels').replaceChildren();
    $('modelToolResult').textContent='';requestId=null;requestSignature=null;
    renderCards();renderSaved();
  }
  function selectPreset(id,fresh=false){
    if(locked||changing)return;
    remember();selectedId=null;
    const preset=presets.find(p=>p.id===id);
    fill(!fresh&&drafts.has('preset:'+id)?drafts.get('preset:'+id):{
      name:preset.label,ai:{provider:id,base_url:preset.base_url,model:preset.model,apikey:''}});
    message('新连接；填好后点击“保存并使用此连接”。');
  }
  function renderCards(){
    const query=$('providerSearch').value.trim().toLowerCase();
    $('providerCards').replaceChildren();
    const matches=presets.filter(p=>(category==='all'||p.category===category)&&[p.label,p.aliases,p.base_url].join(' ').toLowerCase().includes(query));
    for(const p of matches){
      const card=document.createElement('button');card.type='button';card.className='provider-card'+($('provider').value===p.id?' active':'');
      card.disabled=locked||changing;card.setAttribute('aria-pressed',String($('provider').value===p.id));
      const title=document.createElement('strong');title.textContent=p.label;
      const detail=document.createElement('small');detail.textContent=p.id==='custom'?'填写自己的 API 接口':p.protocol;card.append(title,detail);
      card.onclick=()=>selectPreset(p.id);$('providerCards').append(card);
    }
    $('noProviders').hidden=matches.length>0;
    $('providerCategories').replaceChildren();
    for(const [id,label] of [['all','全部'],['official','官方服务'],['aggregator','聚合平台'],['custom','自定义']]){
      const button=document.createElement('button');button.type='button';button.className=category===id?'active':'';
      const count=presets.filter(p=>(id==='all'||p.category===id)&&[p.label,p.aliases,p.base_url].join(' ').toLowerCase().includes(query)).length;
      button.textContent=label+' '+count;button.onclick=()=>{category=id;renderCards()};$('providerCategories').append(button);
    }
  }
  function renderSaved(){
    $('savedConnections').replaceChildren();
    for(const row of catalog.connections){
      const button=document.createElement('button');button.type='button';button.className='connection-card'+(selectedId===row.id?' active':'');
      button.disabled=locked||changing;button.setAttribute('aria-pressed',String(selectedId===row.id));
      const name=document.createElement('strong');name.textContent=row.name;
      const detail=document.createElement('small');detail.textContent=row.model+(catalog.active_id===row.id?' · 当前使用':'');button.append(name,detail);
      button.onclick=async()=>{
        if(changing||locked)return;remember();changing=true;
        try{
          const result=await api.change_connection('activate',{id:row.id});
          if(!result.ok){message(result.message,true);return;}
          catalog=result.catalog;selectedId=row.id;
          fill(drafts.get('saved:'+row.id)||{name:result.selected.name,ai:result.selected.ai});
          message('已切换连接；重新获取试卷后用于后台任务。');
        }catch(_){message('切换失败，请重试。',true)}finally{changing=false;renderSaved();renderCards()}
      };
      $('savedConnections').append(button);
    }
    if(!catalog.connections.length){const p=document.createElement('p');p.className='provider-hint';p.textContent='尚未保存连接，先从下面选一个服务商。';$('savedConnections').append(p)}
  }
  async function save(){
    if(locked||changing)return false;changing=true;$('saveConnection').disabled=true;
    try{
      const result=await api.change_connection('save',{id:selectedId,name:$('connectionName').value,ai:ai()});
      if(!result.ok){message(result.message,true);return false;}
      selectedId=result.selected.id;catalog=result.catalog;
      fill({name:result.selected.name,ai:result.selected.ai});remember();
      message('已保存并使用；重新获取试卷后生效。');return true;
    }catch(_){message('保存失败，请重试。',true);return false}finally{changing=false;$('saveConnection').disabled=locked;renderSaved();renderCards()}
  }
  async function runTool(kind){
    if(locked)return;
    const initial=signature();$('modelToolResult').className='model-result full';$('modelToolResult').textContent=kind==='models'?'正在获取模型列表…':'正在检查连接与 JSON 输出…';
    try{
      const result=await api.start_model_tool(kind,ai());
      if(signature()!==initial)return;
      if(!result.ok){$('modelToolResult').textContent=result.message;$('modelToolResult').classList.add('error');return;}
      requestId=result.request_id;requestSignature=initial;
      update(await api.get_state());
    }catch(_){$('modelToolResult').textContent='请求未完成，请重试。'}
  }
  function update(state){
    locked=Boolean(state.busy);const tool=state.model_tools||{};
    for(const id of ['newConnection','saveConnection','connectionName','fetchModels','testModel']) $(id).disabled=locked||(changing&&id!=='connectionName')||(Boolean(tool.busy)&&['fetchModels','testModel'].includes(id));
    if(tool.request_id===requestId&&requestSignature===signature()&&!tool.busy){
      $('modelToolResult').textContent=tool.message||'';
      $('modelToolResult').className='model-result full '+(tool.ok?'success':'error');
      if(Array.isArray(tool.models)){
        $('availableModels').replaceChildren();
        for(const model of tool.models){const option=document.createElement('option');option.value=model;$('availableModels').append(option)}
      }
    }
    renderSaved();renderCards();
  }
  async function init(value,bridge){
    api=bridge;
    presets=[...await api.get_model_presets(),{id:'custom',label:'自定义兼容接口',category:'custom',aliases:'custom 中转 代理 自定义',base_url:'',model:''}];
    for(const p of presets){const option=document.createElement('option');option.value=p.id;option.textContent=p.label;$('provider').append(option)}
    catalog=await api.get_connections();selectedId=catalog.active_id;
    const row=catalog.connections.find(c=>c.id===selectedId);
    const provider=value.ai?.provider||(presets.find(p=>p.base_url.replace(/\/$/,'')===(value.ai?.base_url||'').replace(/\/$/,'')&&p.model===value.ai?.model)?.id||'custom');
    fill({name:row?.name||presets.find(p=>p.id===provider)?.label||'我的连接',ai:{...value.ai,provider}});
    $('providerSearch').oninput=renderCards;
    $('newConnection').onclick=()=>selectPreset($('provider').value,true);$('saveConnection').onclick=save;
    $('fetchModels').onclick=()=>runTool('models');$('testModel').onclick=()=>runTool('test');
    for(const id of ['apikey','base_url','model']) $(id).addEventListener('input',()=>{requestId=null;requestSignature=null;$('modelToolResult').textContent='';$('modelName').textContent=$('model').value||'选择模型'});
  }
  return {init,update,saveForSettings:()=>ai().apikey?save():Promise.resolve(true)};
})();
