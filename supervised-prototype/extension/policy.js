(function(root){
 const keys=['name','firstName','lastName','email','phone','location','linkedin','website'];
 const aliases={name:['name','full name','fullname'],firstName:['first name','firstname'],lastName:['last name','lastname'],email:['email','email address'],phone:['phone','phone number','telephone'],location:['location','current location','city'],linkedin:['linkedin','linkedin profile','linkedin url'],website:['website','personal website','portfolio','portfolio url']};
 const sensitive=/authoriz|visa|sponsor|ssn|social.?security|demograph|gender|race|ethnic|veteran|disabil|background|criminal|signature|sign here|legal|attest|consent|agree|password|passcode|token|secret|captcha|verification|birth|citizen|nationality|salary|compensation|religion|marital|pronoun|permit|clearance|passport|security|tax|identification/i;
 const norm=s=>String(s||'').replace(/[_-]/g,' ').replace(/\[|\]/g,' ').replace(/\*/g,'').replace(/\s+/g,' ').trim().toLowerCase();
 function safeValue(k,v){if(typeof v!=='string'||!v.trim()||v.length>200||/[\r\n\x00-\x1f]/.test(v)||/bearer\s|-----BEGIN|(?:sk|ghp|github_pat)[_-]|eyJ[A-Za-z0-9_-]{15}/i.test(v))return false;
 if(k==='email')return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
 if(k==='phone')return /^[+()\d .-]{5,30}$/.test(v);
 if(k==='website'||k==='linkedin'){try{const u=new URL(v);return u.protocol==='https:'&&!u.username&&!u.password&&!u.search&&!u.hash&&(k!=='linkedin'||/(^|\.)linkedin\.com$/.test(u.hostname));}catch{return false;}}
 return !/[<>:=/\\]/.test(v)&&!sensitive.test(v);
 }
 function sanitize(o){const out={};for(const k of keys)if(safeValue(k,o?.[k]))out[k]=o[k].trim();return out;}
 function application(url){try{const u=new URL(url);if(u.username||u.password)return null;if(u.origin==='http://127.0.0.1:4317'&&u.pathname==='/test-application')return u.origin+u.pathname;if(u.protocol!=='https:')return null;
 if(['boards.greenhouse.io','job-boards.greenhouse.io'].includes(u.hostname)&&/^\/[\w-]+\/jobs\/\d+\/?$/.test(u.pathname))return u.origin+u.pathname.replace(/\/$/,'');
 if(u.hostname==='jobs.lever.co'&&/^\/[\w-]+\/[a-f0-9-]{36}(?:\/apply)?\/?$/i.test(u.pathname))return u.origin+u.pathname.replace(/\/apply\/?$/,'').replace(/\/$/,'')+'/apply';return null;}catch{return null;}}
 function fieldKey(el){if(el.tagName!=='INPUT'||!['text','email','tel','url',''].includes(el.type)||el.disabled||el.readOnly||el.hidden||el.closest('[hidden],[aria-hidden="true"]'))return null;
 const labels=[...(el.labels||[])].map(l=>l.textContent);const descriptions=(el.getAttribute('aria-describedby')||'').split(/\s+/).map(id=>el.ownerDocument.getElementById(id)?.textContent||'');const context=[el.name,el.id,el.getAttribute('aria-label'),el.autocomplete,el.placeholder,...labels,...descriptions,el.closest('fieldset')?.querySelector('legend')?.textContent].filter(Boolean);
 if(sensitive.test(context.join(' ')))return null;
 const hints=[...labels,el.getAttribute('aria-label')].filter(x=>x?.trim());
 // A visible label must itself be allowlisted. Generic internal IDs cannot override it.
 const candidates=hints.length?hints:[el.name,el.id];
 const matches=candidates.map(x=>Object.keys(aliases).find(k=>aliases[k].includes(norm(x)))).filter(Boolean);
 if(!matches.length||matches.some(k=>k!==matches[0])||hints.some(x=>!Object.values(aliases).flat().includes(norm(x))))return null;
 return matches[0];
 }
 function collect(doc){const result={};for(const el of doc.querySelectorAll('input')){const k=fieldKey(el);if(k&&el.getClientRects().length&&safeValue(k,el.value))result[k]=el.value.trim();}return result;}
 function fill(doc,data){let filled=0;data=sanitize(data);for(const el of doc.querySelectorAll('input')){const k=fieldKey(el);if(!k||!data[k]||el.value!==''||!el.getClientRects().length)continue;const setter=Object.getOwnPropertyDescriptor(doc.defaultView.HTMLInputElement.prototype,'value').set;setter.call(el,data[k]);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));filled++;}return filled;}
 root.NeuralAntPolicy={keys,sanitize,application,fieldKey,collect,fill};
})(globalThis);
