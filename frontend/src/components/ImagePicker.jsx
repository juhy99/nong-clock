import { useEffect, useRef, useState } from "react";
import { MAX_IMAGES, MAX_IMAGE_MB, checkImage } from "../api/upload";

/**
 * 사진 고르기 + 미리보기. 실제 업로드는 글/경매를 등록할 때(uploadImages) 한 번에 한다.
 * @param {{files: File[], onChange: (files: File[]) => void, max?: number}} props
 */
export default function ImagePicker({ files, onChange, max = MAX_IMAGES }) {
  const input = useRef(null);
  const [error, setError] = useState("");
  const [previews, setPreviews] = useState([]);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  function add(list) {
    const picked = [...list];
    const bad = picked.map(checkImage).find(Boolean);
    const ok = picked.filter((f) => !checkImage(f));
    const room = max - files.length;
    setError(bad || (ok.length > room ? `사진은 최대 ${max}장까지 올릴 수 있습니다` : ""));
    if (ok.length && room > 0) onChange([...files, ...ok.slice(0, room)]);
  }

  return (
    <div className="image-picker">
      <div className="thumbs">
        {previews.map((u, i) => (
          <div key={u} className="thumb">
            <img src={u} alt={`사진 ${i + 1}`} />
            {i === 0 && <span className="badge green">대표</span>}
            <button type="button" aria-label={`사진 ${i + 1} 빼기`} onClick={() => onChange(files.filter((_, k) => k !== i))}>×</button>
          </div>
        ))}
        {files.length < max && (
          <button
            type="button"
            className="thumb add"
            onClick={() => input.current.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              add(e.dataTransfer.files);
            }}
          >
            📷<span className="small">사진 추가<br />{files.length}/{max}</span>
          </button>
        )}
      </div>
      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/gif"
        multiple
        hidden
        onChange={(e) => {
          add(e.target.files);
          e.target.value = "";
        }}
      />
      <span className={`hint ${error ? "error" : ""}`}>{error || `JPG·PNG·WEBP·GIF, 장당 ${MAX_IMAGE_MB}MB 이하. 첫 번째 사진이 대표 사진이 돼요.`}</span>
    </div>
  );
}
