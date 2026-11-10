package com.farm.backend.service;

import com.farm.backend.config.ApiException;
import com.farm.backend.domain.Post;
import com.farm.backend.repository.PostRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class PostService {

    private final PostRepository postRepository;
    private final UserService userService;

    public PostService(PostRepository postRepository, UserService userService) {
        this.postRepository = postRepository;
        this.userService = userService;
    }

    /**
     * 게시글 작성. authorId 는 컨트롤러가 세션에서 꺼낸 로그인 회원 번호만 받는다.
     * 로그인한 뒤 정지·탈퇴된 회원(세션은 아직 살아 있음)은 여기서 막는다.
     */
    @Transactional
    public Long writePost(Long authorId, String category, String title, String body) {
        if (userService.activeUser(authorId) == null)
            throw new ApiException(HttpStatus.FORBIDDEN, "글을 쓸 수 없는 계정입니다");
        Post post = new Post();
        post.setAuthorId(authorId);
        post.setCategory(category);
        post.setTitle(title);
        post.setBody(body);
        post.setViews(0);

        postRepository.save(post);
        return post.getId();
    }

    /**
     * 전체 게시글 목록 조회
     */
    public List<Post> getAllPosts() {
        return postRepository.findAll();
    }
}
