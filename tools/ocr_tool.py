"""OCR工具，用于从图片或PDF中提取文本"""
from typing import Dict, Any, Optional
import json
from .base import BaseTool
# 处理相对导入问题
try:
    from ..config.config import Config
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config.config import Config


class OCRTool(BaseTool):
    """OCR工具，用于从图片或PDF中提取文本"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        初始化OCR工具
        
        Args:
            config: 系统配置
        """
        super().__init__(
            name="ocr",
            description="Extract text from images or PDF files using OCR (Optical Character Recognition). Input should be a file path or image data. Returns the extracted text content."
        )
        self.config = config
    
    def execute(self, user_input: str, context: Dict[str, Any] = None) -> str:
        """
        执行OCR提取文本（适配BaseTool接口）
        
        Args:
            user_input: 用户输入（可以是文件路径或JSON格式的参数）
            context: 上下文信息（可选）
            
        Returns:
            提取的文本内容
        """
        import json
        
        # 尝试解析JSON格式的输入
        try:
            params = json.loads(user_input) if user_input.strip().startswith("{") else {}
            file_path = params.get("file_path") or user_input.strip()
            image_data = params.get("image_data")
        except:
            file_path = user_input.strip()
            image_data = None
        
        # TODO: 实现OCR功能
        # 可以使用以下库：
        # - pytesseract (Tesseract OCR)
        # - paddleocr (PaddleOCR)
        # - easyocr (EasyOCR)
        # - pdfplumber (PDF文本提取)
        
        # 临时返回占位信息
        if file_path:
            return json.dumps({
                "status": "pending",
                "message": f"OCR功能待实现。文件路径: {file_path}",
                "extracted_text": ""
            }, ensure_ascii=False)
        elif image_data:
            return json.dumps({
                "status": "pending",
                "message": "OCR功能待实现。已接收到图片数据。",
                "extracted_text": ""
            }, ensure_ascii=False)
        else:
            return json.dumps({
                "status": "error",
                "error": "请提供文件路径(file_path)或图片数据(image_data)"
            }, ensure_ascii=False)
    
    def to_schema(self) -> Dict[str, Any]:
        """
        将工具转换为OpenAI格式的JSON Schema
        
        Returns:
            OpenAI格式的工具定义字典
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the image or PDF file to extract text from"
                        },
                        "image_data": {
                            "type": "string",
                            "description": "Base64 encoded image data (alternative to file_path)"
                        }
                    }
                }
            }
        }

