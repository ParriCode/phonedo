/** Único transporte HTTP del operador. No conoce nodos ni coordenadas. */
export async function requestLocal(path, body, method = 'POST', fetcher = fetch) {
  const response = await fetcher('/api/local/' + path, {
    method, cache: 'no-store', headers: { 'Content-Type': 'application/json', 'X-Phonendo-Control': 'local' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(35000),
  });
  const result = await response.json().catch(() => ({ error: 'Arranca el panel con ./tools/web.sh' }));
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}
