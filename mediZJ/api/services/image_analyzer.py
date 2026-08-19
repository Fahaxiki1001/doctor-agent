"""
图片分析服务
使用独立的多模态 Vision 模型将图片解析为文字描述
"""

import base64
import json
import os
from pathlib import Path
from typing import Any, List, Optional
from loguru import logger

from mediZJ.core.llm_client import LLMClient
from mediZJ.api.models.report import ReportAnalysisDraft, ReportMeasurement

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"

VISION_PROMPT = """
请仔细分析这张医学相关的图片，用中文按以下结构输出：

## 一、图中文字提取
请逐一、完整地提取图片中出现的所有文字，包括但不限于：
- 标题、标签、表头
- 项目名称、数值、单位、参考范围
- 日期、姓名、编号等元信息
- 水印、印章、签名
- 图片边缘或角落的任何文字

对于检验报告/化验单，用 ↑↓ 标注异常项（超出参考范围的值）。

## 二、图片内容描述
- **检验报告/化验单**：描述报告的整体布局、格式类型
- **皮肤照片**：描述皮损的颜色、形态、分布、范围
- **处方单/药品**：描述处方的格式、印章位置
- **影像资料（CT/MRI/X光）**：描述可见的结构异常
- **其他类型**：描述图片的视觉特征和整体印象

请用客观、专业的语言描述，不要给出任何结论，只给出客观描述。"""

REPORT_EXTRACTION_PROMPT = """
你只负责从检验单或体检报告中提取结构化数据，不做诊断。返回严格 JSON：
{
  "document_type": "lab_report|physical_exam|other",
  "confidence": 0.0,
  "warnings": [],
  "manual_review": false,
  "measurements": [
    {"name":"", "value":"", "unit":"", "reference_range":"",
     "abnormal_flag":"low|high|normal|unknown", "confidence":0.0,
     "raw_text":"对应的简短原文"}
  ]
}
看不清或不能确定的字段使用 null，不得猜测数值、单位或参考范围。图片低清、
没有可确认指标或整体置信度低于 0.6 时设置 manual_review=true。不要提取姓名、
身份证号、电话、住址、完整报告正文或图片 Base64。"""


