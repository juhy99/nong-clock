package com.farm.backend.config;

import com.farm.backend.controller.AdminAuthController;
import com.farm.backend.controller.AdminBoardController;
import com.farm.backend.controller.CommentController;
import com.farm.backend.controller.NoticeController;
import com.farm.backend.controller.PostController;
import com.farm.backend.controller.UserController;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.ErrorResponse;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 회원·게시판·댓글 API 오류를 {"message": "..."} 로 통일 (화면 auth.js 의 springError 가 message 를 보여줌).
 * 서버 내부 오류(DB 등)는 문장을 숨기고 로그에만 남긴다 — 예전에는 e.getMessage() 를 그대로 보내 내부 정보가 보였음.
 * 다른 컨트롤러(시세 등)의 오류 처리는 바꾸지 않도록 회원·게시판 컨트롤러에만 적용.
 */
@RestControllerAdvice(assignableTypes = {UserController.class, PostController.class, CommentController.class,
        AdminAuthController.class, AdminBoardController.class, NoticeController.class,
        com.farm.backend.controller.AdminOpsController.class, com.farm.backend.controller.SiteController.class,
        com.farm.backend.controller.AdminRefreshController.class}) // 11-14 관리자·공지 · 11-17 운영·사이트 설정·데이터 갱신
public class ApiExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Map<String, Object>> api(ApiException e) {
        return ResponseEntity.status(e.getStatus()).body(Map.of("message", e.getMessage()));
    }

    /** @Valid 검사 실패 → 422 (명세서 0장 에러 응답과 같은 코드). 첫 번째 문장을 message 로 */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> invalid(MethodArgumentNotValidException e) {
        List<Map<String, String>> detail = e.getBindingResult().getFieldErrors().stream()
                .map(f -> Map.of("field", f.getField(), "msg", String.valueOf(f.getDefaultMessage())))
                .toList();
        FieldError first = e.getBindingResult().getFieldError();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("message", first == null ? "입력값을 확인하세요" : String.valueOf(first.getDefaultMessage()));
        body.put("detail", detail);
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY).body(body);
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, Object>> unreadable(HttpMessageNotReadableException e) {
        return ResponseEntity.badRequest().body(Map.of("message", "요청 형식이 올바르지 않습니다"));
    }

    /** 주소의 숫자 칸에 글자가 오면 (예: /api/posts/abc, ?page=x) → 400 (예전에는 500 + 오류 로그) */
    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<Map<String, Object>> typeMismatch(MethodArgumentTypeMismatchException e) {
        return ResponseEntity.badRequest().body(Map.of("message", "요청 값을 확인하세요 (" + e.getName() + ")"));
    }

    /** 올린 파일이 한도(50MB)를 넘음 (11-17 월보 PDF) */
    @ExceptionHandler(org.springframework.web.multipart.MaxUploadSizeExceededException.class)
    public ResponseEntity<Map<String, Object>> tooLarge(org.springframework.web.multipart.MaxUploadSizeExceededException e) {
        return ResponseEntity.status(HttpStatus.PAYLOAD_TOO_LARGE).body(Map.of("message", "파일이 너무 커요 (50MB 까지)"));
    }

    /** 파일 올리기 요청인데 파일 칸(file)이 없음 */
    @ExceptionHandler({org.springframework.web.multipart.MultipartException.class, org.springframework.web.multipart.support.MissingServletRequestPartException.class,
            org.springframework.web.bind.MissingServletRequestParameterException.class})
    public ResponseEntity<Map<String, Object>> noFile(Exception e) {
        return ResponseEntity.badRequest().body(Map.of("message", "올릴 파일을 골라 주세요"));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> unknown(Exception e, jakarta.servlet.http.HttpServletRequest req) {
        OpsLog.note(req, e);   // 11-17: 관리자 '오류 기록'에 오류 종류를 남김
        // 스프링이 상태 코드를 정해 둔 오류(잘못된 메서드 405, 형식 415 등)는 그 코드 그대로
        if (e instanceof ErrorResponse er)
            return ResponseEntity.status(er.getStatusCode()).body(Map.of("message", "요청을 처리할 수 없습니다 (" + er.getStatusCode().value() + ")"));
        log.error("회원·게시판 API 오류", e);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Map.of("message", "서버 오류가 발생했습니다. 잠시 뒤 다시 시도하세요"));
    }
}
