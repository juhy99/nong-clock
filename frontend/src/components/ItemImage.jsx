// 품목 대표 사진. src/assets/items/<품목코드>.(png|jpg|jpeg|webp) 파일이 있으면 그 사진을, 없으면 이모지를 보여준다.
// 사진은 빌드할 때 자동으로 찾아서 넣으므로, 파일만 폴더에 넣으면 코드 수정 없이 바뀐다 (규칙: src/assets/items/README.md).
const FILES = import.meta.glob("../assets/items/*.{png,jpg,jpeg,webp}", { eager: true, import: "default" });
const BY_CODE = Object.fromEntries(Object.entries(FILES).map(([path, url]) => [path.split("/").pop().replace(/\.\w+$/, ""), url]));

export const hasItemImage = (code) => !!BY_CODE[code];

/**
 * @param {{code: string, emoji?: string, alt?: string, className?: string}} props
 */
export default function ItemImage({ code, emoji = "🧺", alt = "", className = "" }) {
  const src = BY_CODE[code];
  if (src) return <img src={src} alt={alt} className={`item-img ${className}`} loading="lazy" />;
  return (
    <span className={`item-emoji ${className}`} role="img" aria-label={alt}>
      {emoji}
    </span>
  );
}
