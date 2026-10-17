/* Browser-owned tabs cannot always be closed programmatically.
   Close server only after a successful acknowledgement, then attempt to close the
   tab. A user-opened tab is replaced with a blank page as the safe fallback. */
(function(){'use strict';
 window.HistorianClose=async function(button,status){
   if(button){button.disabled=true;button.textContent='Closing Historian…'}
   try{
     const response=await fetch('/app/close',{method:'POST',cache:'no-store'});
     if(!response.ok)throw new Error('Shutdown request was rejected ('+response.status+').');
     const data=await response.json();
     if(!data.ok)throw new Error('Shutdown was not confirmed.');
     if(status)status.textContent='Historian stopped. Closing the page…';
     window.close();
     // Standard user-opened tabs cannot be forcibly closed by web code.
     setTimeout(function(){try{window.location.replace('about:blank')}catch(e){
       if(status)status.textContent='Historian stopped. This browser prevents automatic tab closure; please close this tab.';
     }},130);
   }catch(error){
     if(status)status.textContent='Could not confirm shutdown: '+error.message;
     if(button){button.disabled=false;button.textContent='Close Historian'}
   }
 };
})();
