/* Shared theme controller — intentionally no campaign data access or network requests. */
(function(){
  'use strict';
  var KEY='stellaris-historian-theme-v1';
  function clean(value){return value==='light'?'light':'dark';}
  function stored(){try{return localStorage.getItem(KEY)}catch(e){return null}}
  function setTheme(value,persist){
    var theme=clean(value);
    document.documentElement.setAttribute('data-historian-theme',theme);
    document.documentElement.style.colorScheme=theme;
    if(persist){try{localStorage.setItem(KEY,theme)}catch(e){}}
    document.querySelectorAll('[data-historian-theme-toggle]').forEach(function(button){
      var dark=theme==='dark';
      button.textContent=dark?'☾ Dark mode':'☀ Light mode';
      button.setAttribute('aria-pressed',String(dark));
      button.title=dark?'Switch to light appearance':'Switch to dark appearance';
    });
  }
  window.HistorianTheme={setTheme:setTheme,getTheme:function(){return document.documentElement.getAttribute('data-historian-theme')||'dark'}};
  setTheme(stored()||'dark',false);
  function bind(){
    document.querySelectorAll('[data-historian-theme-toggle]').forEach(function(button){
      button.addEventListener('click',function(){setTheme(window.HistorianTheme.getTheme()==='dark'?'light':'dark',true)});
    });
    setTheme(window.HistorianTheme.getTheme(),false);
  }
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',bind,{once:true})}else{bind()}
  window.addEventListener('storage',function(event){if(event.key===KEY)setTheme(event.newValue||'dark',false)});
})();
