import test from 'node:test';
import assert from 'node:assert/strict';
import { ConfigurationDraft, writePath } from '../configuration/model.js';
import { configurationSchema } from '../configuration/schema.js';

test('Los cambios visuales conservan opciones desconocidas y secretos ocultos',()=>{
  const source={services:{verifiers:[{url:'http://verifier:5000',token:'••••••',extra:true}]},extension:{enabled:true}};
  const draft=new ConfigurationDraft(source);
  draft.set(['stream','enabled'],true);
  const result=draft.validate(configurationSchema('manager'),{kind:'manager'});
  assert.equal(result.services.verifiers[0].token,'••••••');
  assert.equal(result.services.verifiers[0].extra,true);
  assert.deepEqual(result.extension,source.extension);
  assert.equal(source.services.verifiers[0].url,'http://verifier:5000');
});

test('Cambiar de destino borra el token oculto del anterior',()=>{
  const draft=new ConfigurationDraft({managers:[{url:'http://old:3003',token:'••••••'}]});
  draft.setDestination(['managers'],0,'url','http://new:3003');
  assert.equal(draft.value.managers[0].token,'');
});

test('Un destino URL mantiene su formato hasta añadir un token',()=>{
  const draft=new ConfigurationDraft({subscriptions:{managers:['http://manager:3003']}});
  const path=['subscriptions','managers'];
  draft.setDestination(path,0,'url','http://manager2:3003');
  assert.equal(draft.destinations(path)[0],'http://manager2:3003');
  draft.setDestination(path,0,'token','nuevo');
  assert.deepEqual(draft.destinations(path)[0],{url:'http://manager2:3003',token:'nuevo'});
});

test('Visual y JSON comparten los cambios; JSON inválido no destruye el borrador',()=>{
  const draft=new ConfigurationDraft({policy:{minValue:90}});
  draft.set(['policy','minValue'],95);
  assert.equal(JSON.parse(draft.raw).policy.minValue,95);
  assert.equal(draft.setJSON('{'),false);
  assert.equal(draft.value.policy.minValue,95);
  assert.throws(()=>draft.validate([]));
  assert.equal(draft.setJSON('{"policy":{"minValue":100},"extra":1}'),true);
  assert.equal(draft.value.policy.minValue,100);
  assert.equal(draft.value.extra,1);
  assert.equal(draft.setJSON('[]'),false);
});

test('El polling conserva borradores y actualiza formularios sin editar',()=>{
  const draft=new ConfigurationDraft({managerId:'original'});
  draft.sync({managerId:'nuevo'});
  assert.equal(draft.value.managerId,'nuevo');
  draft.set(['managerId'],'sin guardar');
  draft.sync({managerId:'polling'});
  assert.equal(draft.value.managerId,'sin guardar');
});

test('Los mapas rechazan claves repetidas o vacías y conservan políticas por dispositivo',()=>{
  const draft=new ConfigurationDraft({devices:{pulse:{contractId:'C...',policy:{minValue:90},extra:42}}});
  const rows=draft.mapping(['devices']);
  rows.push({key:'',value:{}});
  assert.equal(draft.commitMapping(['devices']),false);
  assert.throws(()=>draft.validate(configurationSchema('publisher'),{kind:'publisher'}));
  rows[1].key='pulse';
  assert.equal(draft.commitMapping(['devices']),false);
  rows[1].key='cold';rows[1].value={contractId:'C2',policy:{minValue:2,maxValue:8,minCount:32}};
  assert.equal(draft.commitMapping(['devices']),true);
  assert.equal(draft.validate(configurationSchema('publisher'),{kind:'publisher'}).devices.pulse.extra,42);
});

test('Políticas y colas se validan también desde JSON avanzado',()=>{
  for(const config of [{policy:{minValue:150,maxValue:100}},{policy:{minCount:33}},{devices:{bad:{policy:{minValue:200,maxValue:10}}}}]){
    const draft=new ConfigurationDraft(config);
    assert.throws(()=>draft.validate(configurationSchema('publisher'),{kind:'publisher'}));
  }
  const draft=new ConfigurationDraft({readerId:'r',queueSize:5000});
  assert.throws(()=>draft.validate(configurationSchema('reader',{liveReader:true}),{kind:'reader',liveReader:true}));
});

test('JSON no cambia identidad en directo ni campos impuestos por Docker o variables',()=>{
  const draft=new ConfigurationDraft({readerId:'r',queueSize:256});
  draft.setJSON('{"readerId":"otro","queueSize":256}');
  assert.throws(()=>draft.validate(configurationSchema('reader',{liveReader:true}),{kind:'reader',liveReader:true}));
  const manager=new ConfigurationDraft({server:{port:3003},queue:{size:1000}});
  manager.set(['server','port'],1234);
  assert.throws(()=>manager.validate(configurationSchema('manager',{managed:true})));
  const schema=configurationSchema('manager',{environment:{MANAGER_QUEUE_SIZE:'••••••'}});
  assert.equal(schema.flatMap((group)=>group.fields).find((field)=>field.path.join('.')==='queue.size').readonly,true);
});

test('Las rutas no permiten contaminar prototipos',()=>{
  assert.throws(()=>writePath({},['__proto__','polluted'],true));
  assert.equal({}.polluted,undefined);
});
