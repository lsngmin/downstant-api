from fastapi import FastAPI, HTTPException
import yt_dlp
import asyncio
from sqlalchemy.orm import Session
from database import get_db, engine
import models, schemas
from MediaUrlRequest import UrlContainer
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, Depends
from urllib.parse import urlparse
models.Base.metadata.create_all(bind=engine)
app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/support", response_class=HTMLResponse)
async def get_support(request: Request):
    return templates.TemplateResponse("support.html", {"request": request})
@app.get("/privacy", response_class=HTMLResponse)
async def get_privacy(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

# 2. 관리자 페이지 (DB에서 데이터 읽어서 보여줌)
@app.get("/admin/contacts", response_class=HTMLResponse)
async def admin_page(request: Request, db: Session = Depends(get_db)):
    # DB에서 최신순으로 문의사항 50개 가져오기
    contacts = db.query(models.Contact).order_by(models.Contact.created_at.desc()).limit(50).all()
    return templates.TemplateResponse("admin.html", {"request": request, "contacts": contacts})

@app.post("/extract")
async def extract_twitter_media(request: UrlContainer):
    print(f"🔎 추출 요청 수신: {request.url}")
    ydl_opts = {
        'format': 'best',
        'quiet': False,  # 오류를 자세히 보기 위해 로그를 켭니다.
        'no_warnings': False,
        # 🔑 트위터 차단을 피하기 위한 핵심 헤더
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://x.com/',
        }
    }
    try:
        loop = asyncio.get_event_loop()

        # 💡 yt-dlp의 정보를 실시간으로 확인하기 위해 비동기 실행
        def get_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(request.url, download=False)

        info = await loop.run_in_executor(None, get_info)

        # 주소 추출 로직
        download_url = info.get('url')

        # 만약 직접적인 url이 없다면 formats 목록에서 찾아보기
        if not download_url and 'formats' in info:
            # 고화질 mp4 우선 선택
            formats = [f for f in info['formats'] if f.get('ext') == 'mp4']
            if formats:
                download_url = formats[-1].get('url')  # 보통 마지막이 최고화질

        if not download_url:
            raise Exception("미디어 주소를 추출하지 못했습니다.")

        print(f"✅ 추출 완료: {info.get('title')[:20]}...")
        return {
            "status": "success",
            "download_url": download_url,
            "title": info.get('title')
        }

    except Exception as e:
        print(f"❌ 상세 에러: {str(e)}")
        raise HTTPException(status_code=400, detail=f"추출 실패: {str(e)}")


def _normalize_url(raw_url: str) -> str:
    cleaned = raw_url.strip()
    if "://" not in cleaned:
        return f"https://{cleaned}"
    return cleaned


def _is_tiktok_url(raw_url: str) -> bool:
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return False
    host = (parsed.netloc or "").lower()
    return host.endswith("tiktok.com") or host.endswith("tiktokv.com")


def _build_format_entry(fmt: dict) -> dict:
    height = fmt.get("height")
    width = fmt.get("width")
    fps = fmt.get("fps")
    tbr = fmt.get("tbr")
    vbr = fmt.get("vbr")
    size = fmt.get("filesize") or fmt.get("filesize_approx")

    label_parts = []
    if height:
        label_parts.append(f"{height}p")
    elif width and height:
        label_parts.append(f"{width}x{height}")
    if fps:
        label_parts.append(f"{int(fps)}fps" if isinstance(fps, (int, float)) else f"{fps}fps")
    bitrate = tbr or vbr
    if bitrate:
        label_parts.append(f"{round(bitrate)}kbps")
    if size:
        size_mb = size / (1024 * 1024)
        label_parts.append(f"{size_mb:.1f}MB")

    return {
        "url": fmt.get("url"),
        "format_id": fmt.get("format_id"),
        "ext": fmt.get("ext"),
        "width": width,
        "height": height,
        "fps": fps,
        "tbr": tbr,
        "vbr": vbr,
        "filesize": size,
        "label": " ".join(label_parts) or "MP4",
    }


def _extract_download_urls(info: dict) -> list[dict]:
    urls = []
    seen = set()
    formats = info.get("formats") or []
    for fmt in formats:
        url = fmt.get("url")
        if not url:
            continue
        if fmt.get("ext") != "mp4":
            continue
        protocol = (fmt.get("protocol") or "").lower()
        if "m3u8" in protocol or "dash" in protocol:
            continue
        if url.endswith(".m3u8"):
            continue
        if url in seen:
            continue
        urls.append(_build_format_entry(fmt))
        seen.add(url)

    if not urls:
        url = info.get("url")
        if url and info.get("ext") == "mp4" and not url.endswith(".m3u8"):
            return [_build_format_entry(info)]

    urls.sort(
        key=lambda item: (item.get("height") or 0, item.get("tbr") or 0),
        reverse=True,
    )
    return [urls[0]] if urls else []


@app.post("/extract/tiktok")
async def extract_tiktok_media(request: UrlContainer):
    raw_url = _normalize_url(request.url)
    if not _is_tiktok_url(raw_url):
        raise HTTPException(status_code=400, detail="TikTok URL만 지원합니다.")

    ydl_opts = {
        "format": "best",
        "quiet": False,
        "no_warnings": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.tiktok.com/",
        },
    }

    try:
        loop = asyncio.get_event_loop()

        def get_info():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(raw_url, download=False)

        info = await loop.run_in_executor(None, get_info)
        download_urls = _extract_download_urls(info)
        if not download_urls:
            raise Exception("다운로드 가능한 주소를 찾지 못했습니다.")

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "download_urls": download_urls,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"추출 실패: {str(e)}")


@app.post("/api/v1/contact")
async def receive_contact(
    request: schemas.ContactRequest,
    db: Session = Depends(get_db)  # 1. DB 세션 주입 추가
):
    # 2. 콘솔 로그 (확인용)
    print(f"📩 문의 접수 시작: {request.user_id}")

    try:
        # 3. DB 모델 객체 생성
        new_contact = models.Contact(
            user_id=request.user_id,
            email=request.email,
            content=request.content,
            device_info=request.device_info,
            os_version=request.os_version,
        )

        # 4. DB에 저장 및 커밋
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact) # 저장된 후 생성된 ID 등을 다시 읽어옴

        print(f"✅ DB 저장 완료: ID {new_contact.id}")

        return {
            "status": "success",
            "message": "문의가 DB에 안전하게 저장되었습니다.",
            "id": new_contact.id
        }

    except Exception as e:
        db.rollback() # 에러 발생 시 진행 중인 작업 취소
        print(f"❌ DB 저장 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="서버 DB 저장 중 오류가 발생했습니다.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
