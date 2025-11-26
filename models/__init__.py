"""模型模块：包含LLM和Embedding模型"""
# 处理相对导入问题
try:
    from .llm import LLM
    from .model import EmbeddingModel
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from models.llm import LLM
    from models.model import EmbeddingModel

__all__ = ['LLM', 'EmbeddingModel']
