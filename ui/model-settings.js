/* Connection manager: local drafts never cross provider boundaries. */
window.ModelSettings = (() => {
  const $ = id => document.getElementById(id);
  let api, presets=[], catalog={connections:[]}, selectedId=null;
  let requestId=null, requestSignature=null, requestKind=null, locked=false, changing=false;
  let models=[], appliedRequest=null, accountRequest=null, accountSignature=null, accountKind=null;
  const checks={browser:{state:'idle',detail:''},account:{state:'idle',detail:''},model:{state:'idle',detail:''}};
  const drafts=new Map();
  let lastModelInput=null,lastAccountInput=null;
  const ai=()=>({provider:$('provider').value,base_url:$('base_url').value,model:$('model').value,apikey:$('apikey').value});
  const snapshot=()=>({id:selectedId,ai:ai()});
  const signature=(kind=requestKind)=>JSON.stringify(kind==='models'?{provider:ai().provider,base_url:ai().base_url,apikey:ai().apikey}:ai());
  const accountValue=()=>({username:$('username').value,password:$('password').value});
  function showModels(open){$('modelPicker').hidden=!open;$('toggleModels').setAttribute('aria-expanded',String(open));if(open)renderModels()}
  function renderModels(){const query=$('modelSearch').value.trim().toLowerCase();const filtered=models.filter(m=>m.toLowerCase().includes(query));$('modelOptions').replaceChildren();$('modelCount').textContent='共 '+models.length+' 个模型，当前显示 '+filtered.length+' 个';$('noModels').hidden=filtered.length>0;for(const id of filtered){const option=document.createElement('button');option.type='button';option.className='model-option';option.setAttribute('role','option');option.setAttribute('aria-selected',String(id===$('model').value));option.textContent=id;option.disabled=locked;option.onclick=()=>{$('model').value=id;$('model').dispatchEvent(new Event('input'));showModels(false);$('model').focus()};$('modelOptions').append(option)}}
  function clearModels(){models=[];$('modelSearch').value='';$('modelOptions').replaceChildren();$('toggleModels').disabled=locked||!ai().apikey.trim();$('toggleModels').textContent='获取模型';showModels(false)}
  const remember=()=>drafts.set($('provider').value,snapshot());
  function message(text,error=false){Notifications.show(text,{error});}
  function renderChecks(){
    const config=[['browser','testBrowser','browserTestResult','browserReady','检查浏览器','✓ 浏览器正常','停止检查','重新检查','浏览器'],['account','testAccount','accountTestResult','accountReady','验证登录','✓ 登录已通过','停止验证','重新验证','账号'],['model','testModel','modelToolResult','modelReady','验证模型','✓ 模型可用','验证中…','重新验证','模型']];
    for(const [key,buttonId,resultId,readyId,idle,passed,running,error,label] of config){
      const check=checks[key],button=$(buttonId);
      button.classList.toggle('is-success',check.state==='passed');button.classList.toggle('is-error',check.state==='error');button.classList.toggle('is-running',check.state==='running');
      button.textContent=check.state==='passed'?passed:check.state==='running'?running:check.state==='error'?error:idle;
      button.title=check.detail||(key==='model'?'发送少量请求验证模型，可能消耗 Token':'可随时点击重新检查');
      button.setAttribute('aria-label',label+'：'+(check.state==='passed'?'已通过':check.state==='running'?'正在检查':check.state==='error'?'未通过':'待检查'));
      button.setAttribute('aria-busy',String(check.state==='running'));
      $(key+'CheckProgress').hidden=check.state!=='running';
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
    selectedId=value.id??null;
    $('base_url').readOnly=false;$('model').readOnly=false;
    $('advanced').open=$('provider').value==='custom';
    if(previous!==JSON.stringify(ai()))resetModelCheck();
    lastModelInput=JSON.stringify(ai());
    const preset=presets.find(p=>p.id===$('provider').value);
    $('providerHint').textContent=(preset?.hint||'使用兼容 OpenAI Chat Completions 的接口。')+' 模型和接口均可修改。';
    $('modelName').textContent=$('model').value||'选择模型';
    clearModels();
    $('modelToolResult').textContent='';requestId=null;requestSignature=null;
    renderCards();
    $('page-settings').dispatchEvent(new Event('change'));
  }
  async function selectPreset(id){
    if(locked||changing||id===$('provider').value)return;
    remember();changing=true;renderCards();$('page-settings').dispatchEvent(new Event('change'));
    try{
      const preset=presets.find(p=>p.id===id);
      let value=drafts.get(id);
      if(!value){
        const saved=catalog.connections.filter(row=>(presets.some(p=>p.id===row.provider)?row.provider:'custom')===id);
        const row=saved.find(row=>row.id===catalog.active_id)||saved.at(-1);
        if(row){
          const result=await api.get_connection(row.id);
          if(!result.ok){message(result.message,true);return;}
          value={id:row.id,ai:{...result.selected.ai,provider:id}};
        }else value={id:null,ai:{provider:id,base_url:preset.base_url,model:preset.model,apikey:''}};
      }
      fill(value);
    }catch(_){message('读取服务商设置失败，请重试。',true)}
    finally{changing=false;renderCards();$('page-settings').dispatchEvent(new Event('change'))}
  }
  function renderCards(){
    $('providerCards').replaceChildren();
    for(const p of presets){
      const card=document.createElement('button');card.type='button';card.className='provider-card'+($('provider').value===p.id?' active':'');
      card.disabled=locked||changing;card.setAttribute('aria-pressed',String($('provider').value===p.id));card.title=p.hint||'填写自己的模型服务地址';
      const title=document.createElement('strong');title.textContent=p.id==='custom'?'自定义':p.id==='kimi'?'Kimi':p.id==='zhipu'?'GLM':p.label;
      const logo=document.createElementNS('http://www.w3.org/2000/svg','svg');logo.classList.add('provider-logo');logo.setAttribute('aria-hidden','true');
      const use=document.createElementNS(logo.namespaceURI,'use');use.setAttribute('href',p.id==='custom'?'#i-settings':'#brand-'+p.id);logo.append(use);
      card.append(logo,title);card.onclick=()=>selectPreset(p.id);$('providerCards').append(card);
    }
  }
  async function save(){
    if(locked||changing)return false;changing=true;$('page-settings').dispatchEvent(new Event('change'));
    try{
      const existing=catalog.connections.find(row=>row.id===selectedId);
      const name=existing?.name||presets.find(p=>p.id===ai().provider)?.label||'我的模型';
      const result=await api.change_connection('save',{id:selectedId,name,ai:ai()});
      if(!result.ok){message(result.message,true);return false;}
      catalog=result.catalog;fill({id:result.selected.id,ai:result.selected.ai});remember();return true;
    }catch(_){message('保存失败，请重试。',true);return false}
    finally{changing=false;renderCards();$('page-settings').dispatchEvent(new Event('change'))}
  }
  async function runTool(kind){
    if(locked)return;
    const initial=signature(kind);if(kind==='test'){checks.model={state:'running',detail:''};renderChecks()}$('modelToolResult').className='check-detail';$('modelToolResult').textContent=kind==='models'?'正在获取模型列表…':'正在检查连接与 JSON 输出…';
    try{
      const result=await api.start_model_tool(kind,ai());
      if(signature(kind)!==initial)return;
      if(!result.ok){Notifications.show(result.message,{error:true});if(kind==='test'){checks.model={state:'error',detail:result.message};renderChecks()}else{$('modelToolResult').textContent=result.message;$('modelToolResult').className='check-detail error'}return;}
      requestId=result.request_id;requestSignature=initial;requestKind=kind;
      update(await api.get_state());
    }catch(_){Notifications.show('请求未完成，请重试。',{error:true});if(kind==='test'){checks.model={state:'error',detail:'请求未完成，请重试。'};renderChecks()}else{$('modelToolResult').textContent='请求未完成，请重试。'}}
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
      Notifications.show(account.message||'检查已结束',{error:!account.ok,key:'account:'+account.request_id});
      if(accountKind==='account'&&account.ok)checks.browser={state:'passed',detail:'已在本次登录验证中成功启动浏览器'};
      accountRequest=null;
    }
    renderChecks();
    $('toggleModels').disabled=locked||Boolean(tool.busy)||!ai().apikey.trim();
    for(const id of ['fetchModels','testModel']) $(id).disabled=locked||changing||(Boolean(tool.busy)&&['fetchModels','testModel'].includes(id));
    if(tool.request_id===requestId&&requestSignature===signature()&&!tool.busy&&tool.request_id!==appliedRequest){
      appliedRequest=tool.request_id;
      Notifications.show(tool.message||'请求已完成',{error:!tool.ok,key:'model:'+tool.request_id});
      $('modelToolResult').textContent=tool.message||'';
      $('modelToolResult').className='check-detail '+(tool.ok?'success':'error');
      if(tool.kind==='test'){checks.model={state:tool.ok?'passed':'error',detail:tool.message||''};renderChecks()}
      if(Array.isArray(tool.models)){
        models=[...tool.models];$('modelSearch').value='';
        $('toggleModels').textContent='选择模型';
        $('toggleModels').disabled=locked||Boolean(tool.busy)||!ai().apikey.trim();showModels(models.length>0);
      }
    }
    renderCards();
  }
  async function init(value,bridge){
    api=bridge;
    lastAccountInput=JSON.stringify({username:value.username??'',password:value.password??''});
    presets=[...await api.get_model_presets(),{id:'custom',label:'自定义兼容接口',category:'custom',aliases:'custom 中转 代理 自定义',base_url:'',model:''}];
    for(const p of presets){const option=document.createElement('option');option.value=p.id;option.textContent=p.label;$('provider').append(option)}
    catalog=await api.get_connections();selectedId=catalog.active_id;
    const row=catalog.connections.find(c=>c.id===selectedId);
    const provider=value.ai?.provider||(presets.find(p=>p.base_url.replace(/\/$/,'')===(value.ai?.base_url||'').replace(/\/$/,'')&&p.model===value.ai?.model)?.id||'custom');
    fill({id:row?.id??null,ai:{...value.ai,provider}});
    $('fetchModels').onclick=()=>runTool('models');$('testModel').onclick=()=>runTool('test');
    $('toggleModels').onclick=()=>models.length?showModels($('modelPicker').hidden):runTool('models');
    $('modelSearch').oninput=renderModels;
    $('modelPicker').addEventListener('keydown',event=>{if(event.key==='Escape'){showModels(false);$('toggleModels').focus()}});
    for(const id of ['apikey','base_url']) $(id).addEventListener('input',()=>{const current=JSON.stringify(ai());if(current===lastModelInput)return;lastModelInput=current;requestId=null;requestSignature=null;clearModels();$('toggleModels').disabled=locked||!ai().apikey.trim();$('modelToolResult').textContent='';resetModelCheck()});
    $('model').addEventListener('input',()=>{const current=JSON.stringify(ai());if(current===lastModelInput)return;lastModelInput=current;if(requestKind==='test'){requestId=null;requestSignature=null;$('modelToolResult').textContent=''}$('modelName').textContent=$('model').value||'选择模型';resetModelCheck();renderModels()});
    for(const id of ['username','password'])$(id).addEventListener('input',()=>{const current=JSON.stringify(accountValue());if(current===lastAccountInput)return;lastAccountInput=current;if(accountKind==='account'){accountRequest=null;accountSignature=null}checks.account={state:'idle',detail:''};renderChecks()});
    const runAccountCheck=async(browserOnly=false)=>{
      try{
        const state=await api.get_state();
        if(state.account_test?.busy){await api.dispatch({action:'stop'});return;}
        const value=accountValue();const initial=JSON.stringify(value);
        const key=browserOnly?'browser':'account';checks[key]={state:'running',detail:browserOnly?'正在准备驱动并打开 Edge…':'正在验证登录，如出现验证码，请在浏览器中完成。'};renderChecks();
        const result=browserOnly?await api.start_browser_test():await api.start_account_test(value);
        if(!browserOnly&&JSON.stringify(accountValue())!==initial)return;
        if(!result.ok){Notifications.show(result.message,{error:true});checks[key]={state:'error',detail:result.message};renderChecks();return;}
        accountRequest=result.request_id;accountSignature=initial;accountKind=key;update(await api.get_state());
      }catch(_){Notifications.show('检查未能启动，请重试。',{error:true});checks[browserOnly?'browser':'account']={state:'error',detail:'检查未能启动，请重试。'};renderChecks()}
    };
    $('testAccount').onclick=()=>runAccountCheck(false);
    $('testBrowser').onclick=()=>runAccountCheck(true);

  }
  return {init,update,isChanging:()=>changing,saveForSettings:()=>{if(ai().apikey.trim())return save();if(catalog.active_id){message('请填写所选服务商的 API Key 后再保存。',true);return Promise.resolve(false)}return Promise.resolve(true)}};
})();
