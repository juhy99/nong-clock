package com.farm.backend.service;

import com.farm.backend.domain.Post;
import com.farm.backend.repository.PostRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PostService {

    private final PostRepository postRepository;

    /**
     * 게시글 작성
     */
    @Transactional
    public Long writePost(Long authorId, String category, String title, String body) {
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