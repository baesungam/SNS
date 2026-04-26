import anthropic
import base64
import os
import io
from PIL import Image


def analyze_images(uploaded_files: list) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    image_contents = []
    for file in uploaded_files[:5]:
        file_bytes = file.read()
        file.seek(0)

        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        img_base64 = base64.standard_b64encode(buffer.getvalue()).decode()

        image_contents.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_base64,
                },
            }
        )

    image_contents.append(
        {
            "type": "text",
            "text": """이 사진들을 분석해서 다음 정보를 한국어로 추출해주세요:
1. 장소/음식/제품의 종류와 특징
2. 분위기 및 인테리어 (해당되는 경우)
3. 음식/제품의 색감, 비주얼 묘사 (구체적으로)
4. 사진에서 보이는 특이점이나 눈에 띄는 점
5. 가격 정보 (보이는 경우)

블로그 후기 작성에 활용할 수 있도록 구체적이고 생생하게 묘사해주세요.""",
        }
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": image_contents}],
    )

    return response.content[0].text
