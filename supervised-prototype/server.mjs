import http from 'node:http';
import {randomBytes,createHash} from 'node:crypto';
import {readFile,writeFile,mkdir,rename} from 'node:fs/promises';
import path from 'node:path';
import {extract,profile,fit,tailor} from './lib/domain.mjs';
import {scan,verify} from './lib/sources.mjs';
import {fixtures,resume} from './lib/fixtures.mjs';
const PORT=Number(process.env.PORT||4317), origin=`http://127.0.0.1:${PORT}`;
const root=path.resolve('.'),dataDir=path.resolve(process.env.NEURAL_ANT_DATA||'.private');
await mkdir(dataDir,{recursive:true,mode:0o700});
let db={profile:null,intake:null,jobs:[],checks:[],drafts:{},events:[]};
try{db=JSON.parse(await readFile(path.join(dataDir,'state.json'),'utf8'));}catch(e){if(e.code!=='ENOENT')throw e;}
const session=randomBytes(32).toString('hex');
async function save(){await writeFile(path.join(dataDir,'state.tmp'),JSON.stringify(db),{mode:0o600});await rename(path.join(dataDir,'state.tmp'),path.join(dataDir,'state.json'));}
function event(role,status,detail){db.events.push({role,status,detail,at:new Date().toISOString()});db.events=db.events.slice(-300);}
async function body(req){let size=0,chunks=[];for await(const c of req){size+=c.length;if(size>8*1024*1024)throw Error('Maximum upload size is 5 MB');chunks.push(c);}return JSON.parse(Buffer.concat(chunks).toString());}
function json(res,value,status=200){res.writeHead(status,{'Content-Type':'application/json'});res.end(JSON.stringify(value));}
function publicState(){return {...db,jobs:db.jobs.map(j=>({...j,fit:fit(j,db.profile)}))};}
async function intake(name,bytes){
 if(bytes.length>5*1024*1024)throw Error('Maximum upload size is 5 MB');
 let text;
 if(/\.(txt|md)$/i.test(name)) text=bytes.toString('utf8');
 else if(/\.pdf$/i.test(name)) {const {getDocument}=await import('pdfjs-dist/legacy/build/pdf.mjs');const doc=await getDocument({data:new Uint8Array(bytes),isEvalSupported:false,useSystemFonts:false}).promise;try{if(doc.numPages>50)throw Error('Maximum 50 pages');const pages=[];for(let n=1;n<=doc.numPages;n++){const page=await doc.getPage(n);pages.push((await page.getTextContent()).items.map(x=>x.str+(x.hasEOL?'\n':' ')).join(''));}text=pages.join('\n');}finally{await doc.destroy();}}
 else if(/\.docx$/i.test(name)){const mammoth=await import('mammoth');text=(await mammoth.default.extractRawText({buffer:bytes})).value;}
 else throw Error('Use TXT, Markdown, text-based PDF, or DOCX.');
 if(!text.trim())throw Error('No text found. Scanned PDFs require a text export; OCR is not supported.');
 const hash=createHash('sha256').update(bytes).digest('hex');
 await writeFile(path.join(dataDir,hash+'.original'),bytes,{mode:0o600,flag:'wx'}).catch(e=>{if(e.code!=='EEXIST')throw e;});
 db.intake={name:path.basename(name),hash,text,proposed:extract(text)};db.profile=null;db.drafts={};
 event('Resume intake','awaiting confirmation','Local extraction complete. Correct all facts before matching.');await save();
}
let mutation=Promise.resolve();
async function handler(req,res){
 res.setHeader('Cache-Control','no-store');res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'");
 if(req.headers.host!==`127.0.0.1:${PORT}`){return json(res,{error:`Open ${origin}; invalid Host`},403);}
 const u=new URL(req.url,origin),p=u.pathname;
 if(req.method==='GET'&&p==='/'){res.setHeader('Set-Cookie',`na_session=${session}; HttpOnly; SameSite=Strict; Path=/`);}
 if(p.startsWith('/api/')&&(!req.headers.cookie?.split('; ').includes(`na_session=${session}`)||req.headers['sec-fetch-site']==='cross-site'))return json(res,{error:'Open the local app first'},403);
 if(req.method!=='GET'&&req.headers.origin!==origin)return json(res,{error:'Invalid origin'},403);
 try{
 if(req.method==='GET'&&p==='/api/state')return json(res,publicState());
 if(req.method==='GET'&&p==='/api/original') {if(!db.intake)throw Error('No original');res.writeHead(200,{'Content-Type':'application/octet-stream','Content-Disposition':`attachment; filename="original${path.extname(db.intake.name).replace(/[^.a-z0-9]/gi,'')}"`});return res.end(await readFile(path.join(dataDir,db.intake.hash+'.original')));}
 if(req.method==='POST'&&p.startsWith('/api/')){
 const input=await body(req);
 if(p==='/api/intake')await intake(input.name,Buffer.from(input.base64,'base64'));
 else if(p==='/api/demo')await intake('synthetic-resume.txt',Buffer.from(resume));
 else if(p==='/api/confirm'){if(!db.intake)throw Error('Upload first');db.profile=profile(input);db.profile.confirmedAt=new Date().toISOString();db.drafts={};event('Fit Reviewer','ready','User confirmed resume facts; prior drafts invalidated.');await save();}
 else if(p==='/api/scout') {if(!db.profile)throw Error('Confirm facts first');if(input.fixture){db.jobs=fixtures();db.checks.push({checkedAt:new Date().toISOString(),status:'fixture',count:3,source:{employer:'Synthetic only'}});}else{const sources=JSON.parse(await readFile('sources.json','utf8'));const result=await scan(sources);db.jobs=result.jobs;db.checks.push(...result.checks);}db.checks=db.checks.slice(-100);db.drafts={};event('Job Scout','complete',`${db.jobs.length} postings collected; see source ledger.`);event('Posting Verifier','review required','Published API evidence recorded. Recheck individual posting before preparing.');event('Fit Reviewer','complete','Compared only confirmed skills; salary and sponsorship uncertainty preserved.');await save();}
 else if(p==='/api/verify'){const i=db.jobs.findIndex(j=>j.id===input.id);if(i<0)throw Error('Unknown job');try{if(!db.jobs[i].fixture)db.jobs[i]=await verify(db.jobs[i]);event('Posting Verifier','complete',`${input.id}: ${db.jobs[i].openEvidence}`);}catch(e){db.jobs[i].verification='unverified — latest check failed';db.jobs[i].openEvidence=e.message;db.jobs[i].checkedAt=new Date().toISOString();event('Posting Verifier','failed',`${input.id}: ${e.message}`);}await save();}
 else if(p==='/api/tailor'){const job=db.jobs.find(j=>j.id===input.id);if(!job||!db.profile)throw Error('Job and confirmed profile required');if(job.excluded)throw Error('Excluded posting');if(job.verification.startsWith('unverified'))throw Error('Recheck posting successfully first');db.drafts[job.id]=tailor(job,db.profile);event('Resume Tailor','awaiting review',`Draft for ${job.title}: confirmed facts only.`);await save();}
 else if(p==='/api/review'){const d=db.drafts[input.id];if(!d)throw Error('Draft not found');d.reviewed=true;d.reviewedAt=new Date().toISOString();event('Resume Tailor','reviewed','User reviewed draft and changes.');event('Application Prep Assistant','manual handoff','Export allowed contact profile, open application, click Fill, save locally; user attaches resume and submits.');await save();}
 else return json(res,{error:'Not found'},404);
 return json(res,publicState());
 }
 const files={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/test-application':'test-application.html'};
 if(req.method==='GET'&&files[p]){res.writeHead(200,{'Content-Type':p.endsWith('.js')?'text/javascript':p.endsWith('.css')?'text/css':'text/html'});return res.end(await readFile(path.join(root,'public',files[p])));}
 json(res,{error:'Not found'},404);
 }catch(e){json(res,{error:e.message},400);}
}
http.createServer((req,res)=>{if(req.method==='POST'){mutation=mutation.then(()=>handler(req,res)).catch(()=>{if(!res.writableEnded)json(res,{error:'Request failed'},500);});}else handler(req,res);}).listen(PORT,'127.0.0.1',()=>console.log(`Neural Ant: ${origin} (private local storage)`));
