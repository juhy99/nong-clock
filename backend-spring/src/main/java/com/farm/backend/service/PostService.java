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
     * 다른 기기에서 탈퇴해 회원이 지워졌는데 이 세션이 남아 있으면 여기서 막는다.
     */
    @Transactional
    public Long writePost(Long authorId, String category, String title, String body) {
        if (userService.findUser(authorId) == null)
            throw new ApiException(HttpStatus.UNAUTHORIZED, "로그인이 필요합니다");
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
