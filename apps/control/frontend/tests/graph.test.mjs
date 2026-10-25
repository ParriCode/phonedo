import test from 'node:test';
import assert from 'node:assert/strict';
import { edgeGeometry, labelPosition } from '../src/graph.mjs';

test('las flechas horizontales terminan antes del borde del destino', () => {
  const edge = edgeGeometry({left:20,top:100,width:120,height:100}, {left:240,top:100,width:120,height:100});
  assert.match(edge.d, /^M 143 150 /);
  assert.ok(edge.d.endsWith('L 235 150'));
});

test('las ramas verticales entran por arriba en ambos destinos', () => {
  for (const left of [20,280]) {
    const edge = edgeGeometry({left:150,top:100,width:120,height:100}, {left,top:300,width:120,height:100},true);
    assert.match(edge.d, /^M 210 203 /);
    assert.ok(edge.d.endsWith(`L ${left+60} 295`));
  }
});

test('las conexiones de derecha a izquierda usan los lados correctos', () => {
  const edge = edgeGeometry({left:300,top:20,width:120,height:100}, {left:20,top:20,width:120,height:100});
  assert.match(edge.d, /^M 297 70 /);
  assert.ok(edge.d.endsWith('L 145 70'));
});

test('HTTP y SSE paralelos conservan geometrías y etiquetas distintas', () => {
  const a = {left:20,top:100,width:120,height:100}, b = {left:240,top:100,width:120,height:100};
  const http = edgeGeometry(a,b), sse = edgeGeometry(a,b,false,30);
  assert.notEqual(http.d,sse.d);
  assert.notEqual(http.y,sse.y);
  assert.ok(sse.d.endsWith('L 235 150'));
});

test('una rama paralela vertical conserva la entrada por arriba', () => {
  const edge = edgeGeometry({left:100,top:100,width:110,height:100}, {left:20,top:250,width:110,height:100},true,30);
  const coordinates = edge.d.match(/-?\d+(?:\.\d+)?/g).map(Number);
  assert.ok(coordinates[5] < coordinates[7]);
  assert.ok(edge.d.endsWith('L 75 245'));
});

test('las etiquetas largas evitan los nodos a ancho de escritorio reducido', () => {
  const label = labelPosition({x:404,y:214}, {width:110,height:14,topOffset:-11},
    [{left:235,top:112,width:126,height:108}], {width:608,height:377});
  assert.ok(label.x - 55 >= 365 || label.y - 11 >= 224 || label.y + 3 <= 108);
});

test('las etiquetas se mantienen dentro del ancho disponible', () => {
  const label = labelPosition({x:390,y:150}, {width:100,height:14,topOffset:-11}, [], {width:300,height:400});
  assert.ok(label.x + 50 <= 292);
  assert.ok(label.x - 50 >= 8);
});
