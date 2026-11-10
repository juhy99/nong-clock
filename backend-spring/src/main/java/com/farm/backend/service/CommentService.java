package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.Post;
import com.farm.backend.domain.PostComment;
import com.farm.backend.domain.User;
import com.farm.backend.dto.CommentResponse;
import com.farm.backend.repository.PostCommentRepository;
import com.farm.backend.repository.PostRepository;
import com.farm.backend.repository.UserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 댓글·답글 (명세서 2-10, 11-10). 화면 가짜 데이터(frontend/src/api/board.js)와 같은 규칙:
 * - 답글은 1단계까지: 답글에 답하면 같은 원댓글 아래에 붙음
 * - 1~500자 (앞뒤 공백 뺀 길이)
 * - 지운 댓글에는 답글을 달 수 없음
 * - 지울 때 살아 있는 답글이 있으면 내용만 비우고 "삭제된 댓글"로 남김, 없으면 행을 지움.
 *   답글을 지워서 "삭제된 댓글"인 원댓글에 남은 답글이 없어지면 원댓글 자리도 지움
 * - 쓰기·지우기는 로그인한 회원(세션)만. 지우기는 본인 댓글만
 * 아직 없는 것: 알림(알림 표가 없음), 관리자 삭제(관리자 표시 열이 없음), 게시판 이용 제한 확인
 */
@Service
@Transactional(readOnly = true)
public class CommentService {
    static final int MAX_LEN = 500;

    private final PostCommentRepository comments;
    private final PostRepository posts;
    private final UserRepository users;

    public CommentService(PostCommentRepository comments, PostRepository posts, UserRepository users) {
        this.comments = comments;
        this.posts = posts;
        this.users = users;
    }

    private Post visiblePost(Long postId) {
        Post post = postId == null ? null : posts.findById(postId).orElse(null);
        if (post == null || (post.getStatus() != null && !"VISIBLE".equals(post.getStatus())))
            throw new ApiException(HttpStatus.NOT_FOUND, "삭제되었거나 볼 수 없는 글입니다");
        return post;
    }

    /** GET /api/posts/{postId}/comments: 원댓글 목록, 각 원댓글의 replies 에 답글 */
    public List<CommentResponse> list(Long postId) {
        visiblePost(postId);
        List<PostComment> rows = comments.findByPostIdOrderByIdAsc(postId);
        Set<Long> authorIds = rows.stream().map(PostComment::getAuthorId).collect(Collectors.toSet());
        Map<Long, String> names = new HashMap<>();
        for (User u : users.findAllById(authorIds)) names.put(u.getId(), u.getName());

        Map<Long, List<CommentResponse>> replies = new HashMap<>();
        for (PostComment c : rows)
            if (c.getParentId() != null)
                replies.computeIfAbsent(c.getParentId(), k -> new ArrayList<>()).add(toResponse(c, names, null));
        List<CommentResponse> top = new ArrayList<>();
        for (PostComment c : rows)
            if (c.getParentId() == null)
                top.add(toResponse(c, names, replies.getOrDefault(c.getId(), List.of())));
        return top;
    }

    /** POST /api/posts/{postId}/comments. authorId 는 세션 회원 번호 */
    @Transactional
    public CommentResponse create(Long authorId, Long postId, String body, Long parentId) {
        User author = authorId == null ? null : users.findById(authorId).orElse(null);
        if (author == null) throw new ApiException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다");
        String text = body == null ? "" : body.trim();
        if (text.isEmpty()) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "댓글 내용을 입력하세요");
        if (text.length() > MAX_LEN) throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "댓글은 500자까지 쓸 수 있습니다");
        Post post = visiblePost(postId);

        Long rootId = null;
        if (parentId != null) {
            PostComment parent = comments.findById(parentId).orElse(null);
            if (parent == null || !parent.getPostId().equals(post.getId()) || parent.isDeleted())
                throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "삭제된 댓글에는 답글을 달 수 없습니다");
            rootId = parent.getParentId() != null ? parent.getParentId() : parent.getId(); // 답글의 답글은 같은 원댓글 아래로
        }
        PostComment c = new PostComment();
        c.setPostId(post.getId());
        c.setParentId(rootId);
        c.setAuthorId(author.getId());
        c.setBody(text);
        c.setDeleted(false);
        comments.save(c);
        return toResponse(c, Map.of(author.getId(), author.getName()), rootId == null ? List.of() : null);
    }

    /** DELETE /api/comments/{id}: 본인 댓글만 */
    @Transactional
    public void delete(Long userId, Long commentId) {
        PostComment c = commentId == null ? null : comments.findById(commentId).orElse(null);
        if (c == null) throw new ApiException(HttpStatus.NOT_FOUND, "이미 지워진 댓글입니다");
        if (!c.getAuthorId().equals(userId)) throw new ApiException(HttpStatus.FORBIDDEN, "본인 댓글만 지울 수 있습니다");

        if (comments.existsByParentIdAndDeletedFalse(c.getId())) {
            c.setDeleted(true); // 답글이 살아 있으면 자리만 남김
            c.setBody("");
            comments.save(c);
            return;
        }
        comments.delete(c); // 남은(이미 지운) 답글은 DB 가 같이 지움
        comments.flush();
        if (c.getParentId() != null) {
            PostComment parent = comments.findById(c.getParentId()).orElse(null);
            if (parent != null && parent.isDeleted() && !comments.existsByParentIdAndDeletedFalse(parent.getId()))
                comments.delete(parent); // 빈 "삭제된 댓글" 자리 정리
        }
    }

    private static CommentResponse toResponse(PostComment c, Map<Long, String> names, List<CommentResponse> replies) {
        return new CommentResponse(c.getId(), c.getParentId(), c.getAuthorId(), names.getOrDefault(c.getAuthorId(), "알 수 없음"),
                c.isDeleted() ? "" : c.getBody(), c.getCreatedAt(), c.isDeleted(), replies);
    }
}
