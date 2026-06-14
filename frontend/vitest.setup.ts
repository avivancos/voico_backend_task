import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./src/test/msw/server";

// MSW intercepts the network so the real api.ts/axios runs in api.test.ts; an unhandled request is
// an error (component tests vi.mock the api module and make none).
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());
