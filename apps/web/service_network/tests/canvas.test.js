import test from 'node:test';
import assert from 'node:assert/strict';
import { CanvasState, ZOOM_LIMITS } from '../state.js';
import { autoLayout, fitViewport } from '../layout.js';
import { networkModel, hostLabel, NODE_SIZE } from '../models.js';
import { edgeGeometry } from '../edge.js';
import { requestLocal } from '../api.js';

const nodes = [
  { id:'r', kind:'reader', name:'Reader', organization:'hospital' },
  { id:'m', kind:'manager', name:'Manager', organization:'hospital' },
  { id:'v', kind:'verifier', name:'Verifier', organization:'hospital' },
  { id:'s', kind:'storage', name:'Storage', organization:'hospital' },
];
const edges = [ {sourceId:'r',targetId:'m'}, {sourceId:'m',targetId:'v'}, {sourceId:'m',targetId:'s'} ];

test('auto layout no solapa servicios ni pierde nodos desconectados', () => {
  const positions = autoLayout(nodes, edges);
  assert.equal(Object.keys(positions).length, 4);
  assert.ok(positions.r.x < positions.m.x);
  assert.ok(positions.m.x < positions.v.x);
  assert.ok(Math.abs(positions.v.y - positions.s.y) >= NODE_SIZE.height);
  assert.equal(Object.keys(autoLayout(nodes, [])).length, 4);
});

test('los ciclos no impiden colocar los nodos', () => {
  const positions = autoLayout(nodes, [...edges, {sourceId:'v',targetId:'r'}]);
  assert.equal(Object.keys(positions).length, nodes.length);
  assert.ok(Object.values(positions).every((point) => Number.isFinite(point.x) && Number.isFinite(point.y)));
});

test('actualizar datos y añadir nodos conserva las posiciones manuales', () => {
  const state = new CanvasState();
  state.sync(nodes, edges);
  state.move('r', {x:-100,y:800});
  state.sync([...nodes, {id:'new',kind:'reader',name:'Other',organization:'remote'}], edges);
  assert.deepEqual(state.positions.r, {x:-100,y:800});
  assert.ok(state.positions.new);
  state.sync(nodes.slice(1), []);
  assert.equal(state.positions.r, undefined);
});

test('el zoom conserva el punto bajo el cursor y limita la escala', () => {
  const state = new CanvasState();
  state.viewport = {x:50,y:-70,zoom:.8};
  const point = {x:300,y:200};
  const before = {x:(point.x-50)/.8,y:(point.y+70)/.8};
  state.zoomAt(point, 2);
  assert.equal((point.x-state.viewport.x)/state.viewport.zoom, before.x);
  assert.equal((point.y-state.viewport.y)/state.viewport.zoom, before.y);
  state.zoomAt(point, 100);
  assert.equal(state.viewport.zoom, ZOOM_LIMITS.max);
  state.zoomAt(point, .001);
  assert.equal(state.viewport.zoom, ZOOM_LIMITS.min);
});

test('Fit view incluye nodos con coordenadas negativas', () => {
  const positions = {a:{x:-200,y:-100},b:{x:700,y:450}};
  const view = fitViewport(positions, 1000, 650);
  for (const point of Object.values(positions)) {
    assert.ok(point.x * view.zoom + view.x >= 0);
    assert.ok(point.y * view.zoom + view.y >= 0);
    assert.ok((point.x+NODE_SIZE.width)*view.zoom+view.x <= 1000);
    assert.ok((point.y+NODE_SIZE.height)*view.zoom+view.y <= 650);
  }
});

test('posiciones y viewport sobreviven a una recarga', () => {
  const values = new Map();
  const storage = {getItem:(key)=>values.get(key),setItem:(key,value)=>values.set(key,value)};
  const state = new CanvasState({storage});
  state.sync(nodes,edges);
  state.move('r',{x:12,y:34});
  state.viewport = {x:90,y:80,zoom:.6};
  state.save();
  const restored = new CanvasState({storage});
  assert.deepEqual(restored.positions.r,{x:12,y:34});
  assert.deepEqual(restored.viewport,state.viewport);
});

test('almacenamiento corrupto o desactivado no bloquea el canvas', () => {
  const state = new CanvasState({storage:{getItem:()=>'{bad',setItem:()=>{throw Error('blocked');}}});
  state.sync(nodes,edges);
  assert.doesNotThrow(()=>state.save());
  assert.equal(Object.keys(state.positions).length,4);
});

test('las conexiones cambian de lado al mover el destino a la izquierda', () => {
  const right = edgeGeometry({x:0,y:0},{x:400,y:200});
  const left = edgeGeometry({x:400,y:0},{x:0,y:200});
  assert.ok(right.path.startsWith(`M ${NODE_SIZE.width} ${NODE_SIZE.height / 2} `));
  assert.ok(left.path.startsWith(`M 400 ${NODE_SIZE.height / 2} `));
  assert.notEqual(right.path,left.path);
});

test('modelo distingue transportes, runtime y destinos inexistentes', () => {
  const model = networkModel({services:[
    {id:'r',kind:'reader',name:'R',url:'http://remote:3002',org:'hospital',managed:true,managers:['m','missing']},
    {id:'m',kind:'manager',name:'M',managers:[]},
    {id:'p',kind:'publisher',name:'P',managers:['m']},
  ], readers:{r:{config:{httpEnabled:false,streamEnabled:true}}},contracts:[{id:'contract'}],rpc:'https://rpc',chainStatus:'up'});
  assert.equal(model.nodes[0].runtime,'docker');
  assert.deepEqual(model.connections.map((edge)=>edge.transport),['sse','sse','stellar']);
  assert.equal(model.connections[0].state,'configured');
  assert.equal(hostLabel('http://machine.test:3002'),'machine.test:3002');
});

test('el cliente conserva la cabecera de control y comunica errores del backend', async () => {
  let request;
  await requestLocal('containers',{kind:'reader'},'POST',async (url,options)=>{
    request={url,...options};return {ok:true,json:async()=>({id:'one'})};
  });
  assert.equal(request.headers['X-Phonendo-Control'],'local');
  assert.equal(request.url,'/api/local/containers');
  await assert.rejects(()=>requestLocal('containers',undefined,'GET',async()=>({ok:false,json:async()=>({error:'No disponible'})})),/No disponible/);
});
