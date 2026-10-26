import { describe, expect, it } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useMessagePulses } from './useMessagePulses.js';

const connections = [{ id: 'r-m', sourceId: 'r', targetId: 'm' }, { id: 'm-s', sourceId: 'm', targetId: 's' }];
const log = (id, node, extra = {}) => ({ id, node, level: 'info', ...extra });

describe('useMessagePulses', () => {
  it('lanza pulsos solo para logs nuevos y no históricos', () => {
    const { result, rerender } = renderHook(({ logs }) => useMessagePulses(logs, connections), { initialProps: { logs: [log('a', 'r')] } });
    expect(result.current).toEqual([]);
    rerender({ logs: [log('b', 'r', { level: 'error' }), log('c', 'm', { historical: true }), log('a', 'r')] });
    expect(result.current).toEqual([{ id: 'b:r-m', edgeId: 'r-m', level: 'error', reverse: false, delay: 0 }]);
  });

  it('escalona los pulsos que llegan juntos por el mismo cable', () => {
    const { result, rerender } = renderHook(({ logs }) => useMessagePulses(logs, connections), { initialProps: { logs: [] } });
    rerender({ logs: [log('f', 'r'), log('e', 'r')] });
    expect(result.current.map((pulse) => [pulse.id, pulse.delay])).toEqual([['e:r-m', 0], ['f:r-m', 180]]);
  });

  it('usa las conexiones de entrada si el nodo no tiene salida', () => {
    const { result, rerender } = renderHook(({ logs }) => useMessagePulses(logs, connections), { initialProps: { logs: [] } });
    rerender({ logs: [log('d', 's')] });
    expect(result.current).toEqual([{ id: 'd:m-s', edgeId: 'm-s', level: 'info', reverse: true, delay: 0 }]);
  });
});
