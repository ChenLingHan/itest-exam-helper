/* Connection manager: local drafts never cross provider boundaries. */
window.ModelSettings = (() => {
  const $ = id => document.getElementById(id);
  let api, presets=[], catalog={connections:[]}, selectedId=null, category='all';
  let requestId=null, requestSignature=null, requestKind=null, locked=false, changing=false;
  let models=[], appliedRequest=null, accountRequest=null, accountSignature=null, accountKind=null;
  const checks={browser:{state:'idle',detail:''},account:{state:'idle',detail:''},model:{state:'idle',detail:''}};
  const drafts=new Map();
  const ai=()=>({provider:$('provider').value,base_url:$('base_url').value,model:$('model').value,apikey:$('apikey').value});
  const snapshot=()=>({ai:ai(),name:$('connectionName').value});
  const signature=(kind=requestKind)=>JSON.stringify(kind==='models'?{provider:ai().provider,base_url:ai().base_url,apikey:ai().apikey}:ai());
  const accountValue=()=>({username:$('username').value,password:$('password').value});
  function showModels(open){$('modelPicker').hidden=!open;$('toggleModels').setAttribute('aria-expanded',String(open));if(open)renderModels()}
  function renderModels(){const query=$('modelSearch').value.trim().toLowerCase();const filtered=models.filter(m=>m.toLowerCase().includes(query));$('modelOptions').replaceChildren();$('modelCount').textContent='共 '+models.length+' 个模型，当前显示 '+filtered.length+' 个';$('noModels').hidden=filtered.length>0;for(const id of filtered){const option=document.createElement('button');option.type='button';option.className='model-option';option.setAttribute('role','option');option.setAttribute('aria-selected',String(id===$('model').value));option.textContent=id;option.disabled=locked;option.onclick=()=>{$('model').value=id;$('model').dispatchEvent(new Event('input'));showModels(false);$('model').focus()};$('modelOptions').append(option)}}
  function clearModels(){models=[];$('modelSearch').value='';$('modelOptions').replaceChildren();$('toggleModels').disabled=locked||!ai().apikey.trim();$('toggleModels').textContent='获取模型';showModels(false)}
  const draftKey=()=>selectedId?'saved:'+selectedId:'preset:'+$('provider').value;
  const remember=()=>drafts.set(draftKey(),snapshot());
  function message(text,error=false){$('connectionResult').textContent=text;$('connectionResult').style.color=error?'#b42318':'';}
  function renderChecks(){
    const config=[['browser','testBrowser','browserTestResult','browserReady','检查浏览器','✓ 浏览器正常','停止检查','重新检查','浏览器'],['account','testAccount','accountTestResult','accountReady','验证登录','✓ 登录已通过','停止验证','重新验证','账号'],['model','testModel','modelToolResult','modelReady','验证模型','✓ 模型可用','验证中…','重新验证','模型']];
    for(const [key,buttonId,resultId,readyId,idle,passed,running,error,label] of config){
      const check=checks[key],button=$(buttonId);
      button.classList.toggle('is-success',check.state==='passed');button.classList.toggle('is-error',check.state==='error');button.classList.toggle('is-running',check.state==='running');
      button.textContent=check.state==='passed'?passed:check.state==='running'?running:check.state==='error'?error:idle;
      button.title=check.detail||(key==='model'?'发送少量请求验证模型，可能消耗 Token':'可随时点击重新检查');
      button.setAttribute('aria-label',label+'：'+(check.state==='passed'?'已通过':check.state==='running'?'正在检查':check.state==='error'?'未通过':'待检查'));
      if(key!=='model'||check.state!=='idle'){
        $(resultId).textContent=check.detail;$(resultId).className='check-detail '+(check.state==='passed'?'success':check.state==='error'?'error':'');
      }
      const ready=$(readyId);ready.classList.toggle('passed',check.state==='passed');ready.classList.toggle('failed',check.state==='error');
      ready.textContent=label+(check.state==='passed'?'已通过':check.state==='running'?'检查中':check.state==='error'?'需重试':'待检查');
    }
  }
  function resetModelCheck(){checks.model={state:'idle',detail:''};renderChecks()}
  function fill(value){
    const previous=JSON.stringify(ai());
    for(const k of ['provider','base_url','model','apikey']) $(k).value=value.ai[k]??(k==='provider'?'custom':'');
    if(!presets.some(p=>p.id===$('provider').value))$('provider').value='custom';
    $('connectionName').value=value.name;
    $('base_url').readOnly=false;$('model').readOnly=false;
    $('advanced').open=$('provider').value==='custom';
    if(previous!==JSON.stringify(ai()))resetModelCheck();
    const preset=presets.find(p=>p.id===$('provider').value);
    $('providerHint').textContent=(preset?.hint||'使用兼容 OpenAI Chat Completions 的接口。')+' 模型和接口均可修改。';
    $('modelName').textContent=$('model').value||'选择模型';
    clearModels();
    $('modelToolResult').textContent='';requestId=null;requestSignature=null;
    renderCards();renderSaved();
  }
  function selectPreset(id,fresh=false){
    if(locked||changing)return;
    remember();selectedId=null;
    const preset=presets.find(p=>p.id===id);
    fill(!fresh&&drafts.has('preset:'+id)?drafts.get('preset:'+id):{
      name:preset.label,ai:{provider:id,base_url:preset.base_url,model:preset.model,apikey:''}});
    message('新配置，填写后保存设置');
  }
  function renderCards(){
    $('providerCards').replaceChildren();
    for(const p of presets){
      const card=document.createElement('button');card.type='button';card.className='provider-card'+($('provider').value===p.id?' active':'');
      card.disabled=locked||changing;card.setAttribute('aria-pressed',String($('provider').value===p.id));card.title=p.hint||'填写自己的模型服务地址';
      const title=document.createElement('strong');title.textContent=p.id==='custom'?'自定义':p.id==='kimi'?'Kimi':p.id==='zhipu'?'GLM':p.label;
      card.append(title);card.onclick=()=>selectPreset(p.id);$('providerCards').append(card);
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
          message('已切换，重新获取试卷后生效');
        }catch(_){message('切换失败，请重试。',true)}finally{changing=false;renderSaved();renderCards()}
      };
      $('savedConnections').append(button);
    }
    if(!catalog.connections.length){const p=document.createElement('p');p.className='provider-hint';p.textContent='选择服务商，填写密钥后保存即可。';$('savedConnections').append(p)}
  }
  async function save(){
    if(locked||changing)return false;changing=true;$('saveConnection').disabled=true;
    try{
      const result=await api.change_connection('save',{id:selectedId,name:$('connectionName').value,ai:ai()});
      if(!result.ok){message(result.message,true);return false;}
      selectedId=result.selected.id;catalog=result.catalog;
      fill({name:result.selected.name,ai:result.selected.ai});remember();
      message('模型配置已保存');return true;
    }catch(_){message('保存失败，请重试。',true);return false}finally{changing=false;$('saveConnection').disabled=locked;renderSaved();renderCards()}
  }
  async function runTool(kind){
    if(locked)return;
    const initial=signature(kind);if(kind==='test'){checks.model={state:'running',detail:''};renderChecks()}$('modelToolResult').className='check-detail';$('modelToolResult').textContent=kind==='models'?'正在获取模型列表…':'正在检查连接与 JSON 输出…';
    try{
      const result=await api.start_model_tool(kind,ai());
      if(signature(kind)!==initial)return;
      if(!result.ok){if(kind==='test'){checks.model={state:'error',detail:result.message};renderChecks()}else{$('modelToolResult').textContent=result.message;$('modelToolResult').className='check-detail error'}return;}
      requestId=result.request_id;requestSignature=initial;requestKind=kind;
      update(await api.get_state());
    }catch(_){if(kind==='test'){checks.model={state:'error',detail:'请求未完成，请重试。'};renderChecks()}else{$('modelToolResult').textContent='请求未完成，请重试。'}}
  }
  function update(state){
    locked=Boolean(state.busy);const tool=state.model_tools||{};
    const account=state.account_test||{};
    $('fetchModels').textContent=tool.busy&&tool.kind==='models'?'获取中…':'刷新';
    $('testBrowser').disabled=locked&&!(account.busy&&account.browser_only);
    $('testAccount').disabled=locked&&(!account.busy||account.browser_only);
    if(account.busy){const key=account.browser_only?'browser':'account';checks[key].state='running'}
    if(account.request_id===accountRequest&&(accountKind==='browser'||accountSignature===JSON.stringify(accountValue()))&&!account.busy){
      checks[accountKind]={state:account.ok?'passed':'error',detail:account.message||''};
      if(accountKind==='account'&&account.ok)checks.browser={state:'passed',detail:'已在本次登录验证中成功启动浏览器'};
      accountRequest=null;
    }
    renderChecks();
    $('toggleModels').disabled=locked||Boolean(tool.busy)||!ai().apikey.trim();
    for(const id of ['newConnection','saveConnection','connectionName','fetchModels','testModel']) $(id).disabled=locked||(changing&&id!=='connectionName')||(Boolean(tool.busy)&&['fetchModels','testModel'].includes(id));
    if(tool.request_id===requestId&&requestSignature===signature()&&!tool.busy&&tool.request_id!==appliedRequest){
      appliedRequest=tool.request_id;
      $('modelToolResult').textContent=tool.message||'';
      $('modelToolResult').className='check-detail '+(tool.ok?'success':'error');
      if(tool.kind==='test'){checks.model={state:tool.ok?'passed':'error',detail:tool.message||''};renderChecks()}
      if(Array.isArray(tool.models)){
        models=[...tool.models];$('modelSearch').value='';
        $('toggleModels').textContent='选择模型';
        $('toggleModels').disabled=locked||Boolean(tool.busy)||!ai().apikey.trim();showModels(models.length>0);
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
    $('newConnection').onclick=()=>selectPreset($('provider').value,true);$('saveConnection').onclick=save;
    $('fetchModels').onclick=()=>runTool('models');$('testModel').onclick=()=>runTool('test');
    $('toggleModels').onclick=()=>models.length?showModels($('modelPicker').hidden):runTool('models');
    $('modelSearch').oninput=renderModels;
    $('modelPicker').addEventListener('keydown',event=>{if(event.key==='Escape'){showModels(false);$('toggleModels').focus()}});
    for(const id of ['apikey','base_url']) $(id).addEventListener('input',()=>{requestId=null;requestSignature=null;clearModels();$('toggleModels').disabled=locked||!ai().apikey.trim();$('modelToolResult').textContent='';resetModelCheck()});
    $('model').addEventListener('input',()=>{if(requestKind==='test'){requestId=null;requestSignature=null;$('modelToolResult').textContent=''}$('modelName').textContent=$('model').value||'选择模型';resetModelCheck();renderModels()});
    for(const id of ['username','password'])$(id).addEventListener('input',()=>{if(accountKind==='account'){accountRequest=null;accountSignature=null}checks.account={state:'idle',detail:''};renderChecks()});
    const runAccountCheck=async(browserOnly=false)=>{
      try{
        const state=await api.get_state();
        if(state.account_test?.busy){await api.dispatch({action:'stop'});return;}
        const value=accountValue();const initial=JSON.stringify(value);
        const key=browserOnly?'browser':'account';checks[key]={state:'running',detail:browserOnly?'正在准备驱动并打开 Edge…':'正在验证登录，如出现验证码，请在浏览器中完成。'};renderChecks();
        const result=browserOnly?await api.start_browser_test():await api.start_account_test(value);
        if(JSON.stringify(accountValue())!==initial)return;
        if(!result.ok){checks[key]={state:'error',detail:result.message};renderChecks();return;}
        accountRequest=result.request_id;accountSignature=initial;accountKind=key;update(await api.get_state());
      }catch(_){checks[browserOnly?'browser':'account']={state:'error',detail:'检查未能启动，请重试。'};renderChecks()}
    };
    $('testAccount').onclick=()=>runAccountCheck(false);
    $('testBrowser').onclick=()=>runAccountCheck(true);

  }
  return {init,update,saveForSettings:()=>ai().apikey?save():Promise.resolve(true)};
})();
