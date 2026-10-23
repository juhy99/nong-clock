# 서버용 회원·게시판 백엔드: docker compose 의 backend (서버 .env 에 COMPOSE_PROFILES=spring 일 때만)
FROM gradle:8.5-jdk17 AS build
WORKDIR /app
COPY build.gradle ./
COPY src ./src
RUN gradle bootJar --no-daemon -q

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
