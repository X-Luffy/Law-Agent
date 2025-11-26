"""Flow模块"""
# 处理相对导入问题
try:
    from .base import BaseFlow
    from .legal_flow import LegalFlow
except (ImportError, ValueError):
    # 如果相对导入失败，使用绝对导入
    import sys
    from pathlib import Path
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from flow.base import BaseFlow
    from flow.legal_flow import LegalFlow

__all__ = ['BaseFlow', 'LegalFlow']

