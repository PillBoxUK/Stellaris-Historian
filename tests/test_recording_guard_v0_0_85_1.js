/* Headless browser-free recording modal interaction checks. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor(name) {this.name=name;this.hidden=true;this.disabled=false;this.textContent='';this.dataset={};this.listeners={};this.classList={add(){},remove(){}};}
  addEventListener(event, fn){this.listeners[event]=fn;}
  focus(){context.document.activeElement=this;}
  click(){this.listeners.click?.();}
  querySelector(){return nodes.panel;}
}
const names=['recording-status-banner','recording-status-label','recording-status-detail','recording-status-action','recording-confirm-modal','recording-guard-civilisation','recording-guard-yes','recording-guard-no','recording-guard-error','live-history'];
const nodes=Object.fromEntries(names.map(n=>[n,new Element(n)]));
nodes.panel=new Element('panel');
const state={campaign:{id:9,empire_name:'Veyran Fixture'},live_history_enabled:false,live_history_busy:false,recording_confirmation_required:true,live_history_status:'OFF',unprocessed_count:4};
const calls=[];
const context={console,Promise,setTimeout:(fn)=>{fn();return 1;},setInterval:()=>1,fetch:async (url,args)=>{
  calls.push([url,args]);
  if(url==='/api/active-campaign') return {ok:true,json:async()=>({...state})};
  if(url==='/api/recording-decision'){
    const p=JSON.parse(args.body);
    assert.equal(p.campaign_id,9);
    state.live_history_enabled=p.enabled;
    state.recording_confirmation_required=false;
    state.live_history_status=p.enabled?'ON - checking archived saves':'OFF';
    return {ok:true,json:async()=>({ok:true,enabled:p.enabled,campaign_id:9,status:state.live_history_status,queued_saves:4})};
  }
  throw Error('Unexpected URL '+url);
},document:{activeElement:null,getElementById:name=>nodes[name]||null,body:{classList:{add(){},remove(){}}},addEventListener(){} }};
vm.createContext(context);
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../static/recording-guard.js'),'utf8'),context);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(nodes['recording-confirm-modal'].hidden,false,'prompt on first selection');
  assert.equal(nodes['recording-status-banner'].dataset.state,'pending');
  nodes['recording-guard-no'].click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(nodes['recording-confirm-modal'].hidden,true,'NO dismisses only after server confirmation');
  assert.equal(nodes['recording-status-banner'].dataset.state,'off');
  assert.match(nodes['recording-status-label'].textContent,/OFF/);
  nodes['recording-status-action'].click();
  assert.equal(nodes['recording-confirm-modal'].hidden,false,'user can reopen from warning');
  nodes['recording-guard-yes'].click();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(nodes['recording-confirm-modal'].hidden,true,'YES completes confirmation');
  assert.equal(nodes['recording-status-banner'].dataset.state,'on');
  assert.equal(state.live_history_enabled,true);
  assert.equal(calls.filter(x=>x[0]==='/api/recording-decision').length,2);
  console.log('v0.0.85.1 JS: initial prompt, NO warning, reopen, YES enable, server confirmation: PASS');
})().catch(err=>{console.error(err);process.exitCode=1;});
