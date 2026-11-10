package com.farm.backend.config;

import org.springframework.http.HttpStatus;

/** 화면에 그대로 보여줘도 되는 오류 (상태 코드 + 한국어 문장). ApiExceptionHandler 가 {"message": "..."} 로 바꿔 보냄 */
public class ApiException extends RuntimeException {
    private final HttpStatus status;

    public ApiException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
