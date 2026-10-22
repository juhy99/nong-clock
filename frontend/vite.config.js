import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// 사용자 사이트(/)와 관리자 사이트(/admin/)를 한 프로젝트에서 따로 빌드한다.
// /admin/reports 처럼 관리자 사이트 안쪽 주소로 바로 들어와도 관리자 화면(admin/index.html)을 보여주게 한다.
// 실제 배포 서버(nginx 등)에도 같은 규칙이 필요하다: /admin/* → /admin/index.html, 나머지 → /index.html
const adminFallback = () => {
  const rewrite = (req, _res, next) => {
    if (/^\/admin(\/|\?|$)/.test(req.url) && !/\.[a-z0-9]+(\?|$)/i.test(req.url.split("?")[0])) req.url = "/admin/index.html";
    next();
  };
  return {
    name: "admin-fallback",
    // 중괄호 필수: 함수를 돌려주면 Vite 가 "나중에 실행할 훅"으로 착각한다
    configureServer(server) {
      server.middlewares.use(rewrite);
    },
    configurePreviewServer(server) {
      server.middlewares.use(rewrite);
    },
  };
};

// 테스트 모드(VITE_DATA_SOURCE=live): 화면이 /live/... 를 부르면 이 개발 서버가 키를 붙여 기상청·네이버로 보낸다.
// 키는 frontend/.env 에 VITE_ 없이 적는다 → 화면 코드(브라우저)에는 들어가지 않는다. 개발 서버에서만 동작, 배포본에는 없음.
const liveProxy = (env) => {
  if (env.VITE_DATA_SOURCE !== "live") return undefined;
  // 공공데이터포털 키: Decoding 키를 권장. Encoding 키(%가 들어 있음)를 넣어도 그대로 쓴다
  const key = env.DATA_GO_KR_KEY ?? "";
  const serviceKey = key.includes("%") ? key : encodeURIComponent(key);
  return {
    "/live/kma": {
      target: "https://apis.data.go.kr",
      changeOrigin: true,
      rewrite: (p) => `${p.replace(/^\/live\/kma/, "")}${p.includes("?") ? "&" : "?"}serviceKey=${serviceKey}`,
    },
    // 네이버 검색 API 는 2026-07-31 부터 NAVER API HUB(네이버클라우드)로 이전 → HUB 주소·헤더 사용
    "/live/naver": {
      target: "https://naverapihub.apigw.ntruss.com",
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/live\/naver/, ""),
      headers: { "X-NCP-APIGW-API-KEY-ID": (env.NAVER_CLIENT_ID ?? "").trim(), "X-NCP-APIGW-API-KEY": (env.NAVER_CLIENT_SECRET ?? "").trim() },
    },
  };
};

// 테스트 모드: 뉴스 수집기(collector/news)가 저장한 기사 파일을 /live/collected-news 로 보여준다. 파일이 없으면 404 → 화면이 네이버를 직접 부름
const collectedNews = (env) => ({
  name: "collected-news",
  configureServer(server) {
    if (env.VITE_DATA_SOURCE !== "live") return;
    // 관리자 › 데이터 수집: 수집 기록·거른 기사 (collect_log.json, rejected.json, news-recent.json)
    server.middlewares.use("/live/collector-data", async (req, res) => {
      const name = req.url.replace(/^\//, "").split("?")[0];
      if (!/^[a-z_-]+\.json$/.test(name)) return void ((res.statusCode = 404), res.end());
      try {
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(await readFile(resolve(__dirname, "../collector/news/data", name)));
      } catch {
        res.statusCode = 404;
        res.end("{}");
      }
    });
    server.middlewares.use("/live/collected-news", async (_req, res) => {
      try {
        const dir = resolve(__dirname, "../collector/news/data");
        const body = await readFile(resolve(dir, "news-recent.json")).catch(() => readFile(resolve(dir, "news.json")));
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(body);
      } catch {
        res.statusCode = 404;
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end(JSON.stringify({ message: "수집한 기사가 없습니다 (collector/news 에서 python collect_news.py)" }));
      }
    });
  },
});

export default defineConfig(({ mode }) => ({
  plugins: [react(), adminFallback(), collectedNews(loadEnv(mode, __dirname, ""))],
  // 관리자 › 서버 상태의 "빌드 시각" (배포 버전은 VITE_BUILD_SHA·MSG·TIME, deploy/deploy.ps1 이 넣음)
  define: { __BUILT_AT__: JSON.stringify(new Date().toISOString()) },
  // shared/news_rules.json(수집기와 같이 쓰는 뉴스 규칙)이 frontend 밖에 있어 한 단계 위까지 읽게 허용
  server: { port: 5173, proxy: liveProxy(loadEnv(mode, __dirname, "")), fs: { allow: [".."] } },
  build: {
    rollupOptions: {
      input: { main: resolve(__dirname, "index.html"), admin: resolve(__dirname, "admin/index.html") },
    },
  },
}));
