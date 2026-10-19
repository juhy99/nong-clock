import { useEffect, useState } from "react";
import { MOCK_PREFIX, getImage } from "../mocks/images";

/** 사진 주소를 그린다. 가짜 저장소 주소("mock-img:")면 브라우저 저장소에서 꺼내 보여준다. */
export default function Photo({ src, alt = "", className, style }) {
  const [url, setUrl] = useState(src?.startsWith(MOCK_PREFIX) ? null : src);
  useEffect(() => {
    if (!src?.startsWith(MOCK_PREFIX)) return setUrl(src);
    let objectUrl;
    let alive = true;
    getImage(src)
      .then((blob) => {
        if (alive && blob) setUrl((objectUrl = URL.createObjectURL(blob)));
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [src]);
  if (!url) return <div className={`photo-empty ${className ?? ""}`} style={style} aria-label={alt} />;
  return <img src={url} alt={alt} className={className} style={style} loading="lazy" />;
}
