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
    expect(result.current).toEqual([{ id: 'b:r-m', edgeId: 'r-m', level: 'error', reverse: false }]);
  });

  it('usa las conexiones de entrada si el nodo no tiene salida', () => {
    const { result, rerender } = renderHook(({ logs }) => useMessagePulses(logs, connections), { initialProps: { logs: [] } });
    rerender({ logs: [log('d', 's')] });
    expect(result.current).toEqual([{ id: 'd:m-s', edgeId: 'm-s', level: 'info', reverse: true }]);
  });
});
