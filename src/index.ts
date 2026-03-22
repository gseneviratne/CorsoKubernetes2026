import http from "node:http";

const port = Number(process.env.PORT) || 3000;
const host = "0.0.0.0";

const server = http.createServer((_req, res) => {
  res.setHeader("Content-Type", "text/plain; charset=utf-8");
  res.end("OK — Corso Kubernetes 2026\n");
});

server.listen(port, host, () => {
  console.log(`Listening on http://${host}:${port}`);
});
