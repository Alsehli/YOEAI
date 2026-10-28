/* Shared JSON Schema: used by llama.cpp constrained output and exported documentation. */
(function(root,factory){const v=factory();if(typeof module==='object'&&module.exports)module.exports=v;else root.YoeVisualSchema=v;})(typeof window==='object'?window:globalThis,()=>{
const text={type:'string',maxLength:1000},key={type:'string',pattern:'^[A-Za-z][A-Za-z0-9_-]*$',maxLength:32},number={type:'number',minimum:-1e15,maximum:1e15},nullable={type:['string','number','null']};
const object=(properties,required=Object.keys(properties))=>({type:'object',properties,required,additionalProperties:false});const array=(items,maxItems,minItems=0)=>({type:'array',items,maxItems,minItems});
const column=object({key,label:text,type:{enum:['text','number','date','status']},unit:text,format:{enum:['text','number','currency','percent','date','time','status']}},['key','label','type']);
const dataset=object({id:key,columns:array(column,32,1),rows:array({type:'object',additionalProperties:nullable},10000,1)});
const base={type:{type:'string'},title:text,description:text};
const components=[
 ...[
  object({...base,type:{const:'chart'},dataset:key,chartType:{enum:['bar','horizontalBar','line','area','scatter','donut','pie','combo']},x:key,series:array(object({field:key,label:text,chartType:{enum:['bar','line']}},['field']),6,1)},['type','dataset','chartType','x','series']),
  object({...base,type:{const:'chart'},dataset:key,chartType:{const:'histogram'},value:key,bins:{type:'integer',minimum:2,maximum:50}},['type','dataset','chartType','value']),
  object({...base,type:{const:'chart'},dataset:key,chartType:{const:'heatmap'},x:key,y:key,value:key},['type','dataset','chartType','x','y','value']),
  object({...base,type:{const:'chart'},dataset:key,chartType:{const:'candlestick'},x:key,open:key,high:key,low:key,close:key},['type','dataset','chartType','x','open','high','low','close'])
 ],
 object({...base,type:{const:'table'},dataset:key,columns:array(key,32,1)},['type','dataset']),
 object({...base,type:{const:'kpi'},dataset:key,field:key,aggregate:{enum:['sum','mean','min','max','last','growth']},label:text,unit:text,target:number},['type','dataset','field','aggregate','label']),
 object({...base,type:{const:'kpi'},dataset:key,aggregate:{const:'count'},label:text,target:number},['type','dataset','aggregate','label']),
 object({...base,type:{const:'timeline'},orientation:{enum:['vertical','horizontal']},events:array(object({id:key,title:text,date:text,endDate:text,dateStatus:{enum:['provided','proposed']},status:{enum:['planned','active','completed','blocked','cancelled']},details:text,dependencies:array(key,20)},['id','title']),200,1)},['type','events']),
 object({...base,type:{const:'flowchart'},nodes:array(object({id:key,label:text,details:text,kind:{enum:['start','process','decision','end']}},['id','label']),60,1),edges:array(object({source:key,target:key,label:text},['source','target']),100)},['type','nodes','edges'])
];
return {anyOf:[object({schemaVersion:{const:'1.0'},type:{enum:['chart','table','dashboard','timeline','flowchart','mixed']},title:text,summary:{type:'string',maxLength:4000},provenance:object({kind:{enum:['user','calculated','retrieved','estimated','example','unverified']},note:text,sources:array(object({url:text,title:text,retrievedAt:text},['url','title']),20)},['kind']),datasets:array(dataset,8),components:array({anyOf:components},12,1)},['schemaVersion','type','title','provenance','datasets','components']),object({schemaVersion:{const:'1.0'},type:{const:'text'},text:{type:'string',maxLength:4000}})]};
});
