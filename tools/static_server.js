const http = require("http");
const fs = require("fs");
const path = require("path");

const projectRoot = path.resolve(__dirname, "..");
const requestedPort = Number(process.argv[2] || 4173);
const port = Number.isFinite(requestedPort) && requestedPort > 0 ? requestedPort : 4173;

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mjs": "application/javascript; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".task": "application/octet-stream",
  ".txt": "text/plain; charset=utf-8",
  ".wasm": "application/wasm",
};

function sendFile(response, filePath) {
  const extension = path.extname(filePath).toLowerCase();
  response.writeHead(200, {
    "Content-Type": mimeTypes[extension] || "application/octet-stream",
    "Cache-Control": extension === ".html" ? "no-store" : "public, max-age=3600",
  });
  fs.createReadStream(filePath).pipe(response);
}

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(payload));
}

function getRequestPathname(rawUrl) {
  try {
    return new URL(rawUrl || "/", "http://localhost").pathname;
  } catch (error) {
    return null;
  }
}

function isInsideProject(resolvedPath) {
  const relativePath = path.relative(projectRoot, resolvedPath);
  return relativePath === "" || (!relativePath.startsWith("..") && !path.isAbsolute(relativePath));
}

function resolveRequestPath(urlPathname) {
  if (!urlPathname) return null;

  let decodedPath = "/";
  try {
    decodedPath = decodeURIComponent(urlPathname);
  } catch (error) {
    return null;
  }

  const candidatePath = decodedPath === "/" ? "/index.html" : decodedPath;
  const resolvedPath = path.normalize(path.join(projectRoot, candidatePath));

  if (!isInsideProject(resolvedPath)) {
    return null;
  }

  if (fs.existsSync(resolvedPath) && fs.statSync(resolvedPath).isDirectory()) {
    return path.join(resolvedPath, "index.html");
  }

  return resolvedPath;
}

const server = http.createServer((request, response) => {
  const pathname = getRequestPathname(request.url);
  if (pathname === "/health") {
    sendJson(response, 200, {
      status: "static",
      modelLoaded: false,
      mode: "browser-only",
    });
    return;
  }

  if (pathname === "/predict/frame") {
    sendJson(response, 503, {
      word: null,
      confidence: 0,
      error: "Python backend is not running in browser-only mode.",
    });
    return;
  }

  const filePath = resolveRequestPath(pathname);
  if (!filePath) {
    sendJson(response, 403, { error: "Forbidden" });
    return;
  }

  fs.stat(filePath, (error, stats) => {
    if (error || !stats.isFile()) {
      sendJson(response, 404, { error: "Not found" });
      return;
    }

    sendFile(response, filePath);
  });
});

server.on("error", (error) => {
  if (error.code === "EADDRINUSE") {
    console.error(`[ERROR] Port ${port} is already in use. Close the other server window or choose another port.`);
  } else {
    console.error(`[ERROR] Could not start EMAA static server: ${error.message}`);
  }
  process.exitCode = 1;
});

server.listen(port, "127.0.0.1", () => {
  console.log(`EMAA static server running at http://127.0.0.1:${port}`);
});
