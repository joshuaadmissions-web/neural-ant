export const SKILLS = ['Python','AWS','AWS Bedrock','RAG','LLM evaluation','NLP','MLOps','OCR','speech intelligence','TypeScript','Docker','Kubernetes','SQL','Terraform'];
export function plain(s='') { return String(s).replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/<[^>]*>/g,' ').replace(/&amp;/g,'&').replace(/&nbsp;/g,' ').replace(/&#\d+;/g,' ').replace(/[ \t]+/g,' ').trim(); }
export function hasSkill(text,skill) { const escaped=skill.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); return new RegExp('(^|[^a-z0-9])'+escaped+'(?=$|[^a-z0-9])','i').test(text); }
export function extract(text) {
 const lines=text.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
 return {name:lines[0]||'',email:text.match(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/i)?.[0]||'',phone:'',location:'',linkedin:'',website:'',years:'',skills:SKILLS.filter(s=>hasSkill(text,s)),facts:lines};
}
export function profile(input) {
 const out={}; for(const k of ['name','email','phone','location','linkedin','website','years']) out[k]=String(input[k]??'').trim().slice(0,300);
 if(out.years && (!Number.isFinite(Number(out.years)) || Number(out.years)<0 || Number(out.years)>70)) throw Error('Experience must be a number from 0 to 70, or blank.');
 for(const k of ['skills','facts']) { if(!Array.isArray(input[k])) throw Error('Facts and skills must be lists'); out[k]=input[k].map(x=>String(x).trim()).filter(Boolean).slice(0,250).map(x=>x.slice(0,2000)); }
 if(!out.name || !out.facts.length) throw Error('Confirm a name and at least one factual resume line.');
 return out;
}
export function evidence(job) {
 const text=plain(job.text), lines=text.split(/(?<=[.!?])\s+|\n/).map(x=>x.trim()).filter(Boolean);
 const money=lines.filter(x=>/salary|base pay|base compensation/i.test(x));
 let salary={status:'unverified',evidence:money.join('\n')||'No explicit annual USD base-salary evidence parsed.'};
 for(const line of money) {
  const amounts=[...line.matchAll(/(?:\$|USD\s*)(\d{2,3}(?:,\d{3})?(?:\.\d+)?)(k)?\b/gi)].map(m=>Number(m[1].replaceAll(',',''))*(m[2]?1000:1));
  if(amounts.length && /USD|U\.S\. dollars?|US dollars?/i.test(line) && /base/i.test(line) && /annual|year|annum|base salary|base pay/i.test(line) && !/hour|month|CAD|AUD|OTE|total compensation/i.test(line)) { const min=Math.min(...amounts);salary={status:min>=100000?'meets minimum':'below minimum',min,currency:'USD',evidence:line};break; }
 }
 if(job.salaryRange?.currency==='USD' && job.salaryRange.interval==='per-year' && /base/i.test(job.salaryDescription||'')) salary={status:job.salaryRange.min>=100000?'meets minimum':'below minimum',min:job.salaryRange.min,currency:'USD',evidence:JSON.stringify(job.salaryRange)+' '+job.salaryDescription};
 const sponsorshipLines=lines.filter(x=>/sponsor|visa|h-?1b|work authoriz/i.test(x));
 const no=sponsorshipLines.some(x=>/(?:no|without|not|unable|cannot|can't|do not|does not|will not|won't|unavailable).{0,90}sponsor|sponsor.{0,90}(?:not available|unavailable|not offered)|must.{0,60}(?:citizen|permanent resident)/i.test(x));
 const yes=!no && sponsorshipLines.some(x=>/(?:offer|provide|available|support|eligible).{0,50}(?:visa sponsorship|sponsorship)|sponsorship.{0,40}(?:available|provided|offered)/i.test(x));
 const location=job.location||'Unspecified';
 const us=/\b(United States|USA|U\.S\.|US|New York|San Francisco|Seattle|Boston|Austin|Los Angeles|Chicago|Washington|California|Texas|Colorado|Virginia|Massachusetts|NY|CA|WA|TX|CO|MA)\b/i.test(location);
 const exp=lines.filter(x=>/\d+\+?\s*(?:-|–|to)?\s*\d*\s*years?/i.test(x));
 return {...job,text,salary,sponsorship:{role: no?'explicit no sponsorship':yes?'role states sponsorship support':'uncertain — manual review',evidence:sponsorshipLines,employerHistory:'Not researched; never used as role evidence'},us:us?'U.S. location indicated':'unverified U.S. eligibility',arrangement:/remote/i.test(location+' '+job.workplaceType)?'remote':/hybrid/i.test(location+' '+job.workplaceType)?'hybrid':/on.?site/i.test(job.workplaceType||'')?'on-site':'unspecified — check posting',experience:exp.length?exp:['Not parsed — review posting'],target:/\b(engineer|developer)\b/i.test(job.title)&&/\b(ai|agentic|agent|llm|cloud|backend|back.end|forward.deployed)\b/i.test(job.title),excluded:no||salary.status==='below minimum'};
}
export function fit(job,p) {
 if(!p) return {status:'Confirm resume facts first',reasons:[],gaps:[]};
 const matched=p.skills.filter(s=>hasSkill(job.text,s));
 const missing=SKILLS.filter(s=>hasSkill(job.text,s)&&!p.skills.some(v=>v.toLowerCase()===s.toLowerCase()));
 const requirements=job.experience.join(' '), years=Number(requirements.match(/(\d+)\+?\s*(?:-|–|to)?\s*\d*\s*years?/i)?.[1]||0);
 const gaps=missing.map(s=>'Not confirmed: '+s);
 const openUnverified=job.verification?.startsWith('unverified') || (!job.fixture && Date.now()-Date.parse(job.checkedAt)>86400000);
 if(openUnverified)gaps.push('Open status unverified or older than 24 hours; recheck posting.');
 if(years && (!p.years || Number(p.years)<years)) gaps.push(`Experience requires review: posting mentions ${years} years; confirmed ${p.years||'unknown'}.`);
 if(job.salary.status==='unverified') gaps.push('Salary unverified; not a confirmed qualifying match.');
 if(job.us!=='U.S. location indicated') gaps.push('U.S. eligibility unverified.');
 if(job.sponsorship.role.startsWith('uncertain')) gaps.push('Role sponsorship uncertain; user must review.');
 return {status:job.excluded?'Excluded':!openUnverified&&job.target&&job.salary.status==='meets minimum'&&job.us==='U.S. location indicated'&&matched.length?'Potential match — review required':'Unverified / needs review',reasons:matched.map(s=>'Confirmed skill appears in posting: '+s),gaps};
}
export function tailor(job,p) {
 const ranked=p.facts.map((text,index)=>({text,index,score:(index<2?1000-index:0)+p.skills.filter(s=>hasSkill(job.text,s)&&hasSkill(text,s)).length})).sort((a,b)=>b.score-a.score||a.index-b.index);
 return {text:ranked.map(x=>x.text).join('\n'),changes:ranked.map((x,i)=>({factIndex:x.index,originalPosition:x.index+1,draftPosition:i+1,text:x.text})),method:'Confirmed facts reordered by overlapping skills. No claims added; no external AI.',reviewed:false};
}
