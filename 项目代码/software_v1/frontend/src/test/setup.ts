import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from '../mocks/server';

if (!Blob.prototype.text) {
  Object.defineProperty(Blob.prototype, 'text', {
    value() {
      return new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsText(this);
      });
    },
  });
}

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
