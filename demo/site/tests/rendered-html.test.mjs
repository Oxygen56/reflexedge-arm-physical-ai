import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("server-renders the ReflexEdge evidence demo", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>ReflexEdge — Verifiable Physical AI on Arm<\/title>/i);
  assert.match(html, /A brake reflex/);
  assert.match(html, /VERIFIED ARM64 RUN/);
  assert.match(html, /6\.04/);
  assert.match(html, /ADDED FALSE NEGATIVES/);
  assert.match(html, /One command/);
  assert.match(html, /CLAIM BOUNDARY/);
  assert.doesNotMatch(html, /codex-preview|react-loading-skeleton/i);
});

test("keeps public claims and boundaries together", async () => {
  const response = await render();
  const html = await response.text();
  assert.match(html, /CPU time per inference is an energy proxy/);
  assert.match(html, /not field safety certification/);
  assert.match(html, /MIT/);
  assert.match(html, /Arm NEON/);
});
