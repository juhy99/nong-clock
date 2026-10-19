// 업로드한 사진의 가짜 저장소. 사진은 커서 localStorage(5MB 제한)에 넣지 않고 브라우저 IndexedDB 에 둔다.
// Spring 이 생기면 사진은 서버(또는 S3 같은 저장소)에 올라가고, 화면에는 사진 주소(URL)만 오간다.
const DB = "farmbid-mock-images";
const STORE = "images";
export const MOCK_PREFIX = "mock-img:";

function open() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx(mode, fn) {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(req?.result);
    t.onerror = () => reject(t.error);
  });
}

/** Blob 저장 → "mock-img:<id>" 주소 */
export async function putImage(blob) {
  const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;
  await tx("readwrite", (s) => s.put(blob, id));
  return MOCK_PREFIX + id;
}

export const getImage = (url) => tx("readonly", (s) => s.get(url.slice(MOCK_PREFIX.length)));

export const clearImages = () => tx("readwrite", (s) => s.clear());
