import { resolve } from "node:path";
import { defineConfig } from "vite";
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

export default defineConfig({
  plugins: [react(), adminFallback()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      input: { main: resolve(__dirname, "index.html"), admin: resolve(__dirname, "admin/index.html") },
    },
  },
});
