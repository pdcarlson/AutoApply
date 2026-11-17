import { describe, expect, it } from 'vitest';
import {
  buttonOf,
  isPaste,
  keyInput,
  pictureBox,
  pointIn,
  socketUrl,
  wheelPixels,
} from './protocol';

const key = (init: Partial<KeyboardEventInit> & { key: string }) =>
  new KeyboardEvent('keydown', init);

describe('socketUrl', () => {
  it('turns the API path into a WebSocket URL on the API origin', () => {
    expect(socketUrl('/api/jobs/j1/live', 'http://localhost:5173/api/')).toBe(
      'ws://localhost:5173/api/jobs/j1/live',
    );
    expect(socketUrl('/api/jobs/j1/live', 'https://app.example/api/')).toBe(
      'wss://app.example/api/jobs/j1/live',
    );
  });

  it('keeps a full URL to another host, such as a cloud streaming gateway', () => {
    expect(socketUrl('wss://stream.example/v/abc?token=t', 'http://localhost:5173/')).toBe(
      'wss://stream.example/v/abc?token=t',
    );
  });
});

describe('pictureBox and pointIn', () => {
  const frame = { left: 100, top: 50, width: 800, height: 800 };

  it('letterboxes a wide picture in a square frame', () => {
    expect(pictureBox(frame, 1280, 720)).toEqual({ left: 100, top: 225, width: 800, height: 450 });
  });

  it('maps a click to fractions of the picture, clamped at its edges', () => {
    const box = pictureBox(frame, 1280, 720);
    expect(pointIn(box, 500, 450)).toEqual({ x: 0.5, y: 0.5 });
    expect(pointIn(box, 0, 100)).toEqual({ x: 0, y: 0 });
    expect(pointIn(box, 5000, 5000)).toEqual({ x: 1, y: 1 });
  });
});

describe('keyInput', () => {
  it('sends the text a plain key types', () => {
    expect(keyInput('down', key({ key: 'A', code: 'KeyA', shiftKey: true }))).toMatchObject({
      type: 'key',
      action: 'down',
      key: 'A',
      code: 'KeyA',
      text: 'A',
      modifiers: { shift: true, ctrl: false },
    });
    expect(keyInput('down', key({ key: 'Enter' })).type === 'key').toBe(true);
    expect(keyInput('down', key({ key: 'Enter' }))).toMatchObject({ text: '\r' });
  });

  it('sends no text for shortcuts, named keys and key releases', () => {
    expect(keyInput('down', key({ key: 'a', ctrlKey: true }))).toMatchObject({
      text: '',
      modifiers: { ctrl: true },
    });
    expect(keyInput('down', key({ key: 'Backspace' }))).toMatchObject({ text: '' });
    expect(keyInput('up', key({ key: 'a' }))).toMatchObject({ text: '' });
  });
});

describe('small helpers', () => {
  it('names mouse buttons', () => {
    expect([0, 1, 2, 7].map(buttonOf)).toEqual(['left', 'middle', 'right', 'none']);
  });

  it('spots paste', () => {
    expect(isPaste(key({ key: 'v', ctrlKey: true }))).toBe(true);
    expect(isPaste(key({ key: 'V', metaKey: true }))).toBe(true);
    expect(isPaste(key({ key: 'v' }))).toBe(false);
  });

  it('converts wheel lines and pages to page pixels', () => {
    expect(wheelPixels(100, 0, 600, 0.5)).toBe(200);
    expect(wheelPixels(3, 1, 600, 1)).toBe(48);
    expect(wheelPixels(1, 2, 600, 1)).toBe(600);
  });
});
