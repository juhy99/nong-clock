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
    "/live/naver": {
      target: "https://openapi.naver.com",
      changeOrigin: true,
      rewrite: (p) => p.replace(/^\/live\/naver/, ""),
      headers: { "X-Naver-Client-Id": env.NAVER_CLIENT_ID ?? "", "X-Naver-Client-Secret": env.NAVER_CLIENT_SECRET ?? "" },
    },
  };
};

export default defineConfig(({ mode }) => ({
  plugins: [react(), adminFallback()],
  server: { port: 5173, proxy: liveProxy(loadEnv(mode, __dirname, "")) },
  build: {
    rollupOptions: {
      input: { main: resolve(__dirname, "index.html"), admin: resolve(__dirname, "admin/index.html") },
    },
  },
}));
