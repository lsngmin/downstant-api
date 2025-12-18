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


@app.post("/api/v1/contact")
async def receive_contact(request: schemas.ContactRequest):
    # 2. 전송된 데이터 확인 (콘솔 로그)
    print("\n" + "=" * 30)
    print(f"📩 새로운 문의 접수!")
    print(f"👤 유저: {request.user_id}")
    print(f"📱 기기: {request.device_info} (iOS {request.os_version})")
    print(f"📄 내용: {request.content}")
    print("=" * 30 + "\n")

    # 3. 비즈니스 로직 (지금은 바로 성공 응답)
    # 나중에 여기에 DB 저장(SQLAlchemy)이나 슬랙 알림 연동을 추가하면 됩니다.

    return {
        "status": "success",
        "message": "문의가 서버에 정상적으로 접수되었습니다.",
        "received_data": request.dict()  # 확인용으로 받은 데이터를 다시 쏴줌
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)