import {evidence,plain} from './domain.mjs';
export function endpoint(s,id='') {
 if(!['greenhouse','lever'].includes(s.type)||!/^[a-zA-Z0-9_-]+$/.test(s.board)) throw Error('Invalid configured source');
 return s.type==='greenhouse'?`https://boards-api.greenhouse.io/v1/boards/${s.board}/jobs${id?'/'+encodeURIComponent(id):'?content=true'}`:`https://api.lever.co/v0/postings/${s.board}${id?'/'+encodeURIComponent(id):''}?mode=json`;
}
async function get(url){const r=await fetch(url,{signal:AbortSignal.timeout(20000),redirect:'error'});if(!r.ok)throw Error(`Source HTTP ${r.status}`);return r.json();}
export function normalize(s,j,checkedAt) {
 const gh=s.type==='greenhouse';
 let url=gh?j.absolute_url:j.hostedUrl; if(!/^https:\/\//.test(url||'')) url='';
 return evidence({id:`${s.type}:${s.board}:${j.id}`,source:s,sourceId:String(j.id),title:gh?j.title:j.text,employer:s.employer,location:gh?j.location?.name:j.categories?.location,workplaceType:j.workplaceType||'',url,applyUrl:/^https:\/\//.test(j.applyUrl||'')?j.applyUrl:url,text:gh?plain(j.content):[j.descriptionPlain,...(j.lists||[]).map(x=>x.text+'\n'+plain(x.content)),j.additionalPlain,j.salaryDescriptionPlain].filter(Boolean).join('\n'),salaryRange:j.salaryRange,salaryDescription:j.salaryDescriptionPlain,checkedAt,openEvidence:`Present in ${s.type} public published-postings API at ${checkedAt}`,verification:'published API listing',fixture:false});
}
export async function scan(sources) {
 const jobs=[],checks=[];
 for(const source of sources){const checkedAt=new Date().toISOString();try{const data=await get(endpoint(source));const list=source.type==='greenhouse'?data.jobs:data;if(!Array.isArray(list))throw Error('Unexpected source schema');jobs.push(...list.filter(j=>source.type!=='greenhouse'||j.internal_job_id!==null).map(j=>normalize(source,j,checkedAt)));checks.push({source,checkedAt,status:'ok',count:list.length,url:endpoint(source)});}catch(e){checks.push({source,checkedAt,status:'error',error:e.message,url:endpoint(source)});}}
 return {jobs,checks};
}
export async function verify(job){const checkedAt=new Date().toISOString();const data=await get(endpoint(job.source,job.sourceId));return {...normalize(job.source,data,checkedAt),verification:'individual published API posting',openEvidence:`Individual job endpoint returned HTTP 200 at ${checkedAt}`};}
