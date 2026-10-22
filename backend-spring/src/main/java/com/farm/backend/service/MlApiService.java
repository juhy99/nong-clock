package com.farm.backend.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

@Service
public class MlApiService {

    private final WebClient webClient;

    public MlApiService(WebClient.Builder webClientBuilder, @Value("${ml.api.url}") String mlApiUrl) {
        this.webClient = webClientBuilder.baseUrl(mlApiUrl).build();
    }

    public String getPrediction(Object requestData) {
        // FastAPI의 예측 엔드포인트(예: /predict)로 POST 요청을 보내고 결과를 받음
        return webClient.post()
                .uri("/predict")
                .bodyValue(requestData)
                .retrieve()
                .bodyToMono(String.class)
                .block(); // 동기식으로 결과를 기다릴 경우 block() 사용 (비동기는 Mono/Flux 활용)
    }
}