class ImageAnalyzer:
    """图片分析器：用 Vision 模型将图片转为文字描述"""

    def __init__(self):
        self.model_name = os.getenv("VISION_MODEL_NAME") or os.getenv(
            "LLM_MODEL_NAME", "gpt-4o"
        )
        self.api_key = os.getenv("VISION_API_KEY") or os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("VISION_BASE_URL") or os.getenv("LLM_BASE_URL")
        self.temperature = float(os.getenv("VISION_TEMPERATURE", "0.3"))
        self.max_tokens = int(os.getenv("VISION_MAX_TOKENS", "2048"))
        self.report_min_confidence = float(
            os.getenv("REPORT_VISION_MIN_CONFIDENCE", "0.6")
        )
        if not 0 <= self.report_min_confidence <= 1:
            raise ValueError("REPORT_VISION_MIN_CONFIDENCE 必须在 0 到 1 之间")

        if not self.api_key or not self.base_url:
            logger.warning(
                "Vision API 凭据未配置，图片分析将不可用。"
                "请设置 VISION_API_KEY/VISION_BASE_URL 或 LLM_API_KEY/LLM_BASE_URL"
            )

    def _get_client(self) -> LLMClient:
        """创建临时 LLMClient 实例，使用 Vision 模型配置"""
        prev = {}
        for key in (
            "LLM_MODEL_NAME",
            "LLM_API_KEY",
            "LLM_BASE_URL",
            "LLM_TEMPERATURE",
            "LLM_MAX_TOKENS",
        ):
            prev[key] = os.environ.get(key)

        try:
            os.environ["LLM_MODEL_NAME"] = self.model_name
            os.environ["LLM_API_KEY"] = self.api_key or ""
            os.environ["LLM_BASE_URL"] = self.base_url or ""
            os.environ["LLM_TEMPERATURE"] = str(self.temperature)
            os.environ["LLM_MAX_TOKENS"] = str(self.max_tokens)
            return LLMClient(model_type="openai_compatible")
        finally:
            for k, v in prev.items():
                if v is not None:
                    os.environ[k] = v
                else:
                    os.environ.pop(k, None)

    def _image_to_base64(self, image_path: str) -> Optional[str]:
        """将本地图片路径转为 base64 data URI"""
        filename = Path(image_path).name
        file_path = _UPLOAD_DIR / filename

        if not file_path.exists():
            file_path = Path(image_path)

        if not file_path.exists():
            logger.warning(f"图片文件不存在: {image_path}")
            return None

        ext = file_path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime = mime_map.get(ext, "image/jpeg")

        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{b64}"

    async def analyze(self, image_paths: List[str], user_question: str) -> str:
        """分析图片并返回增强后的问题文本

        Args:
            image_paths: 图片 URL 列表，如 ["/uploads/20260131_abc.jpg"]
            user_question: 用户原始问题文本

        Returns:
            增强后的问题文本 = 图片描述 + 用户问题
        """
        if not image_paths:
            return user_question

        if not self.api_key or not self.base_url:
            logger.warning("Vision API 未配置，跳过图片分析")
            return user_question

        try:
            client = self._get_client()
        except Exception as e:
            logger.error(f"创建 Vision LLMClient 失败: {e}，跳过图片分析")
            return user_question

        descriptions = []
        for i, img_path in enumerate(image_paths, 1):
            data_uri = self._image_to_base64(img_path)
            if not data_uri:
                descriptions.append(f"图片{i}（{img_path}）：无法加载")
                continue

            messages: Any = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ]

            try:
                response = await client.chat(messages)
                desc_text = response.strip() if response else "（无描述）"
                descriptions.append(f"图片{i}（{img_path}）：\n{desc_text}")
                logger.info(f"图片 {img_path} 分析完成 ({len(desc_text)} 字符)")
            except Exception as e:
                logger.error(f"Vision 模型分析图片 {img_path} 失败: {e}")
                descriptions.append(f"图片{i}（{img_path}）：分析失败 - {e}")

        if not descriptions:
            return user_question

        image_context = "\n\n".join(descriptions)
        enhanced = (
            f"用户提供了如下的信息：\n\n"
            f"{image_context}\n\n"
            f"---\n"
            f"用户问题：{user_question}"
        )
        return enhanced

    async def analyze_report(self, image_paths: List[str]) -> ReportAnalysisDraft:
        """Extract a validated report draft without making medical claims."""

        if not image_paths:
            return ReportAnalysisDraft(
                manual_review=True,
                warnings=["未提供报告图片"],
            )
        if not self.api_key or not self.base_url:
            return ReportAnalysisDraft(
                manual_review=True,
                warnings=["Vision 服务未配置，无法自动提取报告"],
            )
        try:
            client = self._get_client()
        except Exception:
            return ReportAnalysisDraft(
                manual_review=True,
                warnings=["Vision 服务初始化失败"],
            )

        drafts: List[ReportAnalysisDraft] = []
        for image_path in image_paths:
            data_uri = self._image_to_base64(image_path)
            if not data_uri:
                drafts.append(
                    ReportAnalysisDraft(
                        manual_review=True,
                        warnings=["报告图片无法读取"],
                    )
                )
                continue
            messages: Any = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": REPORT_EXTRACTION_PROMPT},
                    ],
                }
            ]
            try:
                response = await client.chat(messages)
                raw = (
                    response
                    if isinstance(response, str)
                    else getattr(response, "content", "")
                )
                raw = (raw or "").strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
                drafts.append(ReportAnalysisDraft.model_validate(json.loads(raw)))
            except Exception:
                drafts.append(
                    ReportAnalysisDraft(
                        manual_review=True,
                        warnings=["报告结构化提取失败，请重试或人工录入"],
                    )
                )

        measurements: List[ReportMeasurement] = []
        warnings: List[str] = []
        for draft in drafts:
            measurements.extend(draft.measurements)
            warnings.extend(draft.warnings)
        confidence = min((draft.confidence for draft in drafts), default=0)
        best_type = next(
            (
                draft.document_type
                for draft in drafts
                if draft.document_type.value != "other"
            ),
            drafts[0].document_type,
        )
        return ReportAnalysisDraft(
            document_type=best_type,
            measurements=measurements,
            confidence=confidence,
            warnings=warnings,
            manual_review=(
                any(draft.manual_review for draft in drafts)
                or confidence < self.report_min_confidence
                or not measurements
            ),
        )
