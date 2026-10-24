'use strict';
// Re-run saved n8n classifier code in isolated VM. Does NOT execute n8n / HTTP / DB.
const fs=require('fs'),path=require('path'),vm=require('vm');
const ROOT=path.resolve(process.argv[2]||path.join(__dirname,'..','n8n'));
const OUTPUT=path.resolve(process.argv[3]||path.join(__dirname,'..','regression-results.json'));
const workflows={}, report={root:path.basename(ROOT),legacy_cases:[],tenant_isolation_negative_cases:[],checks:{source_contracts:[],topology:[]}};
function loadJson(p){return JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'))}
for(const f of fs.readdirSync(path.join(ROOT,'candidates')).filter(x=>x.endsWith('.json')).sort()){
 const workflow=loadJson('candidates/'+f);
 const node=workflow.nodes.find(n=>n.type==='n8n-nodes-base.code'&&n.name==='Fail Closed Classify');
 const stamp=workflow.nodes.find(n=>n.name==='Stamp Envelope Metadata');
 const metadata=stamp.parameters.assignments.assignments;
 const oid=metadata.find(x=>x.name==='orchestration').value;
 if(workflows[oid]||workflow.active!==false)throw Error('Duplicate/active workflow: '+oid);
 if(!node)throw Error('No classifier '+oid);
 const post=workflow.nodes.filter(x=>x.type==='n8n-nodes-base.httpRequest');
 if(!post.every(x=>x.parameters?.url?.includes('PLACEHOLDER_KDB')&&x.parameters?.options?.allowUnauthorizedCerts===false))throw Error('Unexpected network endpoint or TLS flag');
 if(workflow.nodes.some(x=>/postgres|executeCommand|webhook/i.test(x.type)))throw Error('Disallowed workflow node type');
 report.checks.topology.push({oid,file:f,active:false,placeholder_http_nodes:post.length,pass:true});
 workflows[oid]={js:node.parameters.jsCode,metadata};
}
// Cross-archive interface invariant: the M01 O1/O2/O3 contracts require tenant_scope.
const kit=process.argv[4];
if(kit){for(let o=1;o<=3;o++){const names={1:'o1_source_ingest.schema.json',2:'o2_candidate_proposal.schema.json',3:'o3_review_handoff.schema.json'};
  const schema=JSON.parse(fs.readFileSync(path.join(kit,'contracts',names[o]),'utf8'));
  if(!schema.required.includes('tenant_scope'))throw Error('KDB source contract changed');
  report.checks.source_contracts.push({contract:`O${o}`,required_tenant_scope:true});
}}
function classify(oid,body){const flow=workflows[oid];const json=JSON.parse(JSON.stringify(body));for(const m of flow.metadata){if(typeof m.value==='string'&&!m.value.startsWith('={{'))json[m.name]=m.value;}
 const ctx=vm.createContext({$input:{first:()=>({json})}});
 return vm.runInContext('(function(){\n'+flow.js+'\n})()',ctx,{timeout:250})[0].json;
}
const files=fs.readdirSync(path.join(ROOT,'fixtures')).filter(s=>s.endsWith('.json')).sort();
for(const f of files){const c=loadJson('fixtures/'+f);const actual=classify(c.target_oid,c.body).route;
 report.legacy_cases.push({fixture:f,expected:c.expected_route,actual,pass:actual===c.expected_route});
 if(c.expected_route==='ACCEPT'){for(const variant of ['missing','whitespace']){
   const obj=JSON.parse(JSON.stringify(c.body));if(variant==='missing')delete obj.tenant_scope;else obj.tenant_scope='   ';
   const outcome=classify(c.target_oid,obj).route;
   report.tenant_isolation_negative_cases.push({fixture:f,variant,expected:'DENY',actual:outcome,pass:outcome==='DENY'});
 }}
}
report.counts={workflow_count:Object.keys(workflows).length,legacy_cases:report.legacy_cases.length,legacy_pass:report.legacy_cases.filter(x=>x.pass).length,tenant_negative_cases:report.tenant_isolation_negative_cases.length,tenant_negative_pass:report.tenant_isolation_negative_cases.filter(x=>x.pass).length};
report.acceptance={offline_code_node_baseline:report.counts.legacy_pass===report.counts.legacy_cases?'PASS':'FAIL',tenant_fail_closed:report.counts.tenant_negative_pass===report.counts.tenant_negative_cases?'PASS':'FAIL',physical_pg17:'NOT_RUN',PIAC_signature:'NOT_RUN',n8n_runtime:'NOT_RUN'};
fs.writeFileSync(OUTPUT,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({counts:report.counts,acceptance:report.acceptance},null,2));
if(report.acceptance.offline_code_node_baseline!=='PASS')process.exitCode=1;
// Security regressive failure is recorded and surfaced, but not an exception when inspecting source.
