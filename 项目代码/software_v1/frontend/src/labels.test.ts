import { describe, expect, it } from 'vitest';
import { formatDateTime, percent, shortId } from './labels';

describe('labels', () => {
  it('reads naive backend timestamps as UTC', () => {
    expect(formatDateTime('2026-11-02T12:58:49.703748')).toBe(formatDateTime('2026-11-02T12:58:49Z'));
    expect(formatDateTime('2026-11-02T12:58:49+08:00')).toBe(formatDateTime('2026-11-02T04:58:49Z'));
  });

  it('formats percentages and shortens long ids', () => {
    expect(percent(0.6542)).toBe('65.4%');
    expect(percent(0.5, 0)).toBe('50%');
    expect(shortId('5d6c58573b3ef5732e32b24dc6119369')).toBe('5d6c5857…c6119369');
    expect(shortId('short-id')).toBe('short-id');
  });
});
