/** Borrador en memoria. No almacena secretos ni configuración en localStorage. */
const blocked = new Set(['__proto__', 'prototype', 'constructor']);
export function readPath(value, path) {
  for (const key of path) { if (!value || !Object.hasOwn(value,key)) return undefined; value=value[key]; }
  return value;
}
export function writePath(value, path, next) {
  if (!path.length || path.some((key)=>blocked.has(String(key)))) throw Error('Ruta de configuración inválida');
  let cursor=value;
  for (const key of path.slice(0,-1)) {
    if (!Object.hasOwn(cursor,key) || !cursor[key] || typeof cursor[key]!=='object') cursor[key]={};
    cursor=cursor[key];
  }
  const last=path.at(-1);
  if(next===undefined)delete cursor[last]; else cursor[last]=next;
}

export class ConfigurationDraft {
  constructor(value) { this.mode='visual';this.clearToken=false;this.reset(value); }
  reset(value) {
    this.value=structuredClone(value);this.original=JSON.stringify(value);this.raw=JSON.stringify(value,null,2);
    this.dirty=false;this.error='';this.mappings=new Map();
  }
  sync(value) { if(!this.dirty && JSON.stringify(value)!==this.original)this.reset(value); }
  set(path,value) { writePath(this.value,path,value);this.changed(); }
  changed() { this.dirty=true;this.raw=JSON.stringify(this.value,null,2); }
  setJSON(raw) {
    this.raw=raw;this.dirty=true;
    try {
      const parsed=JSON.parse(raw);
      if(!parsed || typeof parsed!=='object' || Array.isArray(parsed))throw Error('La configuración debe ser un objeto JSON');
      this.value=parsed;this.mappings.clear();this.error='';return true;
    }catch(error){this.error=error.message;return false;}
  }
  destinations(path) {
    const list=readPath(this.value,path);
    return Array.isArray(list)?list:[];
  }
  setDestination(path,index,key,value) {
    const list=structuredClone(this.destinations(path));
    const previous=list[index];
    if(typeof previous==='string' && key==='url')list[index]=value;
    else {
      list[index]={...(typeof previous==='string'?{url:previous}:previous),[key]:value};
      if(key==='url' && previous?.url!==value && previous?.token==='••••••')list[index].token='';
    }
    this.set(path,list);
  }
  mapping(path) {
    const id=JSON.stringify(path);
    if(!this.mappings.has(id))this.mappings.set(id,Object.entries(readPath(this.value,path)||{}).map(([key,value])=>({key,value:structuredClone(value)})));
    return this.mappings.get(id);
  }
  commitMapping(path) {
    const rows=this.mapping(path);
    this.dirty=true;
    const keys=rows.map((row)=>row.key.trim());
    if(keys.some((key)=>!key) || new Set(keys).size!==keys.length){this.error='Las claves no pueden estar vacías ni repetidas';return false;}
    writePath(this.value,path,Object.fromEntries(rows.map((row,index)=>[keys[index],structuredClone(row.value)])));
    this.error='';this.changed();return true;
  }
  validate(schema, {kind,liveReader=false}={}) {
    if(this.mode==='json' && !this.setJSON(this.raw))throw Error(this.error);
    if(this.mode!=='json')for(const [path] of this.mappings)if(!this.commitMapping(JSON.parse(path)))throw Error(this.error);
    if(this.error)throw Error(this.error);
    const original=JSON.parse(this.original);
    for(const group of schema)for(const field of group.fields){
      const value=readPath(this.value,field.path);
      if(field.readonly && JSON.stringify(value)!==JSON.stringify(readPath(original,field.path)))throw Error(field.label[0]+': este campo está fijado por el despliegue');
      if(value===undefined || value===''){if(field.required)throw Error(field.label[0]+': campo obligatorio');continue;}
      if(field.type==='number' && (typeof value!=='number' || !Number.isFinite(value) || value<field.min || (field.max!==undefined && value>field.max) || (field.step===1 && !Number.isInteger(value))))throw Error(field.label[0]+': valor fuera de rango');
      if(field.type==='boolean' && typeof value!=='boolean')throw Error(field.label[0]+': valor booleano requerido');
      if(field.type==='destinations'){
        if(!Array.isArray(value))throw Error(field.label[0]+': se esperaba una lista');
        for(const item of value){const url=typeof item==='string'?item:item?.url;try{if(!['http:','https:'].includes(new URL(url).protocol))throw Error();}catch{throw Error(field.label[0]+': URL HTTP/SSE inválida');}}
      }
      if(field.type==='mapping'){
        if(!value || typeof value!=='object' || Array.isArray(value))throw Error(field.label[0]+': se esperaba un objeto');
        for(const [key,row] of Object.entries(value)){
          if(!key.trim())throw Error(field.label[0]+': clave vacía');
          for(const column of field.columns){
            const cell=column.path[0]==='value' ? row : readPath(row,column.path);
            if(column.path[0]!=='value' && (!row || typeof row!=='object' || Array.isArray(row)))throw Error(field.label[0]+': entrada inválida');
            if(cell===undefined || cell==='')continue;
            if(column.type==='number' && (typeof cell!=='number' || !Number.isInteger(cell) || cell<column.min || cell>column.max))throw Error(column.label[0]+': valor fuera de rango');
            if(column.type!=='number' && typeof cell!=='string')throw Error(column.label[0]+': se esperaba texto');
          }
        }
      }
    }
    if(liveReader && this.value.readerId!==JSON.parse(this.original).readerId)throw Error('La identidad del Reader no se puede cambiar en directo');
    if(kind==='publisher'){
      const policy=this.value.policy||{};
      if(policy.minValue>policy.maxValue)throw Error('El mínimo no puede superar al máximo');
      if(policy.minCount>(this.value.batchSize||32))throw Error('Se requieren más lecturas que el tamaño del lote');
      for(const device of Object.values(this.value.devices||{})){
        const effective={minValue:90,maxValue:130,minCount:28,...policy,...device.policy};
        if(effective.minValue>effective.maxValue)throw Error('Política de dispositivo: el mínimo supera al máximo');
      }
    }
    if(liveReader && this.value.managers?.some((target)=>typeof target==='string'))throw Error('Cada Manager necesita un objeto con URL y token');
    if(['verifier','storage'].includes(kind) && this.value.subscriptions?.managers?.length && !this.value.server?.publicUrl && !schema.some((group)=>group.fields.some((field)=>field.path.join('.')==='server.publicUrl' && field.readonly)))throw Error('Las suscripciones SSE necesitan la URL pública del servicio');
    return structuredClone(this.value);
  }
}
