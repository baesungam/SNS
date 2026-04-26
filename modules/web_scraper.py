import requests
from bs4 import BeautifulSoup
import re


def scrape_business_info(url: str) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    info = {
        "url": url,
        "description": "",
        "address": "",
        "phone": "",
        "hours": "",
        "raw_text": "",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = response.apparent_encoding or "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find(
            "meta", attrs={"property": "og:description"}
        )
        if meta_desc:
            info["description"] = meta_desc.get("content", "")

        text = soup.get_text(separator="\n", strip=True)
        lines = [
            line.strip()
            for line in text.split("\n")
            if line.strip() and len(line.strip()) > 3
        ]
        info["raw_text"] = "\n".join(lines[:120])

        address_pattern = re.search(
            r"(서울|경기|부산|인천|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주).{2,30}(동|로|길)\s*\d*",
            text,
        )
        if address_pattern:
            info["address"] = address_pattern.group().strip()

        phone_pattern = re.search(r"0\d{1,2}[-.\s]\d{3,4}[-.\s]\d{4}", text)
        if phone_pattern:
            info["phone"] = phone_pattern.group().strip()

        hours_keywords = ["영업시간", "운영시간", "오픈", "마감", "브레이크타임"]
        for keyword in hours_keywords:
            idx = text.find(keyword)
            if idx != -1:
                info["hours"] = text[idx : idx + 80].replace("\n", " ").strip()
                break

    except requests.exceptions.Timeout:
        info["error"] = "홈페이지 응답 시간 초과"
    except requests.exceptions.ConnectionError:
        info["error"] = "홈페이지에 연결할 수 없습니다"
    except Exception as e:
        info["error"] = str(e)

    return info
