# 서버용 회원·게시판 백엔드: docker compose 의 backend (서버 .env 에 COMPOSE_PROFILES=spring 일 때만)
FROM gradle:8.5-jdk17 AS build
WORKDIR /app
COPY build.gradle ./
COPY src ./src
RUN gradle bootJar --no-daemon -q

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
# 11-13 보안: 관리자(root)가 아닌 일반 사용자로 실행 — 혹시 뚫려도 컨테이너 안에서 할 수 있는 일이 적게
RUN useradd --system --uid 1001 --no-create-home spring
USER spring
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
