// 사진 업로드. 지금은 브라우저 안(IndexedDB)에 저장하고, Spring 이 생기면
// uploadImages 안쪽만 `POST /api/uploads` (multipart/form-data) 호출로 바꾸면 된다. 돌려주는 값은 사진 주소 목록.
import { putImage } from "../mocks/images";

export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
export const MAX_IMAGE_MB = 10;
export const MAX_IMAGES = 5;

/** 사진 파일이 올릴 수 있는 것인지 확인. 문제가 있으면 이유를, 없으면 null */
export function checkImage(file) {
  if (!IMAGE_TYPES.includes(file.type)) return `${file.name}: JPG·PNG·WEBP·GIF 사진만 올릴 수 있습니다`;
  if (file.size > MAX_IMAGE_MB * 1024 * 1024) return `${file.name}: ${MAX_IMAGE_MB}MB 이하만 올릴 수 있습니다`;
  return null;
}

/** 긴 변을 maxSide 로 줄인 JPEG (휴대폰 사진은 수 MB 라서 그대로 두면 화면이 느려진다) */
async function shrink(file, maxSide = 1280, quality = 0.82) {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
}

/** @param {File[]} files @returns {Promise<string[]>} 사진 주소 목록 (순서 유지) */
export async function uploadImages(files) {
  for (const f of files) {
    const err = checkImage(f);
    if (err) throw new Error(err);
  }
  const urls = [];
  for (const f of files) urls.push(await putImage(f.type === "image/gif" ? f : await shrink(f)));
  return urls;
}
