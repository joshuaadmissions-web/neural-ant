chrome.runtime.onInstalled.addListener(()=>chrome.storage.local.setAccessLevel({accessLevel:'TRUSTED_CONTEXTS'}));

importScripts('policy.js');

function splitProfileName(rawName, linkedinUrl) {
 const parts=String(rawName||'').trim().split(/\s+/).filter(Boolean);
 const firstName=parts[0]||'';
 let lastName=parts.slice(1).join(' ');
 try {
  const slug=new URL(linkedinUrl).pathname.split('/').filter(Boolean).pop().toLowerCase().split(/[-_]+/);
  const givenNames=parts.slice(1).map(part=>part.toLowerCase());
  if(givenNames.length&&givenNames.every((part,index)=>slug[index]===part))
   return {firstName:givenNames.map((_,index)=>parts[index+1]).join(' '),lastName:parts[0]};
 } catch {}
 return {firstName,lastName};
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
 if (message?.type !== 'NEURAL_ANT_SYNC_PROFILE') return false;
 const tabId = message.tabId;
 let tabOrigin;
 try { tabOrigin = new URL(message.tabUrl || '').origin; } catch {}
 if (_sender.id !== chrome.runtime.id || !tabId || tabOrigin !== 'http://127.0.0.1:8080') {
  sendResponse({ok:false, message:'Open the local Neural Ant app tab, then sync your profile.'});
  return false;
 }
 chrome.scripting.executeScript({
  target:{tabId}, world:'MAIN',
  func:async()=>{
   const response=await fetch('/api/contact-profile',{credentials:'same-origin',cache:'no-store'});
   if(!response.ok)throw new Error(response.status===404
    ?'The local Neural Ant app does not provide contact profile sync yet.'
    :`Neural Ant returned ${response.status}. Make sure it is running.`);
   return response.json();
  }
 }).then(results=>results?.[0]?.result)
  .then(async raw => {
   if (!raw || typeof raw !== 'object') throw new Error('Could not read the local profile.');
   const {firstName,lastName}=splitProfileName(raw.name,raw.linkedin_url);
   const profile = NeuralAntPolicy.sanitize({
    name: String(raw.name || '').trim(),
    firstName,
    lastName,
    email: raw.email,
    phone: raw.phone,
    location: raw.location,
    state: raw.state,
    linkedin: raw.linkedin_url,
    website: raw.website_url,
   });
   const count = Object.keys(profile).length;
   if (!count) throw new Error('No supported contact details were found. Review My profile in Neural Ant.');
   const profileSyncedAt = new Date().toISOString();
   await chrome.storage.local.set({profile, profileSyncedAt});
   sendResponse({ok:true, count, profileSyncedAt});
  })
  .catch(error => sendResponse({ok:false, message:error.message || 'Could not sync the local profile.'}));
 return true;
});
